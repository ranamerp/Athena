import discord
import asyncio
import asyncpg
from discord import app_commands
from discord.ext import commands
import time
import datetime
from datetime import timezone, timedelta, datetime
import random
from resources import queries, helpers
import pickle



class StoreCog(commands.Cog):
	"""Commands used to buy items from our shop using CowCoins """
	def __init__(self, bot):
		self.bot = bot
		self.prices = {"color": 500, "beta": 250, "historical": 750}
		self.economy = self.bot.get_cog("EconCog")
		self.cards = self.bot.get_cog("CardsCog")
		self.stock = self.bot.get_cog("StockCog")
	


	@commands.hybrid_group(case_insensitive=True)
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def buy(self, ctx:commands.Context):
		"""
		Buy items from the shop. 
		Items you can buy: 

		COLOR
		Buy a new random embed color
		~buy color
		ALT: buy colour
		Buy a new color for command embeds from the store for 500CC.

		PACKS
		Buy packs from the store
		~buy pack(s) [number] [set_name]
		Buy a specified number of packs from the store from a specific set available in the store.
		EXAMPLE: ~buy packs 3 Beta
		Set names are case specific
		"""
		if ctx.invoked_subcommand is None:
			await ctx.send('Please specify something to buy')
	
	@commands.hybrid_group(case_insensitive=True)
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def sell(self, ctx:commands.Context):
		if ctx.invoked_subcommand is None:
			await ctx.send('Please specify something to sell')		

	@buy.command(name='color', aliases=['colour', 'warna'])
	async def buyColor(self, ctx:commands.Context):
		"""
		Buy a new random embed color
		~buy color
		ALT: buy colour
		Buy a new color for command embeds from the store for 500CC.

		"""
		async with self.bot.db.acquire() as conn:
			await self.economy.ensureAccount(ctx, ctx.author.id, conn)
			
			item = "color"

			if not await self.economy.checkValue(ctx.author.id, self.prices[item], conn):
				await ctx.send('You do not have that much in your account!')
				return
			
			async with conn.transaction():
				await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", ctx.author.id, self.prices[item], 1, datetime.now(), f"{item.upper()} Purchase")

				random_number = random.randint(0,16777215)
				hex_number = str(hex(random_number))[2:]

				embed = discord.Embed(title=f"{ctx.author.name}'s New Color - {hex_number}", colour=int(f"0x{hex_number}", 0))
				

				hasColor = await conn.fetchrow("SELECT * FROM economy.colors WHERE user_id = $1;", ctx.author.id)
				if hasColor:
					await conn.execute("UPDATE economy.colors SET hexcode = $1, reroll_count = $2 WHERE user_id = $3;", hex_number, hasColor['reroll_count'] + 1, ctx.author.id)
				else:
					await conn.execute("INSERT INTO economy.colors (user_id, hexcode, reroll_count) VALUES ($1, $2, $3);", ctx.author.id, hex_number, 1)


			await self.economy.updateAccounts([ctx.author.id], conn)
		await ctx.send(f"{ctx.author.name} bought a new color for {self.prices[item]:,d} CC", embed=embed)

	@buy.command(name='pack', aliases=['packs'])
	async def pack(self, ctx:commands.Context, count:int, *, set_name:str):
		"""Buy a pack of cards"""
		if not set_name:
			set_name = 'Beta'

		count = int(count)

		async with self.bot.db.acquire() as conn:
			await self.economy.ensureAccount(ctx, ctx.author.id, conn)

			if not await self.cards.validSet(set_name):
				await ctx.send(f"{set_name} is not an existing set (remember that set name is case sensitive)")
				return

			item = set_name.lower()

			if await conn.fetchval("SELECT COUNT(1) FROM tcg.packs WHERE lower(set_name) = $1 AND owner = 0;", set_name.lower()) < count:
				await ctx.send(f"There are less than {count} {set_name} packs in the store right now")
				return

			if not await self.economy.checkValue(ctx.author.id, self.prices[item] * count, conn):
				await ctx.send('You do not have that much in your account!')
				return
		

			async with conn.transaction():
				await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", ctx.author.id, self.prices[item] * count, 1, datetime.now(), f"{item} Purchase")
				await conn.execute("UPDATE tcg.packs SET owner = $1 WHERE id IN (SELECT id FROM tcg.packs WHERE lower(set_name) = $2 AND owner = 0 ORDER BY RANDOM() LIMIT $3);", ctx.author.id, set_name.lower(), count)

			
			await self.economy.updateAccounts([ctx.author.id], conn)
			
			await ctx.send(f"{ctx.author.name} bought {count} {set_name} packs for {self.prices[item] * count:,d} CC")			

	@buy.command(name='stock')
	async def buyStock(self, ctx:commands.Context, team:str, amount: str):
		"""Buy a team stock"""
		if not team:
			await ctx.send("Please enter a team to buy!", delete_after = 5)
			return
		if not amount:
			await ctx.send("Please enter how much you want to invest.", delete_after=5)
			return		
		
		team = team.lower()
		team = await helpers.getOWL(team)
		if not team:
			await ctx.send("Team not found!", delete_after=5)
			return

		



		async with self.bot.db.acquire() as conn:
			await self.economy.ensureAccount(ctx, ctx.author.id, conn)
			
			if amount.lower() == "random":
				maxamount = await self.economy.getAccValue(ctx, ctx.author, conn)
				amount = int(random.randint(100, maxamount-500))
			else:
				try:
					amount = int(amount)
				except Exception:
					return

			if amount < 0:
				await ctx.send("Please give a positive value", delete_after=5)
				return
			if not await self.economy.checkValue(ctx.author.id, amount, conn):
					await ctx.send('You cannot invest that much!', delete_after=5)
					return

			time = datetime.now()
			async with conn.transaction():
				q = await conn.fetchrow("SELECT currentprice, updatedprice, highprice, lowprice, volume, ticker FROM economy.market WHERE teamshort=$1", team)
				if int(q['ticker']) == 5:
					nextval = 0
				else:
					nextval = int(q['ticker']) + 1
				price = q['currentprice']
				uprice = q['updatedprice']
				numStock = round(amount / price, 2)
				newupdate = ((0.01 * numStock) * uprice) + uprice
				newvol = q['volume'] + numStock
				await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", ctx.author.id, amount, 1, time, f"Buying {team} stock")
				await conn.execute("INSERT INTO economy.history (teamshort, date, oldprice, volume, newprice, note) VALUES ($1, $2, $3, $4, $5, $6);", team, time, uprice, numStock, newupdate, "Buy")
				await conn.execute("INSERT INTO economy.portfolio (userid, teamshort, initprice, totalprice, count, datebought) VALUES ($1, $2, $3, $4, $5, $6)", ctx.author.id, team, price, amount, numStock, time)
				await conn.execute("UPDATE economy.market SET updatedprice=$1, lastupdated=$2, volume=$4, ticker=$5 WHERE teamshort = $3", newupdate, time, team, newvol, nextval)
				if nextval % 5 == 0:
					await self.stock.currentmarket(conn, price, team, q['highprice'], q['lowprice'])
				
			await self.economy.updateAccounts([ctx.author.id], conn)

		await ctx.send(f"{ctx.author.name} bought {numStock} stock ({round(amount, 2)} CC) of {team}@{round(price, 2)}")

	@sell.command(name='stock')
	async def sellStock(self, ctx:commands.Context, team:str, amount: str):
		"""Sell a team stock"""
		if not team:
			await ctx.send("Please enter a team you wish to sell!", delete_after = 5)
			return
		if not amount:
			await ctx.send("Please enter how much you want to invest.", delete_after=5)
			return		

		team = team.lower()
		team = await helpers.getOWL(team)
		if not team:
			await ctx.send("Team not found!", delete_after=5)
			return
		
		
		async with self.bot.db.acquire() as conn:
			await self.economy.ensureAccount(ctx, ctx.author.id, conn)
			
			market = await conn.fetchrow("SELECT currentprice, updatedprice, highprice, lowprice, volume, ticker FROM economy.market WHERE teamshort = $1 ORDER BY teamshort;", team)
			if int(market['ticker']) == 5:
				nextval = 0
			else:
				nextval = int(market['ticker']) + 1
			currentprice = market['currentprice']
			uprice = market['updatedprice']
			
			volume = market['volume']

			totalstockowned = await conn.fetchrow("SELECT sum(count) as count FROM economy.portfolio WHERE teamshort = $1 AND userid=$2 GROUP BY teamshort ORDER BY teamshort", team, ctx.author.id)
			try:
				currenttotalvalue = totalstockowned['count'] * currentprice
			except TypeError:
				await ctx.send("You do not own any stock in that team!", delete_after=5)
			
			if amount.lower() == 'all':
				amount = currenttotalvalue
			else:
				amount = int(float(amount))
				if amount < 0:
					await ctx.send("Please give a positive value", delete_after=5)
					return

			

			portfolio = await conn.fetch(queries.SELLPORTFOLIO, team, ctx.author.id)
			global_amount = round(amount)
			flag = False
			totalstocksold = round(amount/currentprice, 2)
			
			newupdatevalue = uprice - (((0.01 * totalstocksold) * uprice))
			if newupdatevalue < 0:
				newupdatevalue = 0
			if amount > currenttotalvalue:
				await ctx.send("You do not have this much stock to sell!", delete_after=5)
				return
			async with conn.transaction():
				for stock in portfolio:
					if flag == True:
						break
					stockcount = stock['count']
					currentstockvalue = round(currentprice * stockcount, 2)
					await conn.execute("DELETE FROM economy.portfolio WHERE userid = $1 and teamshort = $2 and initprice = $3 and totalprice = $4 and datebought =$5", ctx.author.id, team, stock['initprice'], stock['totalprice'], stock['datebought'])
					if global_amount > currentstockvalue:
						global_amount -= currentstockvalue
						global_amount = round(global_amount)
					else:
						newpersonalvalue = currentstockvalue - global_amount
						numberstocksold = round(global_amount/currentprice, 2)
						newstockcount = stockcount - numberstocksold
						if newstockcount < 0:
							newstockcount = 0
						newvolume = volume - totalstocksold
						if newvolume < 0:
							newvolume = 0

						await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, amount, ctx.author.id, datetime.now(), f"Selling {team} stock")
						await conn.execute("UPDATE economy.market SET updatedprice=$1, lastupdated=$2, volume=$4, ticker=$5 WHERE teamshort = $3", newupdatevalue, datetime.now(), team, newvolume, nextval)
						if newpersonalvalue != 0:
							await conn.execute("INSERT INTO economy.portfolio (userid, teamshort, initprice, totalprice, count, datebought) VALUES ($1, $2, $3, $4, $5, $6);", ctx.author.id, team, stock['initprice'], newpersonalvalue, newstockcount, stock['datebought'])
						flag = True
			
				await conn.execute("INSERT INTO economy.history (teamshort, date, oldprice, volume, newprice, note) VALUES ($1, $2, $3, $4, $5, $6);", team, datetime.now(), uprice, totalstocksold, newupdatevalue, "Sell")	
				if nextval % 5 == 0:
					await self.stock.currentmarket(conn, currentprice, team, market['highprice'], market['lowprice'])
					
			await self.economy.updateAccounts([ctx.author.id], conn)
		await ctx.send(f"{ctx.author.name} sold {totalstocksold} stock ({round(amount, 2)} CC) of {team}@{round(currentprice, 2)}")	
				

	@commands.command(name='color', aliases=['colour', 'warna'])
	#@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def color(self, ctx:commands.Context, who: str=None):
		"""Get your current embed color"""
		if who != None:
			try:
				user = await commands.UserConverter().convert(ctx, who)
			except commands.BadArgument:
				await ctx.send("User not found")
				return
		else:
			user = ctx.author

		async with self.bot.db.acquire() as conn:
			color = await helpers.getColor(conn, user.id)

		embed = discord.Embed(title=f"{user.name}'s Color - {hex(color)[2:]}", colour=color)
		await ctx.send(embed=embed)


	@commands.hybrid_group(case_insensitive=True)
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def store(self, ctx:commands.Context):
		"""
		View items available in the store
		Currently supported store items:

		PACKS
		~store pack
		ALT: store packs
		Displays the packs currently available in the store and their prices.


		"""
		if ctx.invoked_subcommand is None:
			await ctx.send('Please specify something to buy')
	
	@store.command(name='pack', aliases=['packs'])
	async def viewPacks(self, ctx:commands.Context):
		"""View all packs avaliable in the store"""
		async with self.bot.db.acquire() as conn:
			packs = await conn.fetch(queries.GETPACKSINSTORE)
		if not packs:
			await ctx.send("There are no packs in the store right now!")
			return

		embeds = []
		num = 1
		for p in packs:
			embed = discord.Embed(title=f"{p['set_name']} - {num}/{len(packs)}", description=f"**In shop: {p['count']}\nCards per Pack: 3\nPrice: {self.prices[p['set_name'].lower()]}**", colour=await helpers.getColor(self.bot, ctx.author.id))
			embed.set_image(url=p['cover'])
			embeds.append(helpers.Page({'embed': embed}))

			num += 1

		currSort = 0
		choices = await ctx.send(**embeds[currSort].msg)
		if len(embeds) > 1:
			await choices.edit(view=helpers.Pagnation(currSort, embeds, choices, wraps=False, owner=ctx.author))
					


async def setup(bot):
	await bot.add_cog(StoreCog(bot))
