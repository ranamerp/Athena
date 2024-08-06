from asyncpg.exceptions import ReadingExternalRoutineSQLDataNotPermittedError
import discord
import asyncio
import asyncpg
from discord.ext import commands, tasks
from discord.flags import alias_flag_value
from discord.message import PartialMessage
from resources import queries, helpers
import time
from datetime import timezone, timedelta, datetime
import random
import math
import os
from os.path import join, dirname
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
import requests
from io import BytesIO
import pickle

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

TOKEN = os.getenv('TOKEN')
DBPASS = os.getenv('DBPASS')
DBHOST = os.getenv('DBHOST')
DBUSER= os.getenv('DBUSER')


BACKWARDS = 1
FORWARDS = 0

rarityColors = {"Common": 0x979c9f, "Uncommon": 0x2ecc71, "Rare": 0x3498db, "Epic": 0x9b59b6, "Legendary": 0xe67e22}
rarityEmotes = {"Common": "\u26AA", "Uncommon": "\U0001F7E2", "Rare": "\U0001F535", "Epic": "\U0001F7E3", "Legendary": "\U0001F7E0"}

sp = '\U0000202F'
tb = '\U00002001'

class Card:
	def __init__(self, record):
		self.id = str(record['id'])
		self.name = str(record['name'])
		self.rarity = str(record['rarity'])
		self.description = str(record['description'])
		self.picture = str(record['picture'])
		self.set_name = str(record['set_name'])
		self.cover = str(record['cover'])
		self.count = str(record['count'])

	def createView(self):
		if self.count == 'None':
			embed = discord.Embed(title='?', description='?', colour=rarityColors[self.rarity])
			embed.set_image(url='https://cdn.discordapp.com/attachments/852709408201900042/861112936272887858/S02042JXNHF81515718127993.png')
			embed.set_thumbnail(url=self.cover)
			embed.set_footer(text=self.id)
		else:
			embed = discord.Embed(title=f"{self.name}", description=self.description, colour=rarityColors[self.rarity])
			embed.set_image(url=self.picture)
			embed.set_thumbnail(url=self.cover)
			embed.set_footer(text=self.id)
		return embed

class Page:
	def __init__(self):
		self.cards = []
		self.selected = 0

	def addCard(self, card):
		self.cards.append(card)

	def buildDisplayString(self):
		ml = max(len(s.id) for s in self.cards)
		tl = max(len(s.name) for s in self.cards)
		rl = 1
		try:
			nl = max(len(s.count) for s in self.cards if s.count != 'None')
		except ValueError as E:
			nl = 1

		i = 0
		cardsString = ""
		while i < len(self.cards):
			c = self.cards[i]			
			if i == self.selected:
				chevron = '>'
			else:
				chevron = ' '
			
			if c.count == 'None':
					cc = ' '
					cName = ' '
			else:
				cc = c.count
				cName = c.name

			cardsString += f"`{chevron} {c.id:{sp}<{ml}}{tb * 2}`\uFEFF {rarityEmotes[c.rarity]:{sp}<{rl}}\uFEFF **`{cName:{sp}<{tl}}{tb * 3}`**\uFEFF `{cc:{sp}<{nl}}`\n"
			i += 1
		return cardsString

class Album:
	def __init__(self, perPage, currSort=0, viewmode=0):
		self.pages = [Page()]
		self.allCards = []
		self.currSort = 0
		self.viewmode = 0 # 0 is overview, 1 is per card view
		self.perPage = perPage
		self.cardCount = 0

	def addCardToAlbum(self, card):
		if len(self.pages[-1].cards) >= self.perPage:
			self.pages.append(Page())

		newCard = Card(card)
		self.pages[-1].addCard(newCard)
		self.allCards.append(newCard)
		self.cardCount += 1

	def addExistingCardToAlbum(self, card):
		if len(self.pages[-1].cards) >= self.perPage:
			self.pages.append(Page())

		newCard = card
		self.pages[-1].addCard(newCard)
		self.allCards.append(newCard)
		self.cardCount += 1

	def toggleViewmode(self):
		if self.viewmode == 0:
			self.viewmode = 1
		else:
			self.viewmode = 0

	def turnPage(self, direction):
		if direction == BACKWARDS:
			if self.viewmode == 0:
				if self.currSort != len(self.pages) - 1:
					self.currSort += 1
				else:
					self.currSort = 0
			else:
				self.moveSelection(FORWARDS)
		else:
			if self.viewmode == 0:
				if self.currSort != 0:
					self.currSort -= 1
				else:
					self.currSort = len(self.pages) - 1
			else:
				self.moveSelection(BACKWARDS)

	def moveSelection(self, direction):
		page = self.pages[self.currSort]
		pageEnd = len(page.cards) - 1

		if direction == BACKWARDS:
			if self.viewmode == 0:
				if page.selected != 0:
					page.selected -= 1
				else:
					page.selected = pageEnd
			else:
				if page.selected == 0 and self.currSort == 0:
					self.currSort = len(self.pages) - 1
					page = self.pages[self.currSort]
					page.selected = len(page.cards) - 1 
				elif page.selected == 0:
					self.currSort -= 1
					page = self.pages[self.currSort]
					page.selected = len(page.cards) - 1
				else:
					page.selected -= 1
		else:
			if self.viewmode == 0:
				if page.selected != pageEnd:
					page.selected += 1
				else:
					page.selected = 0
			else:
				if page.selected == pageEnd and self.currSort == len(self.pages) - 1:
					self.currSort = 0
					page = self.pages[self.currSort]
					page.selected = 0
				elif page.selected == pageEnd:
					self.currSort += 1
					page = self.pages[self.currSort]
					page.selected = 0
				else:
					page.selected += 1

	async def printAlbum(self, ctx, user, bot, titleString):
		owned = sum([1 for s in self.allCards if s.count != 'None'])
		
		async def createEmbed(pageNum):
			if self.viewmode == 0:
				async with bot.db.acquire() as conn:
					embed = discord.Embed(title=f"{user.name}'s {titleString} - {owned}/{self.cardCount}", description=self.pages[pageNum].buildDisplayString(), colour=await helpers.getColor(conn, user.id))
				embed.set_footer(text=f"{pageNum + 1}/{len(self.pages)}")
			else:
				embed = self.pages[pageNum].cards[self.pages[pageNum].selected].createView()
				embed.set_footer(text=f"{embed.footer.text}  |  {(self.currSort * self.perPage) + self.pages[pageNum].selected + 1}/{self.cardCount}")
			
			return embed

		choices = await ctx.send(embed=await createEmbed(self.currSort))

		def check(reaction, user):
			return (user.id == ctx.author.id) and (str(reaction.emoji) in {"\U00002B05", "\U000027A1", "\U0001F53C", "\U0001F53D", "\U0001F504"}) and (reaction.message.id == choices.id)


		if len(self.pages) > 1:
			await choices.add_reaction("\U00002B05")
			await choices.add_reaction("\U000027A1")

		await choices.add_reaction("\U0001F53C")
		await choices.add_reaction("\U0001F53D")
		
		if ctx.author == user:
			await choices.add_reaction("\U0001F504")

		while True:
			try:
				done, pending = await asyncio.wait([
								ctx.bot.wait_for('reaction_add', check=check),
								ctx.bot.wait_for('reaction_remove', check=check)
							], return_when=asyncio.FIRST_COMPLETED, timeout=62)
			except asyncio.TimeoutError:
				await choices.clear_reactions()
				break

			else:
				try:
					stuff = done.pop().result()

					# Left Arrow
					if str(stuff[0].emoji) == "\U000027A1":
						self.turnPage(BACKWARDS)
						await choices.edit(embed=await createEmbed(self.currSort))
					# Right Arrow
					elif str(stuff[0].emoji) == "\U00002B05":
						self.turnPage(FORWARDS)
						await choices.edit(embed=await createEmbed(self.currSort))
					# Up Arrow
					elif str(stuff[0].emoji) == "\U0001F53C":
						self.moveSelection(BACKWARDS)
						await choices.edit(embed=await createEmbed(self.currSort))
					# Down Arrow
					elif str(stuff[0].emoji) == "\U0001F53D":
						self.moveSelection(FORWARDS)
						await choices.edit(embed=await createEmbed(self.currSort))
					# Circular Arrows
					elif str(stuff[0].emoji) == "\U0001F504":
						if ctx.author == user:
							self.toggleViewmode()
							await choices.edit(embed=await createEmbed(self.currSort))

				except Exception as E:
					if type(E) != KeyError:
						print(E)
						await ctx.send("Something went wrong! Report to merger3")

					await choices.clear_reactions()
					break


				for future in pending:
					future.cancel()

			await asyncio.sleep(.5)
			# if self.viewmode == 0: 
			# 	await asyncio.sleep(.5)
			# else:
			# 	await asyncio.sleep(1)

		for future in pending:
			future.cancel()


