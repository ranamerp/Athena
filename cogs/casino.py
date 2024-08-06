import discord
import asyncio
import asyncpg
from discord.ext import commands
import time
import datetime
from datetime import timezone, timedelta
from discord.ext.commands.cooldowns import BucketType
from random import *
import pickle
from resources import helpers

tableTypes = {"coinflip", "roulette"}
# [number, color, even/odd, high/low, column, dozen]
rt = [["00", 'green', 'None', 'None', 0, 1], [0, 'green', 'None', 'None', 0, 1], [1, 'red', 'odd', 'low', 1, 1], [2, 'black', 'even', 'low', 2, 1], [3, 'red', 'odd', 'low', 3, 1], [4, 'black', 'even', 'low', 1, 1], [5, 'red', 'odd', 'low', 2, 1], [6, 'black', 'even', 'low', 3, 1], [7, 'red', 'odd', 'low', 1, 1], [8, 'black', 'even', 'low', 2, 1], [9, 'red', 'odd', 'low', 3, 1], [10, 'black', 'even', 'low', 1, 1], [11, 'black', 'odd', 'low', 2, 1], [12, 'red', 'even', 'low', 3, 1], [13, 'black', 'odd', 'low', 1, 2], [14, 'red', 'even', 'low', 2, 2], [15, 'black', 'odd', 'low', 3, 2], [16, 'red', 'even', 'low', 1, 2], [17, 'black', 'odd', 'low', 2, 2], [18, 'red', 'even', 'low', 3, 2], [19, 'red', 'odd', 'high', 1, 2], [20, 'black', 'even', 'high', 2, 2], [21, 'red', 'odd', 'high', 3, 2], [22, 'black', 'even', 'high', 1, 2], [23, 'red', 'odd', 'high', 2, 2], [24, 'black', 'even', 'high', 3, 2], [25, 'red', 'odd', 'high', 1, 3], [26, 'black', 'even', 'high', 2, 3], [27, 'red', 'odd', 'high', 3, 3], [28, 'black', 'even', 'high', 1, 3], [29, 'black', 'odd', 'high', 2, 3], [30, 'red', 'even', 'high', 3, 3], [31, 'black', 'odd', 'high', 1, 3], [32, 'red', 'even', 'high', 2, 3], [33, 'black', 'odd', 'high', 3, 3], [34, 'red', 'even', 'high', 1, 3], [35, 'black', 'odd', 'high', 2, 3], [36, 'red', 'even', 'high', 3, 3]]
sp = '\U0000202F'
tb = '\U00002001'


async def genPotVals(n, value):
	l = []
	for i in range(n):
		base = value / n
		for j in range(0 + i):
			cut = (base / (i - j + 3))
			l[j] += cut
			base -= cut
		l.append(base)
	return l


class RouletteNumber:
		def __init__(self, number, color, OE, HL, column, dozen):
			self.number = number
			self.color = color
			self.OE = OE
			self.HL = HL
			self.column = column
			self.dozen = dozen


class RouletteTable:
	def __init__(self):
		self.chart = self.createTable()
		self.wheel = ['🟢 0', '⚫ 28', '🔴 9', '⚫ 26', '🔴 30', '⚫ 11', '🔴 7', '⚫ 20', '🔴 32', '⚫ 17', '🔴 5', '⚫ 22', '🔴 34', '⚫ 15', '🔴 3', '⚫ 24', '🔴 36', '⚫ 13', '🔴 1', '🟢 00', '🔴 27', '⚫ 10', '🔴 25', '⚫ 29', '🔴 12', '⚫ 8', '🔴 19', '⚫ 31', '🔴 18', '⚫ 6', '🔴 21', '⚫ 33', '🔴 16', '⚫ 4', '🔴 23', '⚫ 35', '🔴 14', '⚫ 2', '🟢 0', '⚫ 28', '🔴 9', '⚫ 26', '🔴 30', '⚫ 11', '🔴 7', '⚫ 20', '🔴 32', '⚫ 17', '🔴 5', '⚫ 22', '🔴 34', '⚫ 15', '🔴 3', '⚫ 24', '🔴 36', '⚫ 13', '🔴 1', '🟢 00', '🔴 27', '⚫ 10', '🔴 25', '⚫ 29', '🔴 12', '⚫ 8', '🔴 19', '⚫ 31', '🔴 18', '⚫ 6', '🔴 21', '⚫ 33', '🔴 16', '⚫ 4', '🔴 23', '⚫ 35', '🔴 14', '⚫ 2']



	def createTable(self):
		l = []
		for n in rt:
			l.append(RouletteNumber(n[0], n[1], n[2], n[3], n[4], n[5]))

		return l

	async def randomNumber(self):
		return choice(self.chart)

	async def getNumber(self, num):
		for n in self.chart:
			if n.number == num:
				return n

		return 0

	async def getWheelPart(self, num):
		for i in range(len(self.wheel)):
			if self.wheel[i][2:] == num:
				idx = i
				break

		history = self.wheel[:5]
		history.reverse()
		for i in range(5, len(self.wheel)):
			history.pop()
			history.insert(0, self.wheel[i])

			if self.wheel[i][2:] == str(num):
				return list(reversed(history))


