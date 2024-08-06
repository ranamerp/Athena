import traceback
import sys
import discord
import asyncio
from discord.ext import commands
from discord import app_commands
import asyncpg
import time
import os
from os.path import join, dirname
from dotenv import load_dotenv
import pickle

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
 
# Accessing variables.
TOKEN = os.getenv('TOKEN')
DBPASS = os.getenv('DBPASS')
DBHOST = os.getenv('DBHOST')
DBUSER= os.getenv('DBUSER')
DBDATABASE= os.getenv('DBDATABASE')




initial_extensions = ["notifications", "economy", "casino", "parser", "chat", "blackjack", "sim", "games"]
class Bot(commands.Bot):
	def __init__(self, **kwargs):
		super().__init__(
			description=kwargs.pop("description"),
			command_prefix=("~", "-"),
			case_insensitive=True,
			intents=kwargs.pop("intents"),
			help_command=None
		)
		
	def setDB(self, database):
		self.db: asyncpg.Pool = database

	async def setup_hook(self):
		for extension in initial_extensions:
			try:
				await self.load_extension("cogs." + extension)
			except Exception as e:
				print(f"{e}")
				traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
	
	async def on_ready(self):
		print('We have logged in as {0.user}'.format(self))

bot = Bot(description="The narrator of Overwatch", intents=discord.Intents.all())

@bot.command()
@commands.has_permissions(ban_members=True)
async def sync(ctx):
	#print(ctx.guild.id)
	try:
		await bot.tree.sync(guild=discord.Object(id=ctx.guild.id))
		await ctx.send("We are now synced to this guild")
	except discord.HTTPException as e:
		print(e)
		pass

	
async def run():
	async with bot:
		# NOTE: 127.0.0.1 is the loopback address. If your db is running on the same machine as the code, this address will work
		credentials = {"user": DBUSER, "password": DBPASS, "database": DBDATABASE, "host": DBHOST}
		db = await asyncpg.create_pool(**credentials)

		
		bot.setDB(db)

		
		try:
			await bot.start(TOKEN)
		except KeyboardInterrupt:
			# Make sure to do these steps if you use a command to exit the bot
			await db.close()
			await bot.logout()

@bot.command(name="help", description="Returns all commands available")
async def help(ctx, *input):
	hiddencogs = ['ParserCog']
	if not input:

		emb = discord.Embed(title='Commands and modules', color=discord.Color.blue(),
							description=f'Use `~help <module>` to gain more information about that module ')

		cogs_desc = ''
		for cog in bot.cogs:
			if str(cog) not in hiddencogs:
				cogs_desc += f'`{str(cog)}` {bot.cogs[cog].__doc__}\n'

		emb.add_field(name='Modules', value=cogs_desc, inline=True)
	else:
		for cog in bot.cogs:
			if cog.lower() == (input[0]).lower():
				emb = discord.Embed(title=f'{cog} - Description',
									description=bot.cogs[cog].__doc__,
									color=discord.Color.green())

				for command in bot.get_cog(cog).get_commands():
					if not command.hidden:
						if len(command.short_doc) < 1:
							doc = None
						else:
							doc = command.short_doc
						emb.add_field(name=f"`~{command.name}`", value=doc, inline=True)
				break
		else:
			if input[0] in bot.all_commands:
				cmd = bot.all_commands[input[0]]
				emb = discord.Embed(
					title=f'{cmd} - Commands', 
					description=cmd.help,
					color=discord.Color.green())
			
			else:
				await ctx.send("Help command not found!", delete_after=5)
				return

	await ctx.send(embed=emb)

@bot.command()
@commands.has_permissions(ban_members=True)
async def reload(ctx, *modules):
	modules = list(modules)
	
	if "all" in modules:
		for extension in initial_extensions:
			try:
				await bot.reload_extension("cogs." + extension)
			except commands.ExtensionError as e:
				await ctx.send(f'{e}')
			else:
				await ctx.send(f'Reloaded {extension}')

		await ctx.send("All extensions have been reloaded")

	else:
		for m in modules:
			try:
				await bot.reload_extension("cogs." + m)
			except commands.ExtensionError as e:
				await ctx.send(f'{e}')
			else:
				await ctx.send(f'Reloaded {m}')

