import discord
import asyncio
import asyncpg
from discord.errors import NotFound
from discord.ext import commands, tasks
import datetime
from datetime import timezone, timedelta
from discord.permissions import Permissions
from discord.ext.commands.cooldowns import BucketType
from resources import helpers, queries
import os
import markovify
import re
from concurrent.futures import ProcessPoolExecutor
from collections import deque
import random
import pickle
	

class cacheSemaphore(asyncio.Semaphore):
	def __init__(self, value: int = ...) -> None:
		super().__init__(value)
		self._caches = set()
	


	# def __init__(self, value: int = ...) -> None:
	# 	super().__init__(value)
	# 	self._caches = set()

	def _wake_up_next(self, cache) -> None:
		if self._waiters:
			end = self._waiters[-1]
		while self._waiters:
			waiter = self._waiters.popleft()
			if waiter[1] == cache: 
				if not waiter[0].done():
					waiter[0].set_result(None)
					return
			elif waiter == end:
				return
			
			self._waiters.append(waiter)

	def locked(self, cache):
		return cache in self._caches

	async def acquire(self, cache):
		while cache in self._caches:
			fut = self._get_loop().create_future()
			self._waiters.append([fut, cache])

			try:
				await fut
			except:
				# See the similar code in Queue.get.
				fut.cancel()
				if cache not in self._caches and not fut.cancelled():
					self._wake_up_next(cache)
				raise
		self._caches.add(cache)
		return True

	def release(self, cache):
		self._caches.discard(cache)
		self._wake_up_next(cache)

def createSentence(model):
	simulation = model.make_sentence(max_overlap_ratio = 0.4, max_overlap_total = 3, tries=1000)

	if simulation == None:
		simulation = model.make_short_sentence(500)
		
	return simulation

def sim(trainingData, is_json):
	if not is_json:
		markov_model = markovify.NewlineText(trainingData)
	else:
		markov_model = markovify.NewlineText.from_json(trainingData)
	
	markov_model.compile(inplace=True)
	return markov_model

async def createTrainingData(conn, member):
	prog = re.compile('<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>')
	newmsg = ''
	# messages = await conn.fetch(r"SELECT content FROM discord.messages WHERE author = $1 AND (content NOT ILIKE '%http%' AND content NOT ILIKE '%<@%>%') AND content ~ '^[\x00-\x7F]+$' AND (channel != ALL (ARRAY[348870574761705483, 348939546878017536, 377127072243515393, 268751995282653195, 370677053785243648, 313824017008033802, 269131316526710788])) AND LENGTH(content) > 15 AND words >= 4 ORDER BY RANDOM() LIMIT 100000;", member)
	messages = await conn.fetch(r"SELECT content FROM discord.messages WHERE author = $1 AND (content NOT ILIKE '%http%' AND content NOT ILIKE '%<@%>%') AND content ~ '^[\x00-\x7F]+$' AND (channel != ALL (ARRAY[348939546878017536, 377127072243515393, 268751995282653195, 370677053785243648, 313824017008033802, 269131316526710788])) AND LENGTH(content) > 15 AND words >= 4 ORDER BY RANDOM() LIMIT 100000;", member)

	for msg in messages:
		s = msg['content']
		s = s.replace('\n', ' ')
		m = re.search(prog, s)
		if m != None:
			s = s.replace(m.group(0), m.group('name'))
		s += '\n'
		newmsg = newmsg + s
	return newmsg

async def aquireModel(loop, worker, conn, member):
	print("Aquiring Model")
	# Look for stored model
	stored_mod = await conn.fetchrow("SELECT * FROM discord.simulate WHERE id=$1 LIMIT 1", member)
	try:
		time = stored_mod['timestamp']
		stored_mod = stored_mod[1]

	except TypeError:
		# Build new model
		trainingData = await createTrainingData(conn, member)

		markov_model = await loop.run_in_executor(worker, sim, trainingData, False)
		
		if markov_model == None:
			return None
		
		stored_model = await loop.run_in_executor(worker, markov_model.to_json)

		time = datetime.datetime.now()
		await conn.execute("INSERT INTO discord.simulate VALUES($1,$2,$3, $4)", member, stored_model, time, False)
		mod = markov_model
	else:
		# Check if stored model needs updating
		now = datetime.datetime.now()
		if abs((now - time).days) > 30:
			messages = await conn.fetch(r"SELECT content FROM discord.messages WHERE author = $1 AND (content NOT ILIKE '%http%' AND content NOT ILIKE '%<@%>%') AND content ~ '^[\x00-\x7F]+$' AND LENGTH(content) > 15 AND words >= 4 ORDER BY RANDOM() LIMIT 100000;", member)
			trainingData = await createTrainingData(conn, member)
			mod = await loop.run_in_executor(worker, sim, trainingData, False)
			stored_model = await loop.run_in_executor(worker, mod.to_json)
			await conn.execute("UPDATE discord.simulate SET model = $1, timestamp = $3 WHERE id = $2", stored_model, member, now)
		else:
			mod = await loop.run_in_executor(worker, sim, stored_mod, True)
	
	print("Aquired Model")
	return mod