class CasinoCog(commands.Cog):
	"""Commands relating to minigames that use CowCoins."""

	def __init__(self, bot):
		self.bot = bot
		self.economy = self.bot.get_cog("EconCog")
		self.rTable = RouletteTable()
	


	@commands.command(name='coinflip', aliases=['cf', 'flip'])
	async def coinflip(self, ctx, wager, side):
		try:
			wager = abs(int(wager))
		except ValueError:
			await ctx.send("Wager must be a number")
			return

		async with self.bot.db.acquire() as conn:
			await self.economy.ensureAccount(ctx, ctx.author.id, conn)

			if not await self.economy.checkValue(ctx.author.id, wager, conn):
				await ctx.send('You do not have that much in your account!')
				return

			if side not in {"heads", "tails", 't', 'h'}:
				await ctx.send("Invalid side, valid options are \"heads\", \"tails\", \"t\", or \"h\"")
				return

			async with conn.transaction():
				await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", ctx.author.id, wager, 1, datetime.datetime.now(), "Coinflip wager")

				flipMap = ["Tails", "Heads"]
				headsFlipped = randint(0, 1)

				results = f"And the result is... {flipMap[headsFlipped]}!\n"
				
				if (side.lower() in {"heads", "h"} and headsFlipped) or (side.lower() in {"tails", "t"} and not headsFlipped):

					payout = int(wager * 1.5)
					await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, payout, ctx.author.id, datetime.datetime.now(), "Coinflip payout")

					results += f"Congrats, you won {payout:,d}!"

				else:
					results += f"Better luck next time!"
					won = False

				await ctx.send(results)

			await self.economy.updateAccounts([ctx.author.id], conn)


	@commands.command(name='roulette', aliases=['r', 'spin'])
	async def roulette(self, ctx, wager, bet, num=None):
		try:
			wager = abs(int(wager))
		except ValueError:
			await ctx.send("Wager must be a number")
			return

		if num != None:
			num = int(num)
		bet = bet.lower()
		if bet not in {"red", "black", "odd", "even", "high", "low", "column", "dozen", "straight"}:
			await ctx.send("Invalid bet for roulette")
			return

		if bet in {"column", "dozen"} and num not in range(1, 4):
			await ctx.send("That type of bet requires a number (1-3)")
			return

		if bet == "straight" and num not in range(1, 37):
			await ctx.send("Straight bets require you to pick a number (1-36)")
			return


		async with self.bot.db.acquire() as conn:
			await self.economy.ensureAccount(ctx, ctx.author.id, conn)

			if not await self.economy.checkValue(ctx.author.id, wager, conn):
				await ctx.send('You do not have that much in your account!')
				return

			async with conn.transaction():
				await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", ctx.author.id, wager, 1, datetime.datetime.now(), "Roulette wager")


				number = await self.rTable.randomNumber()

				won = True
				if number.column == 0:
					payout = 0
					resultsStr = "Sorry, nobody wins!"
					won = False
				elif bet in {"red", "black"} and bet == number.color:
					payout = int(wager * 1.5)
					resultsStr = f"Congrats, you won {payout:,d}!"
				elif bet in {"odd", "even"} and bet == number.OE:
					payout = int(wager * 1.5)
					resultsStr = f"Congrats, you won {payout:,d}!"
				elif bet in {"high", "low"} and bet == number.HL:
					payout = int(wager * 1.5)
					resultsStr = f"Congrats, you won {payout:,d}!"
				elif bet == "column" and num == number.column:
					payout = int(wager * 2.5)
					resultsStr = f"Congrats, you won {payout:,d}!"
				elif bet == "dozen" and num == number.dozen:
					payout = int(wager * 2.5)
					resultsStr = f"Congrats, you won {payout:,d}!"
				elif bet == "straight" and num == number.number:
					payout = wager * 35
					resultsStr = f"Congrats, you won {payout:,d}!"
				else:
					payout = 0
					resultsStr = "You didn't win, better luck next time"
					won = False

				if won:
					await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, payout, ctx.author.id, datetime.datetime.now(), "Roulette payout")

			await self.economy.updateAccounts([ctx.author.id], conn)
		
		msg = await ctx.send("Spinning the wheel... ")

		editNums = await self.rTable.getWheelPart(str(number.number))
		for n in editNums:
			await asyncio.sleep(.5)
			await msg.edit(content=f"{msg.content[:21]} **{n}**")

		await msg.edit(content=msg.content + f'\n{resultsStr}')




	@commands.command(name='maketable', aliases=['mt'])
	async def maketable(self, ctx, game, tablename, minimumBet=0):
		game = game.lower()
		if game not in tableTypes:
			await ctx.send("Invalid game type")
			return

		async with self.bot.db.acquire() as conn:
			if await conn.fetchrow("SELECT * FROM economy.tables WHERE dealer = $1 AND game = $2", ctx.author.id, game):
				await ctx.send("You already have an open table for that game!")
				return

			if len(tablename) > 32:
				await ctx.send("Table name is too long")
				return

			tablename = tablename.lower()

			if await conn.fetchrow("SELECT * FROM economy.tables WHERE tablename = $1", tablename):
				await ctx.send("There is already a table with that name")
				return

			try:
				minimumBet = int(minimumBet)
			except ValueError:
				await ctx.send("Minimum bet must be a number")
				return

			await conn.execute("INSERT INTO economy.tables (tablename, game, dealer, created, minimum_bet) VALUES ($1, $2, $3, $4, $5);", tablename, game, ctx.author.id, datetime.datetime.now(), minimumBet)


		await ctx.send(f"**{ctx.author.name}** created a {game} table named **{tablename}** with a minimum bet of **{minimumBet:,d}**")

	@commands.command(name='placebet', aliases=['pb'])
	async def placebet(self, ctx, tablename, *betTypes):
		tablename = tablename.lower()
		async with self.bot.db.acquire() as conn:
			table = await conn.fetchrow("SELECT * FROM economy.tables WHERE tablename = $1", tablename)
			if not table:
				await ctx.send("There are no tables with that name")
				return

			await self.economy.ensureAccount(ctx, ctx.author.id, conn)

			if table['game'] == "roulette":
				if len(betTypes) == 2:
					num = None
				elif len(betTypes) == 3:
					num = betTypes[2]
				else:
					await ctx.send("Incorrect number of arguments for placing a roulette bet")

				wager=betTypes[0]
				bet=betTypes[1]

				try:
					wager = abs(int(wager))
				except ValueError:
					await ctx.send("Wager must be a number")
					return

				if num != None:
					num = int(num)
				bet = bet.lower()
				if bet not in {"red", "black", "odd", "even", "high", "low", "column", "dozen", "straight"}:
					await ctx.send("Invalid bet for roulette")
					return

				if bet in {"column", "dozen"} and num not in range(1, 4):
					await ctx.send("That type of bet requires a number (1-3)")
					return

				if bet == "straight" and num not in range(1, 37):
					await ctx.send("Straight bets require you to pick a number (1-36)")
					return

				if wager < table['minimum_bet']:
					await ctx.send("Your wager is less than the minimum bet for that table")
					return

				if not await self.economy.checkValue(ctx.author.id, wager, conn):
					await ctx.send('You do not have that much in your account!')
					return

				if num != None:
					num = str(num)

				async with conn.transaction():
					await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", ctx.author.id, wager, 1, datetime.datetime.now(), "Roulette wager")
					await conn.execute("INSERT INTO economy.bets (bettor_id, amount, bet, tablename, game, modifier) VALUES ($1, $2, $3, $4, $5, $6);", ctx.author.id, wager, bet, tablename, table['game'], num)
				
				await self.economy.updateAccounts([ctx.author.id], conn)

				await ctx.send(f"Placed bet on table {tablename}")

			elif table['game'] == "coinflip":
				if len(betTypes) != 2:
					await ctx.send("Incorrect number of arguments for placing a coinflip bet")

				wager=betTypes[0]
				side=betTypes[1]

				try:
					wager = abs(int(wager))
				except ValueError:
					await ctx.send("Wager must be a number")
					return

				if wager < table['minimum_bet']:
					await ctx.send("Your wager is less than the minimum bet for that table")
					return

				await self.economy.updateAccounts([ctx.author.id], conn)
				
				if not await self.economy.checkValue(ctx.author.id, wager, conn):
					await ctx.send('You do not have that much in your account!')
					return

				if side not in {"heads", "tails", 't', 'h'}:
					await ctx.send("Invalid side, valid options are \"heads\", \"tails\", \"t\", or \"h\"")
					return

				async with conn.transaction():
					await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", ctx.author.id, wager, 1, datetime.datetime.now(), "Coinflip wager")
					await conn.execute("INSERT INTO economy.bets (bettor_id, amount, bet, tablename, game, modifier) VALUES ($1, $2, $3, $4, $5, $6);", ctx.author.id, wager, side, tablename, table['game'], None)
				
				await self.economy.updateAccounts([ctx.author.id], conn)
				
				await ctx.send(f"Placed bet on table {tablename}")

	@commands.command(name='play')
	async def play(self, ctx, tablename):
		tablename = tablename.lower()
		async with self.bot.db.acquire() as conn:
			table = await conn.fetchrow("SELECT * FROM economy.tables WHERE tablename = $1", tablename)
			if not table:
				await ctx.send("There are no tables with that name")
				return
			if table['dealer'] != ctx.author.id:
				await ctx.send("You're not the dealer for that table!")
				return


			players = await conn.fetch("SELECT * FROM economy.bets WHERE tablename = $1", tablename)

			if not players:
				await ctx.send("No bets made on that table, closing it...")
				await conn.execute("DELETE FROM economy.tables WHERE tablename = $1;", tablename)
				return

			pot = sum(s['amount'] for s in players)
			names = {}
			payouts = {}
			winners = False
			if table['game'] == 'coinflip':
				edit = False
				v = 100
				flipMap = ["Tails", "Heads"]
				headsFlipped = randint(0, 1)

				results = f"And the result is... {flipMap[headsFlipped]}!\n"

				async with conn.transaction():
					for p in players:
						side = p['bet']
						wager = p['amount']
						member = self.bot.get_user(p['bettor_id'])
						if member == None:
							userT = ("Not Found", 1)
						else:
							userT = (member.name, member.id)

						payout = 0
						if (side.lower() in {"heads", "h"} and headsFlipped) or (side.lower() in {"tails", "t"} and not headsFlipped):
							
							payout = int(wager * 1.7) + wager

						try:
							payouts[userT] -= wager
						except KeyError:
							payouts[userT] = wager * -1

						payouts[userT] += payout
						if payout > 0:
							winners = True
							await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, payout, member.id, datetime.datetime.now(), "Coinflip payout")
				
						
			elif table['game'] == 'roulette':
				edit = True
				v = 50
				#number = await self.rTable.getNumber(28)
				number = await self.rTable.randomNumber()

				msg = await ctx.send("Spinning the wheel... ")

				editNums = await self.rTable.getWheelPart(str(number.number))
				for n in editNums:
					await asyncio.sleep(.5)
					await msg.edit(content=f"{msg.content[:21]} **{n}**\n")

				results = msg.content
				async with conn.transaction():
					for p in players:
						bet = p['bet']
						wager = p['amount']
						num = p['modifier']
						if p['modifier']:
							num = int(p['modifier'])
						
						member = self.bot.get_user(p['bettor_id'])
						if member == None:
							userT = ("Not Found", 1)
						else:
							userT = (member.name, member.id)

						won = True
						if number.column == 0:
							payout = 0
							won = False
						elif bet in {"red", "black"} and bet == number.color:
							payout = int(wager * 2) + wager
						elif bet in {"odd", "even"} and bet == number.OE:
							payout = int(wager * 2) + wager
						elif bet in {"high", "low"} and bet == number.HL:
							payout = int(wager * 2) + wager
						elif bet == "column" and num == number.column:
							payout = int(wager * 3) + wager
						elif bet == "dozen" and num == number.dozen:
							payout = int(wager * 3) + wager
						elif bet == "straight" and num == number.number:
							payout = wager * 35 + wager
						else:
							payout = 0
							won = False

						try:
							payouts[userT] -= wager
						except KeyError:
							payouts[userT] = wager * -1

						payouts[userT] += payout
						if won:
							winners = True
							await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, payout, member.id, datetime.datetime.now(), "Roulette payout")

			
			potPayouts = await genPotVals(len([s for s in payouts.values() if s >= 0]), v)
			
			if len(payouts) == 1 and len(potPayouts) == 1:
				potPayouts[0] = 0

			new_d = {str(key[0]): str(value) for key, value in payouts.items()}

			ml = max(len(s) for s in new_d.keys())
			tl = max(len(f"{int(s):,d}") for s in new_d.values())
			if potPayouts:
				nl = max(len(f"{int((s / 100) * pot):,d}") for s in potPayouts)
			else:
				nl = 0

			sorted_tuples = sorted(payouts.items(), key=lambda item: item[1], reverse=True)
			sortedPlayers = {k: v for k, v in sorted_tuples}
			embed = discord.Embed(title=results, colour=0xff8900)

			async with conn.transaction():
				winnerString = ""
				j = 0
				for i in sortedPlayers.items():
					try:
						potAward = int((potPayouts[j] / 100) * pot)
					except IndexError:
						potAward = 0
					
					if potAward:
						winnerString += f"**`{i[0][0]:{sp}<{ml}}{tb * 2}`**\uFEFF`{i[1]:{sp}>{tl},d} + {potAward:{sp}>{nl},d}`\n"
						await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, potAward, i[0][1], datetime.datetime.now(), "Cut of the Pot")
					else:
						winnerString += f"**`{i[0][0]:{sp}<{ml}}{tb * 2}`**\uFEFF`{i[1]:{sp}>{tl},d} + {potAward:{sp}^{nl},d}`\n"
					
					j += 1
				embed.add_field(name="__Results__\n", value=winnerString, inline=False)

				if edit:
					await msg.edit(content=None, embed=embed)
				else:
					await ctx.send(embed=embed)
			
				await conn.execute("DELETE FROM bets WHERE tablename = $1;", tablename)
				await conn.execute("DELETE FROM tables WHERE tablename = $1;", tablename)


			await self.economy.updateAccounts([c['bettor_id'] for c in players], conn)

	@commands.command(name='tables')
	async def tables(self, ctx, game=None):
		async with self.bot.db.acquire() as conn:
			if game != None:
				game = game.lower()
				if game not in tableTypes:
					await ctx.send("Invalid game type")
					return
				tables = await conn.fetch("SELECT * FROM economy.tables WHERE game = $1 ORDER BY created;",  game)
			else:
				tables = await conn.fetch("SELECT * FROM economy.tables ORDER BY created;")
					
			names = {}
			pots = []
			for p in tables:
				players = await conn.fetch("SELECT * FROM economy.bets WHERE tablename = $1 ORDER BY bettor_id, amount DESC;", p['tablename'])
				pot = 0
				if players:
					pot = sum(s['amount'] for s in players)
				pots.append(pot)
				dealer = self.bot.get_user(p['dealer'])
				if dealer == None:
					names[p['dealer']] = "Not Found"
				else:
					names[p['dealer']] = dealer.name


		if tables:
			ml = max(len(s) for s in names.values())
			tl = max(len(s['game']) for s in tables)
			nl = max(len(s['tablename']) for s in tables)
			bl = max(len(f"{s['minimum_bet']:,d}") for s in tables)
			cl = max(len(f"{s:,d}") for s in pots)

		tableString = ""
		i = 0
		for p in tables:
			name = names[p['dealer']]
			if p['minimum_bet']:
				if pots[i]:
					tableString += f"**`{name:{sp}<{ml}}{tb * 2}`**\uFEFF`{p['tablename']:{sp}<{nl}}{tb * 2}\uFEFF{p['game'].capitalize():{sp}<{tl}}{tb * 2}\uFEFF{p['minimum_bet']:{sp}>{bl},d}{tb * 2}\uFEFF{pots[i]:{sp}>{cl},d}`\n"
				else:
					tableString += f"**`{name:{sp}<{ml}}{tb * 2}`**\uFEFF`{p['tablename']:{sp}<{nl}}{tb * 2}\uFEFF{p['game'].capitalize():{sp}<{tl}}{tb * 2}\uFEFF{p['minimum_bet']:{sp}>{bl},d}{tb * 2}\uFEFF{pots[i]:{sp}^{cl},d}`\n"

			else:
				if pots[i]:
					tableString += f"**`{name:{sp}<{ml}}{tb * 2}`**\uFEFF`{p['tablename']:{sp}<{nl}}{tb * 2}\uFEFF{p['game'].capitalize():{sp}<{tl}}{tb * 2}\uFEFF{p['minimum_bet']:{sp}^{bl},d}{tb * 2}\uFEFF{pots[i]:{sp}>{cl},d}`\n"
				else:
					tableString += f"**`{name:{sp}<{ml}}{tb * 2}`**\uFEFF`{p['tablename']:{sp}<{nl}}{tb * 2}\uFEFF{p['game'].capitalize():{sp}<{tl}}{tb * 2}\uFEFF{p['minimum_bet']:{sp}^{bl},d}{tb * 2}\uFEFF{pots[i]:{sp}^{cl},d}`\n"

			i += 1
		embed = discord.Embed(title="Tables", description=tableString, colour=0xff8900)
		await ctx.send(embed=embed)


	@commands.command(name='table', aliases=['bets'])
	async def vtable(self, ctx, tablename, member=None):
		tablename = tablename.lower()
		async with self.bot.db.acquire() as conn:
			table = await conn.fetchrow("SELECT * FROM economy.tables WHERE tablename = $1;", tablename)
			if not table:
				await ctx.send("There are no tables with that name")
				return

			
			if member == None:
				players = await conn.fetch("SELECT * FROM economy.bets WHERE tablename = $1 AND bettor_id = $2 ORDER BY amount DESC;", tablename, ctx.author.id)
				perPage = 10
			elif member.lower() == "all":
				players = await conn.fetch("SELECT * FROM economy.bets WHERE tablename = $1 ORDER BY bettor_id, amount DESC;", tablename)
				perPage = 7
			else:
				try:
					user = await commands.UserConverter().convert(ctx, member)
				except commands.BadArgument:
					await ctx.send("User not found")
					return
				players = await conn.fetch("SELECT * FROM economy.bets WHERE tablename = $1 AND bettor_id = $2 ORDER BY amount DESC;", tablename, user.id)
				perPage = 10


		if not players:
			await ctx.send("No bets found")
			return

		dealer = self.bot.get_user(table['dealer'])
		if dealer == None:
			dname = "Not Found"
		else:
			dname = dealer.name


		pot = sum(s['amount'] for s in players)
		names = []
		wagers = []
		bets = []
		modifiers = []


		for p in players:
			player = self.bot.get_user(p['bettor_id'])
			if player == None:
				names.append("Not Found")
			else:
				names.append(player.name)

			bets.append(p["bet"].capitalize())
			wagers.append(p["amount"])

			if p["modifier"] == None:
				modifiers.append(' ')
			else:
				modifiers.append(str(p["modifier"]))


		ml = max(len(s) for s in names)
		tl = max(len(f"{s:,d}") for s in wagers)
		nl = max(len(s) for s in bets)
		bl = max(len(s) for s in modifiers)

		embeds = []
		i = 0
		while i < len(players):
			tableString = ""
			j = 0
			while j < perPage and i < len(players):						
				tableString += f"**`{names[i]:{sp}<{ml}}{tb * 2}`**\uFEFF`{int(wagers[i]):{sp}>{tl},d}{tb * 2}\uFEFF{bets[i].capitalize():{sp}^{nl}}{sp}\uFEFF{modifiers[i]:{sp}<{bl}}`\n"
				j += 1
				i += 1
			tableString += f"Total Bets: {len(players)}\n"
			tableString += f"Total Pot: {pot:,d}"
				
			embeds.append(discord.Embed(title=f"{dname}'s {table['game'].capitalize()} Table", description=tableString, colour=0xff8900))			

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
								], return_when=asyncio.FIRST_COMPLETED, timeout=31)
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




async def setup(bot):
	await bot.add_cog(CasinoCog(bot))