import discord
import asyncio
import asyncpg
from discord.ext import commands
import time
import datetime
from datetime import timezone, timedelta
from discord.ext.commands.cooldowns import BucketType
from random import *
import os
from os.path import join, dirname
from dotenv import load_dotenv
from resources import helpers
import pickle


dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
 
# Accessing variables.
DBPASS = os.getenv('DBPASS')
DBHOST = os.getenv('DBHOST')
DBUSER= os.getenv('DBUSER')
DBDATABASE= os.getenv('DBDATABASE')

prices = {"color": 500}


class EconCog(commands.Cog):
	"""Commands relating to the economy"""
	def __init__(self, bot):
		self.bot = bot
		self.starred = {}
	#	asyncio.ensure_future(self.addDB())


	# async def addDB(self):
	#	creds = {"user": DBUSER, "password": DBPASS, "database": "economy", "host": DBHOST}
	#	self.db = await asyncpg.create_pool(**creds)



	async def timeoutCheck(self, msg_id, user_id):
		try:
			if user_id in self.starred[msg_id]:
				return False
			else:
				return True
		except KeyError:
			return True


	async def cooldownUserStars(self, msg_id, user_id):
		try:
			self.starred[msg_id].add(user_id)
		except KeyError:
			self.starred[msg_id] = {user_id}
		# await asyncio.sleep(60)
		# self.starred[msg_id].discard(user_id)

	async def hasAcc(self, user_id, conn: asyncpg.Connection):
		userAccount = await conn.fetchrow("SELECT * FROM economy.finances WHERE user_id = $1;", user_id)
		if userAccount:
			return True
		else:
			return False

	async def updateAccounts(self, user_ids, conn: asyncpg.Connection):
		async with conn.transaction():
			for user_id in user_ids:
				userAccount = await conn.fetchrow("SELECT * FROM economy.finances WHERE user_id = $1;", user_id)
				if not userAccount:
					continue
				updatedTime = datetime.datetime.now()
				newAmount = await conn.fetchrow("SELECT SUM(value) AS to_add FROM (SELECT (CASE WHEN sender_id = $1 THEN amount * -1 ELSE amount END) AS value FROM economy.transactions WHERE date > $2 AND (sender_id = $1 OR reciever_id = $1)) t;", user_id, userAccount['last_updated'])	
				if newAmount['to_add'] == None:
					to_add = 0
				else:
					to_add = newAmount['to_add']
					await conn.execute("UPDATE economy.finances SET balance = $1, last_updated = $2 WHERE user_id = $3", userAccount['balance'] + to_add, updatedTime, user_id)

	async def checkValue(self, user_id, value, conn: asyncpg.Connection):

		userAccount = await conn.fetchrow("SELECT * FROM economy.finances WHERE user_id = $1;", user_id)

		if userAccount['balance'] >= value:
			return True
		else:
			return False

	async def ensureAccount(self, ctx, userID, conn: asyncpg.Connection):
		newAccountValue = 10000
		userAccount = await conn.fetchrow("SELECT * FROM economy.finances WHERE user_id = $1;", userID)
		if userAccount == None:
			try:
				user = await commands.UserConverter().convert(ctx, str(userID))
			except commands.BadArgument:
				print("Couldn't find user, cancelling account creation")
				return
			print(f"Opening new account for {user.name}")
			async with conn.transaction():
				await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, newAccountValue, user.id, datetime.datetime.now(), "Opened new account")
				userAccount = await conn.execute("INSERT INTO economy.finances (user_id, balance, last_updated) VALUES ($1, $2, $3);", user.id, 0, datetime.datetime.fromtimestamp(1))
			await self.updateAccounts([userID], conn)
		else:
			await self.updateAccounts([userID], conn)
			return


	async def getAccValue(self, ctx, user, conn: asyncpg.Connection):
		await self.ensureAccount(ctx, user.id, conn)
		return await conn.fetchval('SELECT balance FROM economy.finances WHERE user_id = $1', user.id)

	@commands.command(name='wealthleaderboard', aliases = ['wlb'])
	async def wealthleaderboard(self, ctx):
		sp = '\U0000202F'
		tb = '\U00002001'
		async with self.bot.db.acquire() as conn:
			records = await conn.fetch("SELECT user_id, balance from economy.finances WHERE user_id != 1 ORDER BY balance DESC, user_id LIMIT 50")
		names = {}
		for p in records:
			user = await commands.UserConverter().convert(ctx, str(p['user_id']))
			names[p['user_id']] = user.name[:11]
	
		
		tNames = list(names.values())	
		ml = max(len(s) for s in tNames)
		rl = len(f"{len(records)}.")
		wl = max(len(str(s["balance"])) for s in records)
		embeds = []
		i = 0
		page = 1

		while i < len(records):
			leaderboardString = f"__`{'Name':{sp}^{rl + ml + 3}}`__\uFEFF__`{'Balance':{sp}<{wl}}`__\n"
			j = 0
			while j < 10 and i < len(records):
				r = records[i]
				leaderboardString += f"`{str(i + 1) + '.':{sp}<{rl}}`\uFEFF**`{names[r['user_id']]:{sp}<{ml}}{tb * 2}`**\uFEFF`{r['balance']:{sp}<{wl}}`\n"
				j += 1
				i += 1
			embeds.append(helpers.Page({'embed': discord.Embed(title=f"Balance Leaderboard {page}/{(int(len(records) / 10)) + (int(len(records) % 10 > 0))}", description=leaderboardString, colour=0xff8900)}))
			page += 1
		currSort = 0
		choices = await ctx.send(**embeds[currSort].msg)
		if len(embeds) > 1:
			await choices.edit(view=helpers.Pagnation(currSort, embeds, choices, wraps=False))
		
		
	@commands.command(name='openaccount')
	async def openAcc(self, ctx):
		async with self.bot.db.acquire() as conn:
			await self.ensureAccount(ctx, ctx.author.id, conn)



	@commands.command(name='balance', aliases=['bal', 'b'])
	async def balance(self, ctx, who=None):
		""" 
		View CC Balance
		~balance [user(optional)]
		ALT: bal, b
		Shows the CowCoin balance of a user. A user can be specified using their username, discord ID, and mentions. 
		If no user is specified it returns the balance of the calling user.
		EXAMPLE: ~bal K1NG_IC3
		"""
		if who != None:
			try:
				user = await commands.UserConverter().convert(ctx, who)
			except commands.BadArgument:
				await ctx.send("User not found")
				return
		else:
			user = ctx.author

		async with self.bot.db.acquire() as conn:
			await self.ensureAccount(ctx, user.id, conn)
			userAccount = await conn.fetchrow("SELECT * FROM economy.finances WHERE user_id = $1;", user.id)

		await ctx.send(f"{user.name} has {userAccount['balance']:,d} in their account")

	@commands.command(name='give')
	async def give(self, ctx, recipient: discord.User, amount: int):
		"""
		Give cowcoins to a user
		~give [user]
		Give some of your balance to another user. A user can be specified using their username, discord ID, and mentions. 
		If no user is specified it returns the predictions of the calling user.

		EXAMPLE: ~give TeeHaychZee#1975

		"""
		async with self.bot.db.acquire() as conn:
			amount = abs(amount)
			await self.ensureAccount(ctx, ctx.author.id, conn)
			await self.ensureAccount(ctx, recipient.id, conn)

			if not await self.checkValue(ctx.author.id, amount, conn):
				await ctx.send('You do not have that much in your account!')
				await self.bot.db.release(conn)
				return


			async with conn.transaction():
				await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", ctx.author.id, amount, recipient.id, datetime.datetime.now(), "Direct payment")
				await self.updateAccounts([ctx.author.id, recipient.id], conn)

			await self.ensureAccount(ctx, ctx.author.id, conn)
			await self.ensureAccount(ctx, recipient.id, conn)


		await ctx.send(f"{ctx.author.name} sent {amount:,d} to {recipient.name}")
		

	@commands.command(name='steal')
	async def steal(self, ctx, recipient: discord.User, amount: int):

		if ctx.author.id not in {143730443777343488, 131768212797784064, 104369222167056384, 160439346032279552}:
			return

		async with self.bot.db.acquire() as conn:
			amount = abs(amount)
			await self.ensureAccount(ctx, ctx.author.id, conn)
			await self.ensureAccount(ctx, recipient.id, conn)


			async with conn.transaction():
				await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", recipient.id, amount, ctx.author.id, datetime.datetime.now(), "Theft")
				await self.updateAccounts([ctx.author.id, recipient.id], conn)

			await self.ensureAccount(ctx, ctx.author.id, conn)
			await self.ensureAccount(ctx, recipient.id, conn)


		await ctx.send(f"{ctx.author.name} took {amount:,d} from {recipient.name}")
		

	@commands.command(name='get', hidden=True)
	async def getMoney(self, ctx, amount: int):
		amount = abs(amount)
		#						 merger				 king				 tee				 putty
		if ctx.author.id not in {143730443777343488, 131768212797784064, 104369222167056384, 160439346032279552}:
			return
			
		
		async with self.bot.db.acquire() as conn:
			async with conn.transaction():
				await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, amount, ctx.author.id, datetime.datetime.now(), "Taken directly from house")

			await self.ensureAccount(ctx, ctx.author.id, conn)

			await self.updateAccounts([ctx.author.id], conn)
			

		await ctx.send(f"{ctx.author.name} recieved {amount:,d} from the house")

	@commands.command(name='stimulus', aliases=['stim'], hidden=True)
	async def stimulus(self, ctx, amount: int):
		amount = abs(amount)
		if ctx.author.id not in {143730443777343488, 131768212797784064, 104369222167056384}:
			print(f"{ctx.author.name} Attempted to use stimulus without permission")
			return


		msg = await ctx.send("Distributing stimulus...")

		async with self.bot.db.acquire() as conn:
			async with conn.transaction():
				users = [u['user_id'] for u in await conn.fetch("SELECT user_id FROM economy.finances;")]
				for u in users:
					await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, amount, u, datetime.datetime.now(), "Stimulus Check")
			
			await self.updateAccounts(users, conn)

		await msg.edit(content=f"Sent all users {amount} CC")


async def setup(bot):
	await bot.add_cog(EconCog(bot))