# @commands.cooldown(rate,per,BucketType) 
class SimCog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.cacheSize = 10
		self.sentences = {}
		self.sem = cacheSemaphore(10)
		self.lock = asyncio.Lock()
		self.webhookIndex = 1
		self.bothooks = {}
		self.worker = ProcessPoolExecutor(max_workers=1)
		self.simchan = True
	
	@commands.Cog.listener()
	async def on_ready(self):
		for guild in self.bot.guilds:
			self.bothooks[guild.id] = deque()
			for hook in await guild.webhooks():
				if hook.name == 'Athena':
					self.bothooks[guild.id].append(hook)
					

	async def sendWebhook(self, ctx, user, result, clear_msg=True):
		async with self.lock:
			print("entered Lock")
			bothook = discord.utils.get(await ctx.channel.webhooks(), name="Athena")
			if bothook == None:
				if len(self.bothooks[ctx.guild.id]) < 3:
					print("creating webhook")
					bothook = await ctx.channel.create_webhook(name="Athena")
					self.bothooks[ctx.guild.id].append(bothook)
					print("created webhook")
				else:
					bothook = self.bothooks[ctx.guild.id][0]
					self.bothooks[ctx.guild.id].rotate(-1)
					await bothook.edit(reason="Updating simulation", channel=ctx.channel)

			if clear_msg:
				await ctx.message.delete()
			print("sending webhook")
			await bothook.send(content=str(result), username=user.display_name, avatar_url=user.display_avatar.url)

	@commands.command(name='test')
	@commands.has_permissions(ban_members=True)
	async def testcmd(self, ctx):
		async with self.bot.db.acquire() as conn:
			mod = await createTrainingData(conn, 559575884429000725)
		with open("/test/cam.txt", "w") as f:
			f.write(mod)
		await ctx.send("done")

	@commands.cooldown(1, 1, BucketType.user) 
	@commands.command(name='simulate', aliases = ['sim'])
	#@commands.has_permissions(ban_members=True)
	async def simulate(self, ctx, user=None):
		user = await helpers.getUser(ctx, user)
		if user == None:
			return
		
		member = user.id
		result = None

		loop = asyncio.get_running_loop()

		try:
			# Look for cached sentences
			reload = False
			result = str(self.sentences[member].pop())

			await self.sendWebhook(ctx, user, result)

			if not self.sem.locked(member) and len(self.sentences[member]) < (self.cacheSize / 2):
				reload = True
				raise KeyError
			
		except (KeyError, IndexError):
			await self.sem.acquire(member)
			try:
				try:
					if len(self.sentences[member]) >= (self.cacheSize):
						result = str(self.sentences[member].pop())
						await self.sendWebhook(ctx, user, result)
					
					if len(self.sentences[member]) >= (self.cacheSize / 2):
						return
				except KeyError:
					pass

				if not reload:
					self.sentences[member] = []
					
				async with self.bot.db.acquire() as conn:
					mod = await aquireModel(loop, self.worker, conn, member)

				if result == None:
					print("Creating Result")
					result = await loop.run_in_executor(self.worker, createSentence, mod)
					print("created result")
					await self.sendWebhook(ctx, user, result)
					
				while len(self.sentences[member]) < self.cacheSize:
					print("reloading")
					self.sentences[member].append(await loop.run_in_executor(self.worker, createSentence, mod))
			finally:
				self.sem.release(member)


	@commands.cooldown(1, 3, BucketType.user) 
	@commands.command(name='story', aliases = ['storytime'])
	#@commands.has_permissions(ban_members=True)
	async def story(self, ctx, count=None, user=None):
		try:
			if int(count) >= 1 and int(count) <= 5:
				count = int(count)
			else:
				raise ValueError
		except (ValueError, TypeError):
			user = count
			count = random.randint(3,5)

		user = await helpers.getUser(ctx, user)
		if user == None:
			return
		
		member = user.id
		result = []

		loop = asyncio.get_running_loop()

		try:
			# Look for cached sentences
			reload = False
			if len(self.sentences[user.id]) < count and self.sem.locked(user.id):
				print("trying cache")
				tries = 0
				while len(self.sentences[user.id]) < count and tries < 10:
					await asyncio.sleep(.5)
					tries += 1
			elif len(self.sentences[user.id]) < count:
				raise ValueError

			print("loading from cache")
			for i in range(count):
				result.append(str(self.sentences[member].pop()))


			await ctx.message.delete()


			for r in result:
				await self.sendWebhook(ctx, user, r, clear_msg=False)

			if not self.sem.locked(member) and len(self.sentences[member]) < (self.cacheSize / 2):
				reload = True
				raise KeyError
			
		except (KeyError, IndexError):
			await self.sem.acquire(member)
			try:
				try:
					if len(self.sentences[member]) >= (self.cacheSize):
						print("loading from cache")
						for i in range(count):
							result.append(str(self.sentences[member].pop()))

						await ctx.message.delete()
						for r in result:
							await self.sendWebhook(ctx, user, r, clear_msg=False)

						if len(self.sentences[member]) >= (self.cacheSize / 2):
							return
				except KeyError:
					pass

				if not reload:
					self.sentences[member] = []
					
				async with self.bot.db.acquire() as conn:
					mod = await aquireModel(loop, self.worker, conn, member)

				if not result:
					reload = False
					
					result = self.sentences[member]
					self.sentences[member] = []
					print("Generating story")
					while len(result) < count:
						result.append(await loop.run_in_executor(self.worker, createSentence, mod))
						print("Line added")
					print("story generated")
					await ctx.message.delete()
					for r in result:
						await self.sendWebhook(ctx, user, r, clear_msg=False)
					
				while len(self.sentences[member]) < self.cacheSize:
					print("reloading")
					self.sentences[member].append(await loop.run_in_executor(self.worker, createSentence, mod))
			finally:
				self.sem.release(member)

	@commands.cooldown(1, 1, BucketType.user) 
	@commands.command(name='simchannel')
	@commands.has_permissions(ban_members=True)
	async def simchannel(self, ctx):
		#Get Top 50 Users of the year
		#Lock channel so only mods can talk
		#Choose a random user from the top 50 users, and run sim (maybe in 30 second intervals?)
		#OK MAYBE JUST COPY STORY CODE BUT THEN HAVE IT LOOP RANDOM USERS IDK
		#continue this until phrase "Athena, time to stop" (Or something along those lines)

		self.simchan = True
		async with self.bot.db.acquire() as conn:
			query = """
			select u.name, m.author, count(*) as c from discord.messages m
			LEFT JOIN discord.users u
			ON m.author = u.id
			where timestamp > '2023-12-31'
			group by 1, 2
			order by 3 DESC
			LIMIT 75
			"""

			data = await conn.fetch(query)

		#Locks the channel
		channel = ctx.channel
		await channel.send("The simulation has begun.")
		role = ctx.guild.default_role
		overwrite = channel.overwrites_for(role)
		overwrite.send_messages = False
		await channel.set_permissions(role, overwrite = overwrite)


		#To run sim cif not self.simchan:
		# 	await ctx.send("The simulation has ended")ommand
		# 
		#users = {}

		while self.simchan:
			user = random.choice(data)
			print(user)
			# if user[0] in users:
			# 	if users[user[0]]['count'] >= 2:
			# 		if users[user[0]]['passed'] >= 3:
			# 			users[user[0]]['count'] = 0
			# 			users[user[0]]['passed'] = 0
			# 		users[user[0]]['passed'] += 1
			# 		continue
			user = await helpers.getUser(ctx, user[0])
			print(user)
			#users[user[0]]['count'] += 1
			if user == None:
				continue
			member = user.id
			result = []
			count = random.randint(3,5)
			await asyncio.sleep(30)
			loop = asyncio.get_running_loop()

			try:
				# Look for cached sentences
				reload = False
				if len(self.sentences[user.id]) < count and self.sem.locked(user.id):
					print("trying cache")
					tries = 0
					while len(self.sentences[user.id]) < count and tries < 10:
						await asyncio.sleep(.5)
						tries += 1
				elif len(self.sentences[user.id]) < count:
					#raise ValueError
					print("ValueError")
					continue

				#print("loading from cache")
				for i in range(count):
					result.append(str(self.sentences[member].pop()))


				#await ctx.message.delete()


				for r in result:
					await self.sendWebhook(ctx, user, r, clear_msg=False)

				if not self.sem.locked(member) and len(self.sentences[member]) < (self.cacheSize / 2):
					reload = True
					continue
					#raise KeyError
				
			except (KeyError, IndexError):
				await self.sem.acquire(member)
				try:
					try:
						if len(self.sentences[member]) >= (self.cacheSize):
							#print("loading from cache")
							for i in range(count):
								result.append(str(self.sentences[member].pop()))

							#await ctx.message.delete()
							for r in result:
								await self.sendWebhook(ctx, user, r, clear_msg=False)

							if len(self.sentences[member]) >= (self.cacheSize / 2):
								return
					except KeyError:
						pass

					if not reload:
						self.sentences[member] = []
						
					async with self.bot.db.acquire() as conn:
						mod = await aquireModel(loop, self.worker, conn, member)

					if not result:
						reload = False
						
						result = self.sentences[member]
						self.sentences[member] = []
						#print("Generating story")
						while len(result) < count:
							result.append(await loop.run_in_executor(self.worker, createSentence, mod))
							#print("Line added")
						#print("story generated")
						#await ctx.message.delete()
						for r in result:
							await self.sendWebhook(ctx, user, r, clear_msg=False)
						
					while len(self.sentences[member]) < self.cacheSize:
						print("reloading")
						self.sentences[member].append(await loop.run_in_executor(self.worker, createSentence, mod))
				finally:
					self.sem.release(member)

			# await self.simulate(ctx, user[0])
			# await asyncio.sleep(5)

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.content.lower() == "athena end the simulation" and message.author.guild_permissions.ban_members:
			
			self.simchan = False

async def setup(bot):
	await bot.add_cog(SimCog(bot))
