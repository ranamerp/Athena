#from cogs.cards import setup
import pickle
import asyncio
import inspect
import discord
import re
import json
from discord.ext import commands, tasks

with open('resources/emoji_map.json', 'r') as data:
	unicodeEmotes = json.load(data)
	uni = set(unicodeEmotes.values())
	
class BackButton(discord.ui.Button):
	def __init__(self):
		super().__init__(style=discord.ButtonStyle.secondary, emoji='\U00002B05', row=0)

	async def callback(self, interaction: discord.Interaction):
		assert self.view is not None
		view: Pagnation = self.view
		if view.owner and interaction.user != view.owner:
			return

		if view.index:
			view.index -= 1
		elif not view.index and view.wraps:
			view.index = view.length - 1
		else:
			return
		
		await interaction.response.defer(thinking=False)
		#asyncio.ensure_future(view.turnPage())
		await view.turnPage()

class ForwardButton(discord.ui.Button):
	def __init__(self):
		super().__init__(style=discord.ButtonStyle.secondary, emoji='\U000027A1', row=0)

	async def callback(self, interaction: discord.Interaction):
		assert self.view is not None
		view: Pagnation = self.view
		if view.owner and interaction.user != view.owner:
			return

		if view.index != view.length - 1:
			view.index += 1
		elif view.index == view.length - 1 and view.wraps:
			view.index = 0
		else:
			return
		
		await interaction.response.defer(thinking=False)
		#print(interaction.response)
		#asyncio.ensure_future(view.turnPage())
		await view.turnPage()
		

class Page():
	def __init__(self, msg, buttons: list[discord.Button]=[], funcs={}, isAsync=False):
		self.buttons = buttons
		self.funcs = funcs
		self.msg = msg
		self.isAsync = isAsync

	def setView(self, view):
		self.view = view

	async def setProp(self, prop, value, args=[], kwargs={}, resend=False):
		try:
			if args or kwargs:
				self.msg[prop] = await self.funcs[value](*args, **kwargs)
		except KeyError:
			self.msg[prop] = value

		await self.view.turnPage(resend)

class Pagnation(discord.ui.View):
	def __init__(self, index, pages: list[Page], msg: discord.message.Message, wraps=False, owner=False, cooldown=1):
		super().__init__(timeout=122)
		self.clear_items()
		self.wraps=wraps
		self.owner=owner
		self.index=index
		self.length = len(pages)
		self.msg = msg
		#self.interaction = interaction
		self.pages = pages
		self.cd = cooldown
		for page in self.pages:
			page.setView(self)
		
		#self.turnPage(isetup=True)
		asyncio.ensure_future(self.turnPage(isetup=True))

	def setupButtons(self):
		page = self.pages[self.index]
		self.clear_items()
		if (self.index or self.wraps) and (len(self.pages) != 1):
			self.add_item(BackButton())

		for b in page.buttons:
			self.add_item(b)

		if ((self.index != len(self.pages) - 1) or self.wraps) and (len(self.pages) != 1):
			self.add_item(ForwardButton())

		
	async def turnPage(self, resend=False, isetup=False):
		page = self.pages[self.index]
		self.setupButtons()
		if not isetup:
			for item in self.children:
				item.disabled = True
		if resend:
			oldMsg = self.msg
			self.msg = await self.msg.channel.send(**page.msg, view=self)
			await oldMsg.delete()
			#await self.interaction.edit_original_message(**page.msg, view=self)
		else:
			await self.msg.edit(**page.msg, view=self)
			#await self.interaction.edit_original_message(**page.msg, view=self)

		if not isetup:
			#asyncio.ensure_future(self.liftCooldown())
			#print("test")
			await self.liftCooldown()

	async def liftCooldown(self):
		await asyncio.sleep(self.cd)

		for item in self.children:
			item.disabled = False

		#await self.interaction.edit_original_message(**self.pages[self.index].msg, view=self)
		await self.msg.edit(**self.pages[self.index].msg, view=self)

	async def on_timeout(self):
		self.clear_items()
		#await self.interaction.edit_original_message(view=self)
		await self.msg.edit(view=self)



async def getColor(conn, userid):
	try:
		color = await conn.fetchrow("SELECT * FROM economy.colors WHERE user_id = $1;", userid)
	except:
		return int("0x696969", 0)
	if not color:
		return int("0x696969", 0)
	else:
		return int(f"0x{color['hexcode']}", 0)



async def getUser(ctx, who):
	if who != None:
		try:
			user = await commands.MemberConverter().convert(ctx, who)
		except commands.BadArgument:
			try:
				user = await commands.UserConverter().convert(ctx, who)
			except commands.BadArgument:
				await ctx.send("User not found")
				return None
	else:
		user = ctx.author
	
	return user

async def getOWL(key):
	key = key.lower()
	customAbbreviations = {'cdh': 'CDH', 'hzs': 'HZS', 'hou': 'HOU', 'tor': 'TOR', 'bos': 'BOS', 'par': 'PAR', 'atl': 'ATL', 'dal': 'DAL', 'gla': 'GLA', 'gzc': 'GZC', 'seo': 'SEO', 'ldn': 'LDN', 'shd': 'SHD', 'van': 'VAN', 'val': 'VAL', 'was': 'WAS', 'phi': 'PHI', 'fla': 'FLA', 'nye': 'NYE', 'sfs': 'SFS', 'lag': 'GLA', 'lav': 'VAL', 'nyc': 'NYE', 'nyxl': 'NYE', 'ny': 'NYE', 'df': 'DAL', 'dc': 'WAS', 'fuel': 'DAL', 'dallas': 'DAL', 'philly': 'PHI', 'philadelphia': 'PHI', 'fusion': 'PHI', 'houston': 'HOU', 'outlaws': 'HOU', 'boston': 'BOS', 'uprising': 'BOS', 'excelsior': 'NYE', 'sf': 'SFS', 'shock': 'SFS', 'valiant': 'VAL', 'gladiators': 'GLA', 'florida': 'FLA', 'mayhem': 'FLA', 'shanghai': 'SHD', 'dragons': 'SHD', 'seoul': 'SEO', 'dynasty': 'SHD', 'london': 'LDN', 'spitfire': 'LDN', 'chengdu': 'CDH', 'hunters': 'CDH', 'hangzhou': 'HZS', 'spark': 'HZS', 'paris': 'PAR', 'eternal': 'PAR', 'toronto': 'TOR', 'defiant': 'TOR', 'vancouver': 'VAN', 'titans': 'VAN', 'washington': 'WAS', 'justice': 'WAS', 'atlanta': 'ATL', 'reign': 'ATL', 'rain': 'ATL', 'guangzhou': 'GZC', 'charge': 'GZC', 'glads': 'GLA', 'flm': 'FLA'}
	try:
		item = customAbbreviations.get(key)
	except TypeError:
		item = None
	return item


def emoteParse(s):
    p = re.compile("<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>")
    e = p.search(s)
    while e:
        s = s.replace(e.group(), '')
        e = p.search(s)

    s = s.replace(" ", '')
    if not (set(s) <= uni):
        return False

    return True
