import datetime
import re
import asyncio
import asyncpg
import discord
from discord.ext import commands
import os
from os.path import join, dirname
from dotenv import load_dotenv


dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
 
# Accessing variables.
DBPASS = os.getenv('DBPASS')
DBHOST = os.getenv('DBHOST')
DBUSER= os.getenv('DBUSER')
DBDATABASE= os.getenv('DBDATABASE')

class ParserCog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.starred = {}
	#	asyncio.ensure_future(self.addDB())
	# 	self.parse.start()

	# def cog_unload(self):
	# 	self.parse.cancel()

	#async def addDB(self):
	#	creds = {"user": DBUSER, "password": DBPASS, "database": "discord", "host": DBHOST}
	#	self.db = await asyncpg.create_pool(**creds)


	async def embedParse(self, value):
		return value


	async def nullParser(self, value):
		if not value:
			return None
		else:
			return value


	async def embedImage(self, value):
		if not value:
			return None
		else:
			if not value.url:
				if not value.proxy_url:
					return None
				else:
					return value.proxy_url
			else:
				return value.url


	async def getRef(self, reference):
		try:
			ref = reference.reference.message_id
		except AttributeError:
			ref = None

		return ref

	async def getName(self, value):
		try:
			name = value.emoji.name
		except AttributeError:
			name = value

		return name




	@commands.command(name='update')
	@commands.has_permissions(ban_members=True)
	async def update(self, ctx):
		print("Starting update parse...")
		overall = 0
		reactCount = 0

		async with self.bot.db.acquire() as conn:
			# Begin loop over channels
			for textchan in ctx.guild.channels:
				if textchan.type == discord.ChannelType.category:
					cate = await conn.fetchrow("SELECT * FROM discord.categories WHERE id = $1", textchan.id)
					if cate != None:
						await conn.execute("DELETE FROM discord.categories WHERE id = $1;", textchan.id)
					await conn.execute("INSERT INTO discord.categories VALUES ($1, $2, $3, $4, $5, $6);", textchan.id, textchan.guild.id, textchan.name, textchan.position, textchan.created_at, textchan.created_at)

				elif textchan.type in [discord.ChannelType.text, discord.ChannelType.news] and textchan.id != 378193791846318080:
					threads = textchan.threads
					threads.append(textchan)
					for chan in threads:
						c = await conn.fetchrow("SELECT * FROM discord.channels WHERE id = $1", chan.id)
						if c != None:
							await conn.execute("DELETE FROM discord.channels WHERE id = $1;", chan.id)
						if chan.type in [discord.ChannelType.news_thread, discord.ChannelType.public_thread, discord.ChannelType.private_thread]:
							await conn.execute("INSERT INTO discord.channels VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);", chan.id, chan.guild.id, await self.nullParser(chan.category_id), chan.name, None, None, chan.created_at, chan.created_at, chan.parent_id)
						else:
							await conn.execute("INSERT INTO discord.channels VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);", chan.id, chan.guild.id, await self.nullParser(chan.category_id), chan.name, chan.topic, chan.position, chan.created_at, chan.created_at, None)

						# Pull the mark messages
						latest = await conn.fetch("SELECT * FROM discord.messages WHERE channel=$1 ORDER BY timestamp DESC LIMIT 10;", chan.id)
						for m in latest:
							try:
								mark = await chan.fetch_message(m["id"])
								break
							except Exception as E:
								print("Couldn't get latest message, trying backup")
								print(E)
						else:
							print("Unable to get valid message from", chan.name, ", using defaults")
							mark = None

						print(f"Updating messages from {chan.name}")
						counter = 0
						total = 0
						etotal = 0
						dupe = 0
						async for chat in chan.history(limit=None, after=mark):
							if counter == 1000:
								print(total, "from", chan.name)
								counter = 0
							# try:
							# except asyncpg.exceptions.UniqueViolationError:
							# 	dupe += 1

							await conn.execute("INSERT INTO discord.messages VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11);", chat.id, chat.author.id, chat.content, chat.channel.id, chat.guild.id, chat.pinned, bool(chat.edited_at), chat.jump_url, await self.getRef(chat), len(re.compile("\\s+").split(chat.content)), chat.created_at)

							for attach in chat.attachments:
								await conn.execute("INSERT INTO discord.attachments VALUES ($1, $2, $3, $4, $5, $6);", attach.id, chat.id, attach.size, attach.filename, attach.url, bool(attach.height))

							for em in chat.embeds:
								await conn.execute("INSERT INTO discord.embeds (message_id, title, description, url, image) VALUES ($1, $2, $3, $4, $5);", chat.id, await self.embedParse(em.title), await self.embedParse(em.description), await self.embedParse(em.url), await self.embedImage(em.image))

							reactOrder = 0
							for r in chat.reactions:
								reactOrder += 1
								userOrder = 0

								async for u in r.users():
									userOrder += 1
									# print(chat.id, chat.jump_url)
									if type(r.emoji) == str:
										await conn.execute("INSERT INTO discord.reactions VALUES ($1, $2, ASCII($3), $4, $5, $6, $7, $8, $9);", chat.id, r.emoji, r.emoji, False, None, False, u.id, reactOrder, userOrder)
									else:
										if r.emoji.name == None:
											r.emoji.name = "Deleted"
										await conn.execute("INSERT INTO discord.reactions VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);", chat.id, r.emoji.name, await self.nullParser(r.emoji.id), True, str(r.emoji.url), r.emoji.animated, u.id, reactOrder, userOrder)
									reactCount += 1
									etotal += 1

							counter += 1
							total += 1
							overall += 1

						print("Finished updating", chan.name, "with", dupe, "duplicates")
						print(total, "messages updated from", chan.name, "and", etotal, "reactions")
						print(overall, "Total Messages Parsed and", reactCount, "Total Reactions")

			print("Finished Updating Messages")


			print("Updating usernames...")

			users = set(ctx.guild.members)
			print("Server members retrieved")

			count = 0
			total = len(users)

			for user in users:
				if count == 1000:
					print("Processed", count, "of", total)
					count = 0
				try:
					avi = user.avatar.with_size(4096).url
					is_ani = user.avatar.is_animated()
				except AttributeError:
					avi = None
					is_ani = False
				custom_name_record = await conn.fetchrow("SELECT custom_name FROM discord.users WHERE id = $1;", user.id)
				if custom_name_record == None:
					await conn.execute("INSERT INTO discord.users VALUES ($1, $2, $3, $4, $5, $6, $7);", user.id, user.name, user.discriminator, bool(user.bot), avi, is_ani, user.created_at)
				else:
					if custom_name_record["custom_name"]:
						await conn.execute("UPDATE discord.users SET discriminator = $1, avatar = $2, animated_avatar = $3 WHERE id = $4;", user.discriminator, avi, is_ani, user.id)
					else:
						await conn.execute("UPDATE discord.users SET name = $1, discriminator = $2, avatar = $3, animated_avatar = $4 WHERE id = $5;", user.name, user.discriminator, avi, is_ani, user.id)

				count += 1

			print("Finished updating", total,  "usernames")


			# Update users
			print("Fetching new users")
			newUsers = await conn.fetch('SELECT author FROM discord.messages WHERE author NOT IN (SELECT id FROM discord.users) GROUP BY author;')
			print("Found", len(newUsers), "new users")

			ids = set([i["author"] for i in newUsers])

			total = len(ids)
			count = 0
			notFound = 0
			notFoundList = []

			for i in ids:
				user = None
				try:
					user = await self.bot.fetch_user(i)
				except discord.NotFound as E:
					print(E)
					msgID = await conn.fetchrow("SELECT * FROM discord.messages WHERE author=$1 LIMIT 1;", i)
					chan = self.bot.get_channel(msgID["channel"])
					if chan != None:
						msg = await chan.fetch_message(msgID["id"])
						user = msg.author

				if user != None:
					try:
						try:
							avi = user.avatar.with_size(4096).url
							is_ani = user.avatar.is_animated()
						except AttributeError:
							avi = None
							is_ani = False
						await conn.execute("INSERT INTO discord.users VALUES ($1, $2, $3, $4, $5, $6, $7);", user.id, user.name, user.discriminator, bool(user.bot), avi, is_ani, user.created_at)
						count += 1
						print("Processed", user.name, "-", count, "of", total, "with", notFound, "errored")
					except asyncpg.exceptions.UniqueViolationError as E:
						print("Name not found!")
						notFound += 1
						print(E)
						notFoundList.append(i)

			print(count, "users read into database")

		print("Finished Update!")


async def setup(bot):
	await bot.add_cog(ParserCog(bot))