@bot.check
async def channel_filter(ctx):
	command = ctx.command.name
	aliases = ctx.command.aliases
	chan = ctx.message.channel.name
	aliases.append(command)
	flag = True
	async with bot.db.acquire() as conn:
		for item in aliases:
			items = await conn.fetch("SELECT channel, command FROM discord.filters WHERE command=$1 AND channel=$2", item, chan)
			if len(items) > 0:
				flag = False
				break
	
	return flag 

@bot.command(name='addfilter', aliases = ['af', 'afilter', 'addfil'], hidden = True)
@commands.has_permissions(ban_members=True)
async def add_filter(ctx, command, channel=None):
	"""
	Adds a filter to the filter list
	Syntax: ~addfilter [command] [channel]
	Aliases: ~af, ~afilter, ~addfil
	"""
	if channel==None: 
		channel = ctx.message.channel.name
	
	async with bot.db.acquire() as conn:
		comm = await conn.fetch("SELECT channel, command FROM discord.filters WHERE command=$1 AND channel=$2", command, channel)
		if len(comm) > 0 :
			await ctx.send("This command is already filtered in this channel!")
			return
		else:
			await conn.execute("INSERT INTO discord.filters (channel, command) VALUES ($1, $2)", channel, command)

	await ctx.send(f"Successfully added {command} in {channel} to the filter!")

@bot.command(name='removefilter', aliases = ['rf', 'rfilter', 'removefil'], hidden=True)
@commands.has_permissions(ban_members=True)
async def remove_filter(ctx, command, channel=None):
	"""
	Removes a filter from the filter list
	Syntax: ~removefilter [command] [channel]
	Aliases: ~rf, ~rfilter, ~removefil
	"""
	if channel==None: 
		channel = ctx.message.channel.name
	
	async with bot.db.acquire() as conn:
		await conn.execute("DELETE FROM discord.filters WHERE channel=$1 and command=$2", channel, command)

	await ctx.send(f"Successfully removed {command} in {channel} to the filter!")

@bot.command(name='filters', hidden=True)
@commands.has_permissions(ban_members=True)
async def list_filters(ctx, channel=None):
	"""
	Lists all filters in the server
	Syntax: ~filters [channel]
	"""
	if channel == None:
		channel = ctx.message.channel.name
	
	async with bot.db.acquire() as conn:
		filters = await conn.fetch("SELECT channel, command FROM discord.filters ORDER BY channel")
		dic ={}
		for item in filters:
			dic.setdefault(item['channel'], []).append(item['command'])

		if channel.lower()=="all":
			chatstr = ""
			for chan in dic:
				dic[chan].sort()
				chatstr += f"Commands filtered in {chan}: {dic[chan]}\n"
			await ctx.send(chatstr)
		
		else:
			for chan in dic:
				if chan == channel:
					dic[chan].sort()
					await ctx.send(f"Commands filtered in {channel}: {dic[chan]}")

	
@bot.event
async def on_command_error(ctx, error):
	"""The event triggered when an error is raised while invoking a command.
	ctx   : Context
	error : Exception"""
	# This prevents any commands with local handlers being handled here in on_command_error.
	if hasattr(ctx.command, 'on_error'):
		return

	# ignored = (commands.CommandNotFound, commands.UserInputError)
	ignored = (commands.CommandNotFound)

	# Allows us to check for original exceptions raised and sent to CommandInvokeError.
	# If nothing is found. We keep the exception passed to on_command_error.
	error = getattr(error, 'original', error)

	# Anything in ignored will return and prevent anything happening.
	if isinstance(error, ignored):
		return

	elif isinstance(error, commands.CommandOnCooldown):
		await ctx.message.delete()
		# await ctx.send(f"Command is on cooldown for {int(error.retry_after)} more seconds", delete_after=3)
		return

	elif isinstance(error, commands.CheckFailure):
		print("A check function failed")
		return
	else:
		print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
		traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)



# @bot.event
# async def on_message(message):
# 	if isinstance(message.channel, discord.DMChannel) and message.author.id not in {143730443777343488, 136594603829755904}:
# 		return

# 	#if message.channel.name in {"general", "overwatch", "ow-esports", "other-games", "other-esports", "sports", "anime", "creative", "music", "politics"}:
# 	#	return

# 	if message.author == bot.user:
# 		return

if __name__ == '__main__':
	asyncio.run(run())