class CardsCog(commands.Cog):
	"""Commands relating to the CowCards Trading Card System."""

	def __init__(self, bot):
		self.bot = bot
		self.economy = self.bot.get_cog("EconCog")
		self.rarityRanks = {"Common": 1, "Uncommon": 2, "Rare": 3, "Epic": 4, "Legendary": 5}
		self.rarityEmotes = {"Common": "\u26AA", "Uncommon": "\U0001F7E2", "Rare": "\U0001F535", "Epic": "\U0001F7E3", "Legendary": "\U0001F7E0"}
		self.mostRecentPack = {}
		self.mostRecentDisplay = {}
		self.notifs = self.bot.get_cog("NotifsCog")
		self.searchReset.start()



	# async def addDB(self):
	#	creds = {"user": DBUSER, "password": DBPASS, "database": "tcg", "host": DBHOST}
	#	self.tcgDB = await asyncpg.create_pool(**creds)

	async def validSet(self, set_name):
		set_name = set_name.lower()
		async with self.bot.db.acquire() as conn:
			isSet = await conn.fetchval("SELECT COUNT(1) AS count FROM tcg.set_contents WHERE lower(set_name) = $1", set_name)
		if not isSet:
			return False
		else:
			return True

	def cog_unload(self):
		self.searchReset.cancel()

	@tasks.loop(hours=24.0)
	async def searchReset(self):
		if len(self.mostRecentDisplay) > 1000:
			self.mostRecentDisplay.clear()
			print("Cleared saved displays")


	@searchReset.before_loop
	async def before_searchReset(self):
		await self.bot.wait_until_ready()


	async def validateOffer(self, ctx, user, cardKey, conn, tradeInfo=None):
		if cardKey.lower().endswith('cc'):
			moneyOffered = abs(int(cardKey[:-2]))
			
			await self.economy.ensureAccount(ctx, user.id, conn)

			if not await self.economy.checkValue(user.id, moneyOffered, conn):
				await ctx.send(f'{user.name} does not have that much in their account!')
				return -1
			elif tradeInfo and moneyOffered < tradeInfo['min_bid']:
				await ctx.send(f"{moneyOffered} is less then {tradeInfo['min_bid']}, the minimum bid for this trade")
				return -1
			else:	
				return moneyOffered
		else:
			card = await conn.fetch(queries.FETCHUSERCARD, cardKey, user.id)
			if not card:
				await ctx.send(f"{cardKey} not found in {user.name}'s inventory")
				return -1
			else:
				if tradeInfo and self.rarityRanks[card[0]['rarity']] < self.rarityRanks[tradeInfo['min_rarity']]:
					await ctx.send(f"{card[0]['name']} is a {card[0]['rarity']}, which is lower than minimum rarity of {tradeInfo['min_rarity']} for this trade")
					return -1

				for c in card:
					if not await conn.fetchrow("SELECT * FROM tcg.offers WHERE item = $1;", c['id']):
						return c
				else:
					await ctx.send(f"All {user.name}'s copies of {card[0]['name']} are already up for trade!")
					return -1
		

	async def cancelTradeHelper(self, trade, conn, userID=None):
		tradeID = trade['id']
		async with conn.transaction():
			if not userID or userID == trade['creator']:
				moneyOffered = await conn.fetch("SELECT * FROM tcg.offers WHERE trade_id = $1 AND type = 'Currency';", tradeID)
			else:
				moneyOffered = await conn.fetch("SELECT * FROM tcg.offers WHERE trade_id = $1 AND offerer = $2 AND type = 'Currency';", tradeID, userID)

			if moneyOffered:
				for item in moneyOffered:
						await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, item['item'], item['offerer'], datetime.now(), f"Refunded Trade Offer")
			
				await self.economy.updateAccounts([o['offerer'] for o in moneyOffered], conn)
			
			if not userID or userID == trade['creator']:
				await conn.execute("DELETE FROM tcg.trades WHERE id = $1;", tradeID)
			else:
				await conn.execute("DELETE FROM tcg.offers WHERE trade_id = $1 AND offerer = $2;", tradeID, userID)



	# Requires a valid trade object and user that has made an offer
	async def completeTrade(self, trade, userID, conn):
		async with conn.transaction():
			offers = await conn.fetch("SELECT id, item, type, offerer FROM tcg.offers WHERE trade_id = $1 AND (offerer = $2 OR offerer = $3);", trade["id"], userID, trade['creator'])
			for item in offers:
				if item['offerer'] == trade['creator']:
					sender = trade['creator']
					receiver = userID
				else:
					sender = userID
					receiver = trade['creator']


				if item['type'] == 'Currency':
					await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", sender, item['item'], receiver, datetime.now(), f"Accepted Trade")
				else:
					await conn.execute("UPDATE tcg.circulation SET owner = $1, changed_hands = NOW() WHERE id = $2", receiver, item['item'])
				
				await conn.execute("DELETE FROM tcg.offers WHERE id = $1;", item['id'])	
			await self.economy.updateAccounts([sender, receiver], conn)
			await self.cancelTradeHelper(trade, conn)
		

	# in any place offers are being added, make sure that a number of items being passed to this doesn't cause the total to exceed 10
	async def addOffers(self, user, tradeID, itemsRaw, conn):
		moneyOffered = sum([n for n in itemsRaw if type(n) is int])
		items = [n for n in itemsRaw if type(n) is not int]

		async with conn.transaction():	
			for item in items:
				await conn.execute("INSERT INTO tcg.offers (offerer, item, type, trade_id, created_at) VALUES ($1, $2, $3, $4, NOW());", user.id, item['id'], 'Card', tradeID)

			if moneyOffered:
				if not await self.economy.checkValue(user.id, moneyOffered, conn):
					moneyOffered = await conn.fetchval('SELECT balance FROM economy.finances WHERE user_id = $1;', user.id)

				moneyExists = await conn.fetchval("SELECT item FROM tcg.offers WHERE trade_id = $1 AND offerer = $2 AND type = 'Currency';", tradeID, user.id)
				if moneyExists:
					await conn.execute("UPDATE tcg.offers SET item = $3 WHERE trade_id = $1 AND offerer = $2 AND type = 'Currency';", tradeID, user.id, moneyExists + moneyOffered)
				else:
					await conn.execute("INSERT INTO tcg.offers (offerer, item, type, trade_id, created_at) VALUES ($1, $2, $3, $4, NOW());", user.id, moneyOffered, 'Currency', tradeID)
				
				await conn.execute("INSERT INTO tcg.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", user.id, moneyOffered, 1, datetime.now(), f"Trade Offer")

				await self.economy.updateAccounts([user.id], conn)



	@commands.command(name='load', hidden=True)
	@commands.has_permissions(ban_members=True)
	async def loadCards(self, ctx):

		mainfont = ImageFont.truetype(BytesIO(requests.get('http://us.battle.net/forums/static/fonts/koverwatch/koverwatch.ttf').content), 120)
		sidefont = ImageFont.truetype(BytesIO(requests.get('http://us.battle.net/forums/static/fonts/bignoodletoo/bignoodletoo.ttf').content), 40)
		rarefont = ImageFont.truetype(BytesIO(requests.get('https://cdn.discordapp.com/attachments/852709408201900042/859517641328164864/DubaiW23-Medium.ttf').content), 30)

		if not ctx.message.attachments:
			await ctx.send("No attached files found!")
			return

		for f in ctx.message.attachments:
			obj = await f.read()
			players = obj.split(b'\r\n')
			players = [o.split(b',') for o in players]
			

		async with self.bot.db.acquire() as conn:
			async with conn.transaction():
				i = 0
				for player in players:
					if len(player) < 4:
						continue
					
					try:
						cardSet = str(player[4], 'UTF-8')
					except IndexError:
						cardSet= "Beta"
					
					xchan = discord.utils.get(ctx.guild.channels, name="starboard")
					template_image = 'https://cdn.discordapp.com/attachments/846584907991220274/854810471361413140/card_template_transparent.png'
					player_image = str(player[0], 'UTF-8-sig')
					player_name = str(player[1], 'UTF-8-sig')
					player_team = str(player[2], 'UTF-8-sig')
					rarity = str(player[3], 'UTF-8-sig')
					

					await conn.execute("INSERT INTO tcg.cards (name, picture, description, rarity) VALUES ($1, $2, $3, $4);", player_name, player_image, player_team, rarity)
	
			
					isSet = await conn.fetchrow("SELECT * FROM tcg.sets WHERE lower(set_name) = $1", cardSet.lower())

					if not isSet:
						await ctx.send(f"{cardSet} is not a valid set name")
						raise ReadingExternalRoutineSQLDataNotPermittedError


					cardID = await conn.fetchval("SELECT MAX(id) FROM tcg.cards")
					setLen = len(players) - 1
					rarestr = f'{i+1}/{setLen} [{rarity}]'

					pilng = requests.get(str(player_image), stream=True).raw
					try:
						player = Image.open(pilng).convert("RGBA")
					except UnidentifiedImageError:
						await ctx.send("There's been an error with this image. Sleeping for 30 seconds and trying again...", delete_after=30)
						await asyncio.sleep(30)
						try:
							pilng = requests.get(str(player_image), stream=True).raw
							player = Image.open(pilng).convert("RGBA")
						except UnidentifiedImageError:
							await ctx.send(f"This image is incompatible. {player_name}: {player_image}")
					
					player = player.resize((600,640), Image.ANTIALIAS)

					template = Image.open(requests.get(template_image, stream=True).raw).convert("RGBA")
					try:
						template.paste(player, (72,160), player)
					except ValueError:
						await ctx.send(f"Incompatible Image for {player_name}. Please provide a PNG! Current URL {player_image}")
					draw = ImageDraw.Draw(template)
					W,H = template.size
					w,h = draw.textsize(player_name, mainfont)
					w1,h1 = draw.textsize(player_team, sidefont)
					w2,h2 = draw.textsize(rarestr, rarefont)
					draw.text((((W-w) / 2), 830), player_name, align='center', font=mainfont, fill=(0,0,0))
					draw.text(((W-w1) /2 ,939), player_team, align='center', font=sidefont, fill=(33,33,33))
					draw.text((((W-w2)/2), 980), rarestr, align='center', font=rarefont, fill=(0,0,0))
					with BytesIO() as image_binary:
						template.save(image_binary, 'PNG')
						image_binary.seek(0)
						msg = await xchan.send(file=discord.File(fp=image_binary, filename=f'{player_name}-image.png'))
						imagelink = msg.attachments[0].url


					await conn.execute("UPDATE tcg.cards SET picture= $1 WHERE name=$2 AND description = $3 and rarity=$4 and ID = $5", imagelink, player_name, player_team, rarity, cardID)
					
					await conn.execute("INSERT INTO tcg.set_contents (set_name, card_id) VALUES ($1, $2)", cardSet, cardID)
					i += 1

					print(f"{i}\\{len(players) - 1} read. Player entered: {player_name} : {player_image}")

		await ctx.send("Successfully read players into database")
		

	@commands.command(name='makeset', hidden=True)
	@commands.has_permissions(ban_members=True)
	async def makeSet(self, ctx, cover, *, set_name):
		async with self.bot.db.acquire() as conn:
			if await conn.fetchrow("SELECT * FROM tcg.sets WHERE lower(set_name) = $1;", set_name.lower()):
				await ctx.send("A set with that name already exists!")
				return

			await conn.execute('INSERT INTO tcg.sets (set_name, cover, created_at) VALUES ($1, $2, NOW());', set_name, cover)

		await ctx.send(f"Created set {set_name}")


	@commands.command(name='loadset', hidden=True)
	@commands.has_permissions(ban_members=True)
	async def loadset(self, ctx):
		if not ctx.message.attachments:
			await ctx.send("No attached files found!")
			return

		for f in ctx.message.attachments:
			obj = await f.read()
			cards = obj.split(b'\r\n')
			cards = [o.split(b',') for o in cards]
				
		async with self.bot.db.acquire() as conn:
			async with conn.transaction():
				i = 0
				for card in cards:
					if len(card) < 2:
						continue

					cardSet = str(card[0], 'UTF-8')
					isSet = await conn.fetchrow("SELECT * FROM tcg.sets WHERE lower(set_name) = $1", cardSet.lower())
					if not isSet:
						await ctx.send(f"{cardSet} is not a valid set name")
						raise ReadingExternalRoutineSQLDataNotPermittedError
					await conn.execute("INSERT INTO tcg.set_contents (set_name, card_id) VALUES ($1, $2);", str(card[0], 'UTF-8'), str(card[1], 'UTF-8'))
			
					i += 1

					print(f"{i}\\{len(cards) - 1} read")

		await ctx.send("Successfully added cards to set")


	@commands.command(name='print', hidden=True)
	@commands.has_permissions(ban_members=True)
	async def printCards(self, ctx, sourceSet, packs: int, perPack: int, *odds):
		count = packs * perPack
		defaultOdds = [59, 24, 12, 4, 1]
		if not odds:
			odds = defaultOdds

		async def fillPool(rarity, conn):
			print(f"Filling {rarity} pool")
			cardDefs = await conn.fetch(queries.SETRARITYSELECTION, sourceSet, rarity)
			cards = [c['id'] for c in cardDefs]
			return cards

		printTime = datetime.now()
		await ctx.send(f"Printing {packs} packs ({count} cards)")


		if not await self.validSet(sourceSet):
			await ctx.send(f"{sourceSet} is not a valid set name")
			return

		async with self.bot.db.acquire() as conn:
			print("Creating rarity pools")
			rarityPools = {}
			for r in ('Common', 'Uncommon', 'Rare', 'Epic', 'Legendary'):
				rarityPools[r] = await fillPool(r, conn)
		
			dst = odds	
			vls = 'Common', 'Uncommon', 'Rare', 'Epic', 'Legendary'
			picks = [v for v, d in zip(vls, dst) for i in range(d)]

			async with conn.transaction():
				for i in range(count): 
					r = random.choice(picks)
					if not rarityPools[r]:
						rarityPools[r] = await fillPool(r, conn)
					
					try:
						cardSelected = rarityPools[r].pop(random.randrange(len(rarityPools[r])))
					except ValueError:
						await ctx.send("Pack not found! (Remember that this command is case sensitive!")
						return

					await conn.execute("INSERT INTO tcg.circulation (card, owner, set_name, created_at, opened) VALUES ($1, $2, $3, NOW(), FALSE);", cardSelected, 0, sourceSet)
					print("Printed card")
				await ctx.send(f"{count} cards printed, placing them into packs...")

				for i in range(packs):
					await conn.execute("INSERT INTO tcg.packs (owner, set_name, card_count, created_at) VALUES ($1, $2, $3, NOW());", 0, sourceSet, perPack)
					newPack = await conn.fetchval("SELECT MAX(id) FROM tcg.packs;")
					cardSeletions = await conn.fetch("SELECT * FROM tcg.circulation WHERE (owner = 0 AND set_name = $1) AND id NOT IN (SELECT circulation_id FROM tcg.contents) ORDER BY RANDOM() LIMIT 3;", sourceSet)

					for c in cardSeletions:
						await conn.execute("INSERT INTO tcg.contents (circulation_id, pack_id) VALUES ($1, $2);", c['id'], newPack)

					print("Created pack")

		
		await ctx.send(f"Created {packs} packs")


	@commands.command(name='open', aliases=['op', 'openpack', 'openpacks'])
	async def openPack(self, ctx, count: int, *, set_name):
		#fix packs case sensativity
		"""
		Open packs
		~open [number] [set_name]
		ALT: op/openpack/openpacks
		Open a specified number of packs you own from a particular set. Cannot open more than 10 packs
		Packs are case sensative
		EXAMPLE: ~open 3 Beta

		"""
		if count > 10:
			await ctx.send("You can only up to 10 packs at one time")
			return

		perPage = 5
		user = ctx.author

		async with self.bot.db.acquire() as conn:
			packs = await conn.fetch("SELECT * FROM tcg.packs WHERE owner= $1 AND lower(set_name) = $2 ORDER BY RANDOM() LIMIT $3;", ctx.author.id, set_name.lower(), count)
			if not packs:
				await ctx.send("You do not have any matching packs")
				return
			
			cards = []
			for p in packs: 
				cards.extend(await conn.fetch(queries.CARDSINPACK, p['id']))
						
			album = Album(perPage)
			album.viewmode = 1

			async with conn.transaction():
				for card in cards:
					album.addCardToAlbum(card)
					await conn.execute("UPDATE tcg.circulation SET owner = $1, opened = TRUE, changed_hands = NOW() WHERE id = $2;", ctx.author.id, card['circulation_id'])

				for p in packs: 
					await conn.execute("DELETE FROM tcg.packs WHERE id = $1", p['id'])

	

		self.mostRecentDisplay[ctx.author.id] = [user.id, album]
		self.mostRecentPack[ctx.author.id] = album

		await album.printAlbum(ctx, user, self.bot, "New Cards")



	@commands.command(name='lastpack', aliases=['lp'])
	async def lastPack(self, ctx):
		"""
		Show your last pack
		~lastpack
		ALT: lp
		Displays the contents of the last pack you opened
		"""
		
		album = self.mostRecentPack[ctx.author.id]
		currSort = self.mostRecentPack[ctx.author.id][1]

		await album.printAlbum(ctx, ctx.author, self.bot, "New Cards")


	@commands.command(name='collection', aliases=['cl', 'cards'])
	async def cardCollection(self, ctx, *, args=None):
		"""
		View the card collection of a user
		~collection [user] [search [term](optional)]
		ALT: cl/cards
		View the card collection of a user. Allows you to narrow down your search in a collection with specific search terms (set name, card name, card description, rarity). The word ‘search’ must be included if using search terms.  A user can be specified using their username, discord ID, and mentions. 
		If no user is specified it returns the collection of the calling user.
		EXAMPLE: ~collection AngieTheCat Doha

		"""

		if args:
			args = args.split(' ')
		perPage = 10

		async with self.bot.db.acquire() as conn:
			if not args:
				user = ctx.author
				cards = await conn.fetch(queries.GETUSERCOLLECTION, user.id)
			elif len(args) == 1:
				try:
					user = await commands.UserConverter().convert(ctx, args[0])
				except commands.BadArgument:
					await ctx.send("User not found")
					return
				cards = await conn.fetch(queries.GETUSERCOLLECTION, user.id)
			elif args[0].lower() == 'search' and len(args) >= 2:
				user = ctx.author
				searchTerms = ' '.join(args[1:])
				cards = await conn.fetch(queries.SEARCHUSERCOLLECTION, user.id, searchTerms, f"%{searchTerms}%")
			else:
				try:
					user = await commands.UserConverter().convert(ctx, args[0])
				except commands.BadArgument:
					await ctx.send("User not found")
					return

				searchTerms = ' '.join(args[2:])
				cards = await conn.fetch(queries.SEARCHUSERCOLLECTION, user.id, searchTerms, f"%{searchTerms}%")


			if not cards:
				await ctx.send(f"No cards found!")
				return

		album = Album(10)

		for card in cards:
			album.addCardToAlbum(card)

		self.mostRecentDisplay[ctx.author.id] = [user.id, album]

		await album.printAlbum(ctx, user, self.bot, "Collection")

	@commands.command(name='search', aliases=['research'])
	async def searchPrevious(self, ctx, *, args=None):
		"""
		Add additional terms to previous search command
		~search [term]
		ALT: research
		Allows you to add additional search terms to your previous search command (i.e. from ~collection). 
		Search terms are; set name, card name, card description, rarity.
		EXAMPLE: ~search epic

		"""

		perPage = 10
		try:
			results = self.mostRecentDisplay[ctx.author.id][1]
		except KeyError:
			await ctx.send("No previous search found")
			return

		# {userID: [userID, cards]}
		try:
			user = await commands.UserConverter().convert(ctx, str(self.mostRecentDisplay[ctx.author.id][0]))
			username = user.name
		except commands.BadArgument:
			await ctx.send("The user of your previous search could not be found")
			return
	
		if not args:
			album = results

		else:
			args = args.lower()
			results = results.allCards
			cards = [r for r in results if args in r.name.lower() or args == r.rarity.lower() or args == r.set_name.lower() or args in r.description.lower()]

			if not cards:
				await ctx.send("No cards found!")
				return


			album = Album(perPage)

			for card in cards:
				album.addExistingCardToAlbum(card)
		
		if ctx.invoked_with == 'search':
			self.mostRecentDisplay[ctx.author.id] = [self.mostRecentDisplay[ctx.author.id][0], album]

		await album.printAlbum(ctx, user, self.bot, "Cards")


	@commands.command(name='packs')
	async def userPacks(self, ctx, who=None):
		"""
		Shows a user’s pack collection
		~packs [user(optional)]
		Shows the pack collection of a user.  A user can be specified using their username, discord ID, and mentions. 
		If no user is specified it returns the pack collection of the calling user.
		EXAMPLE: ~packs merger3
		"""
		perPage = 5
		if who != None:
			try:
				user = await commands.UserConverter().convert(ctx, who)
			except commands.BadArgument:
				await ctx.send("User not found")
				return
		else:
			user = ctx.author

		async with self.bot.db.acquire() as conn:
			packs = await conn.fetch("SELECT set_name, COUNT(set_name) FROM tcg.packs WHERE owner = $1 GROUP BY set_name ORDER BY COUNT(set_name) DESC;", user.id)

			if not packs:
				await ctx.send(f"{user.name} has no packs!")
				return
			
			color = await helpers.getColor(conn, user.id)

		ml = max(len(str(s['set_name'])) for s in packs)
		tl = max(len(str(s['count'])) for s in packs)


		i = 0
		page = 1
		embeds = []
		while i < len(packs):
			cardsString = ""
			j = 0
			while j < perPage and i < len(packs):
				c = packs[i]			
				cardsString += f"**`{c['set_name']:{sp}<{ml}}{tb * 2}`**\uFEFF `{c['count']:{sp}<{tl}}`\n"
				j += 1
				i += 1
			
			embeds.append(discord.Embed(title=f"{user.name}'s Unopened Packs - {page}/{int(math.ceil(len(packs) / perPage))}", description=cardsString, colour=color))
			page += 1

		currSort = 0
		choices = await ctx.send(embed=embeds[currSort])

		def check(reaction, user):
			return user.id != self.bot.user.id and str(reaction.emoji) in {"\U00002B05", "\U000027A1"} and reaction.message.id == choices.id

		if len(embeds) > 1:
			await choices.add_reaction("\U00002B05")
			await choices.add_reaction("\U000027A1")


			while True:
				try:
					done, pending = await asyncio.wait([
									ctx.bot.wait_for('reaction_add', check=check),
									ctx.bot.wait_for('reaction_remove', check=check)
								], return_when=asyncio.FIRST_COMPLETED, timeout=62)
				except asyncio.TimeoutError:
					await choices.clear_reactions()
					break

				else:
					try:
						stuff = done.pop().result()

						if str(stuff[0].emoji) == "\U000027A1" and currSort != len(embeds) - 1:
								currSort += 1
								await choices.edit(embed=embeds[currSort])
						elif str(stuff[0].emoji) == "\U00002B05" and currSort != 0:
							currSort -= 1
							await choices.edit(embed=embeds[currSort])
					except:
						await choices.clear_reactions()
						break


					for future in pending:
						future.cancel()

				await asyncio.sleep(1)

			for future in pending:
				future.cancel()


	@commands.command(name='card', aliases=['vc'])
	async def viewCard(self, ctx, card):
		"""
		View a specific card from your collection
		~card [card_name/ID]
		ALT: vc
		View a specific card that you own via card name or card ID.

		EXAMPLE: 
		~card Carpe
		~card 721
		"""
		async with self.bot.db.acquire() as conn:
			card = await conn.fetch(queries.FETCHUSERCARD, card, ctx.author.id)
		
		embeds = []
		if not card:
			await ctx.send("You have none of that card! (or it does not exist)")
			return
		
		embed = discord.Embed(title=f"{card[0]['name']}", description=card[0]['description'], colour=rarityColors[card[0]['rarity']])
		embed.set_image(url=card[0]['picture'])
		embed.set_thumbnail(url=card[0]['cover'])
		embed.set_footer(text=card[0]['cardid'])
		embeds.append(embed)
		
		ml = 4
		tl = 15

		cardString = ""
		for i in range(0, 2, len(card)):
			if i == len(card) - 1 and len(card) % 2 != 0:
				cardString += f"`{card[i]['id']:{sp}<{tl}}`\n"
				break

			cardString += f"`{card[i]['id']:{sp}<{ml}}{tb * 7} {card[i + 1]['id']:{sp}<{ml}}`\n"

		embeds.append(discord.Embed(title=f"{card[0]['name']}'s Owned - {len(card)} Total", description=cardString, colour=rarityColors[card[0]['rarity']]))


		currSort = 0
		choices = await ctx.send(embed=embeds[currSort])

		def check(reaction, user):
			return user.id != self.bot.user.id and str(reaction.emoji) in {"\U00002B05", "\U000027A1"} and reaction.message.id == choices.id

		if len(embeds) > 1:
			await choices.add_reaction("\U00002B05")
			await choices.add_reaction("\U000027A1")


			while True:
				try:
					done, pending = await asyncio.wait([
									ctx.bot.wait_for('reaction_add', check=check),
									ctx.bot.wait_for('reaction_remove', check=check)
								], return_when=asyncio.FIRST_COMPLETED, timeout=62)
				except asyncio.TimeoutError:
					await choices.clear_reactions()
					break

				else:
					try:
						stuff = done.pop().result()

						if str(stuff[0].emoji) == "\U000027A1" and currSort != len(embeds) - 1:
								currSort += 1
								await choices.edit(embed=embeds[currSort])
						elif str(stuff[0].emoji) == "\U00002B05" and currSort != 0:
							currSort -= 1
							await choices.edit(embed=embeds[currSort])
					except:
						await choices.clear_reactions()
						break


					for future in pending:
						future.cancel()

				await asyncio.sleep(1)

			for future in pending:
				future.cancel()


	@commands.command(name='quicktrade', aliases=['qt', 'trade'])
	async def quickTrade(self, ctx, *offerings):
		"""
		Offer cards or CC for trade
		~quicktrade [card] [#cc]
		ALT: qt
		Puts a card, or a set of cards, up for trade. You can put upto 10 cards on offer in one listing, separated by spaces.
		Cards can be listed by either name, card id, or circulation id. CowCoins can be listed for trade by suffixing the amount with cc.

		EXAMPLE:
		~qt doha 700cc
		~qt 721 diem
		~qt 500cc
		"""

		offers = []
		
		async with self.bot.db.acquire() as conn:
			for offer in offerings:
				value = await self.validateOffer(ctx, ctx.author, offer, conn)
				if value != -1:
					offers.append(value)
				else:
					return

			if len([n for n in offers if type(n) is int]) > 10:
				await ctx.send("You can only add up to 10 cards in one trade")
				return

			newID = random.randint(0, 4095)
			t = 0
			while await conn.fetchrow("SELECT * FROM tcg.trades WHERE id = $1;", newID):
				newID = random.randint(0, 4095)
				t += 1
				if t >= 4096:
					await ctx.send("The marketplace is full!")
					return
			
			async with conn.transaction():
				await conn.execute("INSERT INTO tcg.trades (id, creator, min_rarity, min_bid, created_at) VALUES ($1, $2, $3, $4, NOW());", newID, ctx.author.id, "Common", 0)
				await self.addOffers(ctx.author, newID, offers, conn)



		await ctx.send(f"Successfully created trade owned by {ctx.author.name} with ID {hex(newID)[2:]}")
		await self.notifs.optIn('offer', ctx.author.id)

	@commands.command(name='makeoffer', aliases=['offer', 'mo'])
	async def makeOffer(self, ctx, tradeID, *offerings):
		"""
		Make an offer on an existing trade
		~makeoffer [tradeID] [offering]
		ALT: offer/mo
		Place an offer on an existing trade. You can put upto 10 cards on offer in one listing, separated by spaces. 
		Cards can be listed by either name, card id, or circulation id. CowCoins can be listed by suffixing the amount with cc.
		EXAMPLE: ~offer 7b2 doha 100cc
		"""
		async with self.bot.db.acquire() as conn:
			try:
				user = await commands.UserConverter().convert(ctx, tradeID)
				trade = await conn.fetchrow("SELECT * FROM tcg.trades WHERE creator = $1;", user.id)
			except commands.BadArgument:
				trade = await conn.fetchrow("SELECT * FROM tcg.trades WHERE id = $1;", int(('0x' + tradeID), 0))
				if not trade:
					await ctx.send("No matching trades found!")
					return
				
			offers = []
			
			for offer in offerings:

				value = await self.validateOffer(ctx, ctx.author, offer, conn)
				if value != -1:
					offers.append(value)
				else:
					return

			cardsInOffer = await conn.fetchval("SELECT COUNT(1) FROM tcg.offers WHERE trade_id = $1 AND offerer = $2 AND type = 'Card';",trade['id'], ctx.author.id)
			if cardsInOffer != None and cardsInOffer + len([n for n in offers if type(n) is int]) > 10:
				await ctx.send("You can only add up to 10 cards in one trade")
				return
			
			await self.addOffers(ctx.author, trade['id'], offers, conn)
		
		await self.notifs.notify('offer', f"New offer on your trade {tradeID} from {ctx.author.name}\n\n(Opt out with '~opt out offers' in the server", trade['creator'])
		await ctx.send(f"Successfully placed an offer on trade {hex(trade['id'])[2:]}")


	@commands.command(name='accept')
	async def acceptOffer(self, ctx, tradeID, who=None):
		"""
		Accept a trade offer
		~accept [tradeID] [user]
		Accept a trade offer from a particular user for the specified trade. This closes the trade and returns all the non-accepted offerings to their users. If there is only one offer on a trade it will automatically accept it, even if no user is specified. A user can be specified using their username, discord ID, and mentions.
		EXAMPLE: ~accept 7c4 merger3

		"""
		async with self.bot.db.acquire() as conn:
			owner = ctx.author.id
			trade = await conn.fetchrow("SELECT * FROM tcg.trades WHERE id = $1;", int(('0x' + tradeID), 0))
			if not trade:
				await ctx.send("No matching trades found!")
				return

			if trade['creator'] != owner:
				await ctx.send("You cannot accept someone else's trade")
				return

			if who != None:
				try:
					user = await commands.UserConverter().convert(ctx, who)
					offerer = user.id
					if user.id == trade["creator"]:
						await ctx.send("You cannot accept your own offers for a trade")
						return
					
					if not await conn.fetch("SELECT * FROM tcg.offers WHERE trade_id = $1 AND offerer = $2;", trade["id"], user.id):
						raise commands.BadArgument
				
				except commands.BadArgument:
					await ctx.send("User not found or has not made an offer on this trade")
					return
			else:
				user = await conn.fetch("SELECT offerer FROM tcg.offers WHERE trade_id = $1 AND offerer != $2 GROUP BY trade_id, offerer;", trade['id'], trade['creator'])
				if len(user) == 0:
					await ctx.send("No offers have been made on that trade!")
				elif len(user) > 1:
					await ctx.send("Multiple offers have been made, provide a user to accept their offer")
				else:
					offerer = user[0]['offerer']

			await self.completeTrade(trade, offerer, conn)

		await ctx.send(f"Successfully closed trade {hex(trade['id'])[2:]}")

	

	@commands.command(name='propose', aliases=['pro'])
	async def propose(self, ctx, user, *offerings):
		try:
			user = await commands.UserConverter().convert(ctx, user)
		except commands.BadArgument:
			await ctx.send("User not found")
			return
	
		if len(offerings) < 2:
			await ctx.send("You must include at least one card to give and at least one to receive")
			return

		async with self.bot.db.acquire() as conn:
			offering = []
			recieving = []
			if len(offerings) == 2:
				value = await self.validateOffer(ctx, ctx.author, offerings[0], conn)
				if value != -1:
					offering.append(value)
				else:
					return
				
				value = await self.validateOffer(ctx, user, offerings[1], conn)
				if value != -1:
					recieving.append(value)
				else:
					return

			elif 'for' in offerings:
				for i in range(len(offerings)):
					if i < offerings.index('for'):
						value = await self.validateOffer(ctx, ctx.author, offerings[i], conn)
						if value != -1:
							offering.append(value)
						else:
							return
					elif i > offerings.index('for'):
						value = await self.validateOffer(ctx, user, offerings[i], conn)
						if value != -1:
							recieving.append(value)
						else:
							return
			else:
				await ctx.send("No 'for' included, failed to parse trade")
				return

			if not offering:
				await ctx.send("You did not offer anything")
				return

			if not recieving:
				await ctx.send("You did not request anything")
				return


			newID = random.randint(0, 4095)
			t = 0
			while await conn.fetchrow("SELECT * FROM tcg.trades WHERE id = $1;", newID):
				newID = random.randint(0, 4095)
				t += 1
				if t >= 4096:
					await ctx.send("The marketplace is full!")
					return
			
			async with conn.transaction():
				await conn.execute("INSERT INTO tcg.trades (id, creator, min_rarity, min_bid, created_at) VALUES ($1, $2, $3, $4, NOW());", newID, ctx.author.id, "Common", 0)
				trade = await self.tcgDB.fetchrow("SELECT * FROM tcg.trades WHERE id = $1;", newID)
				await self.addOffers(ctx.author, newID, offering, conn)
				await self.addOffers(user, newID, recieving, conn)



			choices = ctx.message

			def check(reaction, ruser):
				if str(reaction.emoji) == "\U00002714" and ruser.id == user.id and reaction.message.id == choices.id:
					return True
				elif str(reaction.emoji) == "\U0000274C" and ruser.id in {user.id, ctx.author.id} and reaction.message.id == choices.id:
					return True
				else:
					return False

			
			# check
			await choices.add_reaction("\U00002714")
			# X
			await choices.add_reaction("\U0000274C")


			try:
				done, pending = await asyncio.wait([
								ctx.bot.wait_for('reaction_add', check=check),
								ctx.bot.wait_for('reaction_remove', check=check)
							], return_when=asyncio.FIRST_COMPLETED, timeout=302)
			except asyncio.TimeoutError:
				await choices.clear_reactions()

			else:
				try:
					stuff = done.pop().result()

					if str(stuff[0].emoji) == "\U00002714":
						await self.completeTrade(trade, user.id, conn)
						await ctx.send(f"Successfully completed trade")
					elif str(stuff[0].emoji) == "\U0000274C":
						await self.cancelTradeHelper(trade, conn)
						await ctx.send("Trade declined or cancelled")
					
				except:
					await choices.clear_reactions()


				for future in pending:
					future.cancel()

			for future in pending:
				future.cancel()


	@commands.command(name='trades', aliases=['ts'])
	async def viewTrades(self, ctx, *, args=None):
		"""
		Search trades
		~trades search [term]
		ALT: ts
		Search trades using search terms. Search terms are; set name, card name, card description, rarity, CC.
		EXAMPLE: ~trades search legendary
		"""
		perPage = 10
		if args:
			args = args.split(' ')

		async with self.bot.db.acquire() as conn:
			if not args:
				user = ctx.author
				cards = await conn.fetch(queries.SEARCHTRADESBYUSER, user.id)
			elif len(args) == 1:
				try:
					user = await commands.UserConverter().convert(ctx, args[0])
				except commands.BadArgument:
					await ctx.send("User not found")
					return
				cards = await conn.fetch(queries.SEARCHTRADESBYUSER, user.id)
			elif args[0].lower() == 'search' and len(args) >= 2:
				if len(args) == 2 and args[1].isdecimal():
					cards = await conn.fetch(queries.SEARCHTRADESBYCURRENCY, int(args[1]))
				else:
					user = ctx.author
					searchTerms = ' '.join(args[1:])
					cards = await conn.fetch(queries.SEARCHTRADESBYCARDS, searchTerms, f"%{searchTerms}%")
			else:
				try:
					user = await commands.UserConverter().convert(ctx, args[0])
				except commands.BadArgument:
					await ctx.send("User not found")
					return

				searchTerms = ' '.join(args[2:])
				cards = await conn.fetch(queries.SEARCHTRADESBYCARDSANDUSER, user.id, searchTerms, f"%{searchTerms}%")

			if not cards:
				await ctx.send(f"No cards found!")
				return
			

			i = 0
			page = 1
			embeds = []
			for a in cards:
				trade = await conn.fetchrow("SELECT *, DATE_PART('day', NOW() - created_at) age FROM tcg.trades WHERE id = $1;", a['trade_id'])

				offers = await conn.fetch(queries.CREATOROFFERSONTRADE, trade['id'], trade['creator'])

				o = offers[0]
				user = await commands.UserConverter().convert(ctx, str(o['offerer']))
				userOffers = await conn.fetch(queries.USEROFFERS, trade['id'], user.id)
			
				if o['currency'] == None:
					currency = 0
				else:
					currency = o['currency']

				if trade['description'] == None:
					desc = "No Description"
				else:
					desc = trade['description']
				dayString = f"Minimum Rarity: **{trade['min_rarity']}**\nMinimum Bid: **{trade['min_bid']}**\nAge: **{int(trade['age'])}**\nCowCoins: **{currency}**\n\uFEFF\n{desc}\n\uFEFF\n"
		
				ml = max(len(str(s['circ_id'])) for s in userOffers)
				tl = max(len(str(s['card_id'])) for s in userOffers)
				nl = max(len(s['name']) for s in userOffers)
				al = max(len(str(int(s['age']))) for s in userOffers)
				if al < 3:
					al = 3

				for c in userOffers:	
					dayString += f"`{c['circ_id']:{sp}<{ml}}{tb * 2} {c['card_id']:{sp}^{tl}}{tb}`\uFEFF {self.rarityEmotes[c['rarity']]:{sp}^{1}}\uFEFF **`{c['name']:{sp}^{nl}}{tb * 2}`**\uFEFF`{int(c['age']):{sp}^{al}}`\n"
					i += 1
				
				embeds.append(discord.Embed(title=f"{user.name}'s Trade - {hex(trade['id'])[2:]} - {page}/{len(cards)}", description=dayString, colour=await helpers.getColor(conn, user.id)))
				page += 1
		

		currSort = 0
		choices = await ctx.send(embed=embeds[currSort])

		def check(reaction, user):
			return (user.id == ctx.author.id) and (str(reaction.emoji) in {"\U00002B05", "\U000027A1"}) and (reaction.message.id == choices.id)

		if len(embeds) > 1:
			await choices.add_reaction("\U00002B05")
			await choices.add_reaction("\U000027A1")


			while True:
				try:
					done, pending = await asyncio.wait([
									ctx.bot.wait_for('reaction_add', check=check),
									ctx.bot.wait_for('reaction_remove', check=check)
								], return_when=asyncio.FIRST_COMPLETED, timeout=182)
				except asyncio.TimeoutError:
					await choices.clear_reactions()
					break

				else:
					try:
						stuff = done.pop().result()

						if str(stuff[0].emoji) == "\U000027A1" and currSort != len(embeds) - 1:
								currSort += 1
								await choices.edit(embed=embeds[currSort])
						elif str(stuff[0].emoji) == "\U00002B05" and currSort != 0:
							currSort -= 1
							await choices.edit(embed=embeds[currSort])
					except:
						await choices.clear_reactions()
						break


					for future in pending:
						future.cancel()

				await asyncio.sleep(1)

			for future in pending:
				future.cancel()


	@commands.command(name='alltrades', aliases=['at'])
	async def viewAllTrades(self, ctx, who=None):
		"""
		View all live trades for a user
		~alltrades [user]
		ALT: at
		View all live trades for a specified user. A user can be specified using their username, discord ID, and mentions. 
		EXAMPLE: ~alltrades 98106214629531648
		"""
		perPage = 10
		if who == None:
			who = 'all'
			user = ctx.author
		elif who.lower() == 'me':
			user = ctx.author
		elif who != None:
			try:
				user = await commands.UserConverter().convert(ctx, who)
			except commands.BadArgument:
				await ctx.send("User not found")
				return

		async with self.bot.db.acquire() as conn:
			if who != None and who.lower() == 'all':
				trades = await conn.fetch(queries.ALLTRADES)
				title = 'All'
			else:
				trades = await conn.fetch(queries.ALLUSERTRADES, user.id)
				title = f"{user.name}'s"

			if not trades:
				await ctx.send(f"No trades found!")
				return

			color = await helpers.getColor(conn, user.id)

		ml = 3
		cl = 1
		if set([s['amount'] for s in trades]) == {None}:
			tl = 1
		else:
			tl = max(len(str(s['amount'])) for s in trades)
		rl = max(len(s['min_rarity']) for s in trades)

		nl = max(len(str(s['min_bid'])) for s in trades)
		if nl < 3:
			nl = 3

		al = max(len(str(s['age'])) for s in trades)
		if al < 3:
			al = 3

		i = 0
		page = 1
		pages = []
		while i < len(trades):
			cardsString = f"{'id':{sp}^{ml}}{tb} {'#':{sp}^{cl}}{tb} {'$':{sp}^{tl}}{tb} {'m_b':{sp}^{nl}}{tb} {'m_r':{sp}^{3}}{tb}{'age':{sp}^{al}}\n"
			cardsString += ('-' * (len(cardsString) - 1)) + '\n'
			j = 0
			while j < perPage and i < len(trades):
				c = trades[i]			
			
				amount = c['amount']
				if amount == None:
					amount = 0

				cardsString += f"{hex(c['id'])[2:]:{sp}<{ml}}{tb} {c['items']:{sp}^{cl}}{tb} {amount:{sp}^{tl}}{tb} {c['min_bid']:{sp}^{nl}}{tb} {c['min_rarity'][:1]:{sp}^{3}}{tb}{int(c['age']):{sp}^{al}}\n"
				j += 1
				i += 1
			
			pages.append(discord.Embed(title=f"{title} Trades- {page}/{int(math.ceil(len(trades) / perPage))}", description=f"```asciidoc\n{cardsString}```", colour=color))
			page += 1

		
		currSort = 0
		choices = await ctx.send(embed=pages[currSort])

		def check(reaction, user):
			return (user.id == ctx.author.id) and (str(reaction.emoji) in {"\U00002B05", "\U000027A1"}) and (reaction.message.id == choices.id)

		if len(pages) > 1:
			await choices.add_reaction("\U00002B05")
			await choices.add_reaction("\U000027A1")


			while True:
				try:
					done, pending = await asyncio.wait([
									ctx.bot.wait_for('reaction_add', check=check),
									ctx.bot.wait_for('reaction_remove', check=check)
								], return_when=asyncio.FIRST_COMPLETED, timeout=62)
				except asyncio.TimeoutError:
					await choices.clear_reactions()
					break

				else:
					try:
						stuff = done.pop().result()

						if str(stuff[0].emoji) == "\U000027A1" and currSort != len(pages) - 1:
								currSort += 1
								await choices.edit(embed=pages[currSort])
						elif str(stuff[0].emoji) == "\U00002B05" and currSort != 0:
							currSort -= 1
							await choices.edit(embed=pages[currSort])
					except:
						await choices.clear_reactions()
						break


					for future in pending:
						future.cancel()

				await asyncio.sleep(1)

			for future in pending:
				future.cancel()


	@commands.command(name='cancel', aliases=['c'])
	async def cancelTrade(self, ctx, tradeID):
		"""
		Cancel a trade or trade offer.
		~cancel [tradeID]
		ALT: c
		Cancel a trade
		EXAMPLE: ~c 5q4
		"""
		async with self.bot.db.acquire() as conn:
			owner = ctx.author.id
			trade = await conn.fetchrow("SELECT * FROM tcg.trades WHERE id = $1;", int(('0x' + tradeID), 0))
			
			if not trade:
				await ctx.send("No matching trades found!")
				return

			if trade['creator'] == owner:
				await self.cancelTradeHelper(trade, conn)
				await ctx.send(f"Cancelled trade {hex(trade['id'])[2:]}")
			else:
				offers = await conn.fetch("SELECT * FROM tcg.offers WHERE trade_id = $1 AND offerer = $2;", trade['id'], ctx.author.id)
				if offers:
					await self.cancelTradeHelper(trade, conn, ctx.author.id)
					await ctx.send(f"Removed your offers on trade {hex(trade['id'])[2:]}")
				else:
					await ctx.send("You haven't made any offers on that trade")

		


	@commands.command(name='viewtrade', aliases=['vt'])
	async def viewTrade(self, ctx, tradeID):
		"""
		View a trade
		~viewtrade [tradeID]
		ALT: vt
		Display a trade and all offers on it.
		"""
		async with self.bot.db.acquire() as conn:
			trade = await conn.fetchrow("SELECT *, DATE_PART('day', NOW() - created_at) age FROM tcg.trades WHERE id = $1;", int(('0x' + tradeID), 0))
			if not trade:
				await ctx.send("No matching trades found!")
				return

			creator = await commands.UserConverter().convert(ctx, str(trade['creator']))
			offers = await conn.fetch(queries.CREATOROFFERSONTRADE, trade['id'], trade['creator'])
			offers.extend(await conn.fetch(queries.ALLOFFERSONTRADE, trade['id'], trade['creator']))

			i = 0
			page = 1
			embeds = []
			while i < len(offers):
				o = offers[i]
				user = await commands.UserConverter().convert(ctx, str(o['offerer']))
				userOffers = await conn.fetch(queries.USEROFFERS, trade['id'], user.id)
				
				if user.id == trade['creator']:
					if o['currency'] == None:
						currency = 0
					else:
						currency = o['currency']

					if trade['description'] == None:
						desc = "No Description"
					else:
						desc = trade['description']
					dayString = f"Minimum Rarity: **{trade['min_rarity']}**\nMinimum Bid: **{trade['min_bid']}**\nAge: **{int(trade['age'])}**\nCowCoins: **{currency}**\n\uFEFF\n{desc}\n\uFEFF\n"
				else:
					if o['currency'] == None:
						currency = 0
					else:
						currency = o['currency']
					dayString = f"__**{user.name}'s** Offer:__\nCard Value: **{o['value']}**\nCowCoins: **{currency}**\n\uFEFF\n"

				if userOffers:
					ml = max(len(str(s['circ_id'])) for s in userOffers)
					tl = max(len(str(s['card_id'])) for s in userOffers)
					nl = max(len(s['name']) for s in userOffers)
					al = max(len(str(int(s['age']))) for s in userOffers)
					if al < 3:
						al = 3

					for c in userOffers:	
						dayString += f"`{c['circ_id']:{sp}<{ml}}{tb * 2} {c['card_id']:{sp}^{tl}}{tb}`\uFEFF {self.rarityEmotes[c['rarity']]:{sp}^{1}}\uFEFF **`{c['name']:{sp}^{nl}}{tb * 2}`**\uFEFF`{int(c['age']):{sp}^{al}}`\n"
						i += 1
				
				embeds.append(discord.Embed(title=f"{creator.name}'s Trade - {hex(trade['id'])[2:]} - {page}/{len(offers)}", description=dayString, colour=await helpers.getColor(conn, user.id)))
				page += 1
			

		currSort = 0
		choices = await ctx.send(embed=embeds[currSort])

		def check(reaction, user):
			return (user.id == ctx.author.id) and (str(reaction.emoji) in {"\U00002B05", "\U000027A1"}) and (reaction.message.id == choices.id)

		if len(embeds) > 1:
			await choices.add_reaction("\U00002B05")
			await choices.add_reaction("\U000027A1")


			while True:
				try:
					done, pending = await asyncio.wait([
									ctx.bot.wait_for('reaction_add', check=check),
									ctx.bot.wait_for('reaction_remove', check=check)
								], return_when=asyncio.FIRST_COMPLETED, timeout=182)
				except asyncio.TimeoutError:
					await choices.clear_reactions()
					break

				else:
					try:
						stuff = done.pop().result()

						if str(stuff[0].emoji) == "\U000027A1" and currSort != len(embeds) - 1:
								currSort += 1
								await choices.edit(embed=embeds[currSort])
						elif str(stuff[0].emoji) == "\U00002B05" and currSort != 0:
							currSort -= 1
							await choices.edit(embed=embeds[currSort])
					except:
						await choices.clear_reactions()
						break


					for future in pending:
						future.cancel()

				await asyncio.sleep(1)

			for future in pending:
				future.cancel()


	@commands.command(name='quickopen', aliases=['qo'])
	async def quickOpenPacks(self, ctx, count: int, *, set_name):
		"""
		Open packs, efficiently
		~quickopen [number] [set]
		ALT: qo
		Opens multiple packs in a condensed format compared to ~open
		EXAMPLE: ~qo 5 Beta
		"""

		perPage = 5
		user = ctx.author
		async with self.bot.db.acquire() as conn:
			packs = await conn.fetch("SELECT * FROM tcg.packs WHERE owner= $1 AND lower(set_name) = $2 ORDER BY RANDOM() LIMIT $3;", ctx.author.id, set_name.lower(), count)
			if not packs:
				await ctx.send("You do not have any matching packs")
				return
			
			cards = []
			for p in packs: 
				cards.extend(await conn.fetch(queries.CARDSINPACK, p['id']))
						
			album = Album(perPage)
			async with conn.transaction():
				for card in cards:
					album.addCardToAlbum(card)
					await conn.execute("UPDATE tcg.circulation SET owner = $1, opened = TRUE, changed_hands = NOW() WHERE id = $2;", ctx.author.id, card['circulation_id'])

				for p in packs: 
					await conn.execute("DELETE FROM tcg.packs WHERE id = $1", p['id'])

		self.mostRecentDisplay[ctx.author.id] = [user.id, album]

		await album.printAlbum(ctx, user, self.bot, "New Cards")


	@commands.command(name='edit', aliases=['edt'])
	async def editTrade(self, ctx, tradeID, setting, *, value):
		"""
		Modify trade details
		~edit [tradeID] [setting] [value]
		ALT: edt
		Allows you to set certain parameters in a trade.
		Settings;
		minimumbid/minbid/bid/mb: allow you to set the minimum amount of CowCoins for offers on the trade.
		minimumrarity/minrarity/rarity/mr: allow you to set the minimum rarity of cards offered on the trade.
		description/desc/d: set a searchable description on the trade

		EXAMPLE:
		~edit 7a4 minbid 1000
		~edit 7a4 mr Legendary
		~edit 7a4 desc Looking for either a legendary or a generous amount of CowCoins for this trade.

		"""
		owner = ctx.author.id
		tradeID = int(('0x' + tradeID), 0)
		async with self.bot.db.acquire() as conn:
			trade = await conn.fetchrow("SELECT * FROM tcg.trades WHERE id = $1;", tradeID)
			if not trade:
				await ctx.send("No matching trades found!")
				return

			if trade['creator'] != owner:
				await ctx.send("You cannot edit someone else's trade")
				return

			setting = setting.lower()
			if setting in {"minbid", "bid", "minimumbid", "mb"}:
				if not value.isdecimal():
					await ctx.send("Minimum bid must be a number")
					return
				
				await conn.execute("UPDATE tcg.trades SET min_bid = $1 WHERE id = $2;", abs(int(value)), tradeID)

			elif setting in {"minrarity", "rarity", "minimumrarity", "mr"}:
				if value.lower() not in {"common", "uncommon", "rare", "epic", "legendary"}:
					await ctx.send("Invalid minimum rarity")
					return

				await conn.execute("UPDATE tcg.trades SET min_rarity = $1 WHERE id = $2;", value.lower().capitalize(), tradeID)

			elif setting in {"description", "desc", "d"}:

				await conn.execute("UPDATE tcg.trades SET description = $1 WHERE id = $2;", value[:1000], tradeID)
			else:
				await ctx.send("Not a valid field to modify")
				return
			
		await ctx.send("Modified Trade")


	@commands.command(name='collectionstats', aliases=['cs'])
	async def collectionStats(self, ctx, who=None):
		"""
		Collection statistics for a user
		~collectionstats [user(optional)]
		ALT: cs
		Shows an overview of the collection for a user. A user can be specified using their username, discord ID, and mentions. 
		If no user is specified it returns the collection statistics of the calling user. 

		EXAMPLE: ~cs K1NG_IC3

		"""
		perPage = 5
		if who == None or who.lower() == 'me':
			user = ctx.author
		else:
			try:
				user = await commands.UserConverter().convert(ctx, who)
			except commands.BadArgument:
				await ctx.send("User or set not found")
				return
				
		async with self.bot.db.acquire() as conn:
			stats = await conn.fetch(queries.COLLECTIONSTATS, user.id)
			stats.extend(await conn.fetch(queries.COLLECTIONSTATSBYSET, user.id))

			if not stats:
				await ctx.send(f"{user.name} has no cards yet!")

			color = await helpers.getColor(conn, user.id)

		ml = max(len(s['set_name']) for s in stats)
		cl = max(len(str(s['commons'])) for s in stats)
		ul = max(len(str(s['uncommons'])) for s in stats)
		rl = max(len(str(s['rares'])) for s in stats)
		el = max(len(str(s['epics'])) for s in stats)
		ll = max(len(str(s['legendaries'])) for s in stats)
		tl = max(len(str(s['total'])) for s in stats)

		i = 0
		page = 1
		embeds = []
		while i < len(stats):
			cardsString = f"__**`{'Set Name':{sp}^{ml}}{tb}`**\uFEFF `{'T':{sp}^{tl}}{tb * 2}{'L':{sp}^{ll}}{tb * 2}{'E':{sp}^{el}}{tb * 2}{'R':{sp}^{rl}}{tb * 2}{'U':{sp}^{ul}}{tb * 2}{'C':{sp}^{cl}}`__\n"

			j = 0
			while j < perPage and i < len(stats):
				c = stats[i]			
				
				cardsString += f"**`{c['set_name']:{sp}<{ml}}{tb}`**\uFEFF `{c['total']:{sp}<{tl}}{tb * 2}{c['legendaries']:{sp}<{ll}}{tb * 2}{c['epics']:{sp}<{el}}{tb * 2}{c['rares']:{sp}<{rl}}{tb * 2}{c['uncommons']:{sp}<{ul}}{tb * 2}{c['commons']:{sp}<{cl}}`\n"
				j += 1
				i += 1
			
			embeds.append(discord.Embed(title=f"{user.name}'s Collection Stats - {page}/{int(math.ceil(len(stats) / perPage))}", description=cardsString, colour=color))
			page += 1
		
		currSort = 0
		choices = await ctx.send(embed=embeds[currSort])

		def check(reaction, user):
			return (user.id == ctx.author.id) and (str(reaction.emoji) in {"\U00002B05", "\U000027A1"}) and (reaction.message.id == choices.id)

		if len(embeds) > 1:
			await choices.add_reaction("\U00002B05")
			await choices.add_reaction("\U000027A1")


			while True:
				try:
					done, pending = await asyncio.wait([
									ctx.bot.wait_for('reaction_add', check=check),
									ctx.bot.wait_for('reaction_remove', check=check)
								], return_when=asyncio.FIRST_COMPLETED, timeout=62)
				except asyncio.TimeoutError:
					await choices.clear_reactions()
					break

				else:
					try:
						stuff = done.pop().result()

						if str(stuff[0].emoji) == "\U000027A1" and currSort != len(embeds) - 1:
								currSort += 1
								await choices.edit(embed=embeds[currSort])
						elif str(stuff[0].emoji) == "\U00002B05" and currSort != 0:
							currSort -= 1
							await choices.edit(embed=embeds[currSort])
					except:
						await choices.clear_reactions()
						break


					for future in pending:
						future.cancel()

				await asyncio.sleep(1)

			for future in pending:
				future.cancel()

	@commands.command(name='owldex', aliases=['od'])
	async def owldex(self, ctx, *, args=None):
		"""
		View your collection, including missing cards
		~owldex [search [term](optional)]
		View your collection together with the cards you are missing from it. Missing cards are ‘blank’ and only show the ID of the card. 
		Search terms are; set name, card name, card description, rarity.
		"""
		if args:
			args = args.split(' ')
		perPage = 10

		async with self.bot.db.acquire() as conn:
			if not args:
				user = ctx.author
				cards = await conn.fetch(queries.POKEDEXQUERY, user.id)
			elif len(args) == 1:
				try:
					user = await commands.UserConverter().convert(ctx, args[0])
				except commands.BadArgument:
					await ctx.send("User not found")
					return
				cards = await conn.fetch(queries.POKEDEXQUERY, user.id)
			elif args[0].lower() == 'search' and len(args) >= 2:
				user = ctx.author
				searchTerms = ' '.join(args[1:])
				cards = await conn.fetch(queries.SEARCHPOKEDEX, user.id, searchTerms, f"%{searchTerms}%")
			else:
				try:
					user = await commands.UserConverter().convert(ctx, args[0])
				except commands.BadArgument:
					await ctx.send("User not found")
					return

				searchTerms = ' '.join(args[2:])
				cards = await conn.fetch(queries.SEARCHPOKEDEX, user.id, searchTerms, f"%{searchTerms}%")


		if not cards:
			await ctx.send(f"No cards found!")
			return

		album = Album(10)

		for card in cards:
			album.addCardToAlbum(card)

		self.mostRecentDisplay[ctx.author.id] = [user.id, album]

		await album.printAlbum(ctx, user, self.bot, "OWLdex")


async def setup(bot):
	await bot.add_cog(CardsCog(bot))
