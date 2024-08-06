import enum
from random import *
from collections import deque
from typing import Type
import discord
import asyncio
import asyncpg
from discord.ext import commands
from discord.ext.commands import context
from discord.ext.commands.core import check
from discord.interactions import Interaction, InteractionResponse
from discord.message import Message
from discord.webhook.async_ import WebhookMessage
from resources import queries, helpers
from resources.games import *
import time
import datetime
from datetime import timezone, timedelta
from millify import millify, prettify

class HitButton(discord.ui.Button):
	def __init__(self):
		super().__init__(style=discord.ButtonStyle.green, label='Hit', row=0)

	async def callback(self, interaction: discord.Interaction):
		assert self.view is not None
		if self.view.table.players[self.view.table.currPlayer].id == interaction.user.id:
			asyncio.ensure_future(self.view.table.hitPlayer()) 

class StayButton(discord.ui.Button):
	def __init__(self):
		super().__init__(style=discord.ButtonStyle.blurple, label='Stay', row=0)

	async def callback(self, interaction: discord.Interaction):
		assert self.view is not None
		if self.view.table.players[self.view.table.currPlayer].id == interaction.user.id:
			asyncio.ensure_future(self.view.table.nextPlayer()) 

class DDButton(discord.ui.Button):
	def __init__(self):
		super().__init__(style=discord.ButtonStyle.secondary, label='Double Down', row=1)

	async def callback(self, interaction: discord.Interaction):
		assert self.view is not None
		if self.view.table.players[self.view.table.currPlayer].id == interaction.user.id:
			asyncio.ensure_future(self.view.table.doubleDown()) 

class JoinButton(discord.ui.Button):
	def __init__(self):
		super().__init__(style=discord.ButtonStyle.blurple, label='Join', row=0)

	async def callback(self, interaction: discord.Interaction):
		assert self.view is not None
		if not self.view.table.started:
			self.view.table.blocked = True
			asyncio.ensure_future(self.view.table.addPlayer(interaction.user)) 

class LeaveButton(discord.ui.Button):
	def __init__(self):
		super().__init__(style=discord.ButtonStyle.red, label='Leave', row=0)

	async def callback(self, interaction: discord.Interaction):
		assert self.view is not None
		if not self.view.table.started:
			asyncio.ensure_future(self.view.table.removePlayer(interaction.user))

class StartButton(discord.ui.Button):
	def __init__(self):
		super().__init__(style=discord.ButtonStyle.green, label='Start', row=0)

	async def callback(self, interaction: discord.Interaction):
		assert self.view is not None
		if self.view.table.players[self.view.table.currPlayer].id == interaction.user.id:
			if not self.view.table.blocked:
				asyncio.ensure_future(self.view.table.playRound())
			else:
				await self.view.table.ctx.send(content=f'{interaction.user.mention} Players are still entering bets', delete_after=3)
		else:
			await self.view.table.ctx.send(content=f'{interaction.user.mention} Only the host can start the game', delete_after=3)

class BetButton(discord.ui.Button):
	def __init__(self):
		super().__init__(style=discord.ButtonStyle.secondary, label='Change Bet', row=1)

	async def callback(self, interaction: discord.Interaction):
		assert self.view is not None
		self.view.table.blocked = True
		if interaction.user.id in [p.id for p in self.view.table.players] and self.view.table.getPlayer(interaction.user.id).wager != "-----" and not self.view.table.started:
			asyncio.ensure_future(self.view.table.getBet(interaction.user))
		else:
			self.view.table.blocked = False

class ViewBetButton(discord.ui.Button):
	def __init__(self):
		super().__init__(style=discord.ButtonStyle.secondary, label='View Bet', row=1)

	async def callback(self, interaction: discord.Interaction):
		assert self.view is not None
		if interaction.user.id in [p.id for p in self.view.table.players]:
			asyncio.ensure_future(self.view.table.displayBet(interaction.user, interaction))

class BlackjackInteraction(discord.ui.View):
	def __init__(self, table):
		super().__init__(timeout=600.0)
		self.value = None
		self.table: BlackjackTable = table

		self.add_item(StartButton())
		self.add_item(JoinButton())
		self.add_item(LeaveButton())
		self.add_item(BetButton())
		self.add_item(ViewBetButton())


	async def on_timeout(self):
		self.clear_items()
		await self.table.msg.edit(view=self)
		

class BJHand(Hand):
	def __init__(self, cards=None):
		super().__init__(cards)

	def calculateValue(self, addHidden=False):
		total = 0
		aces = []
		for card in self.cards:
			if card.hidden and not addHidden:
				continue
			elif card.rank.name != 'Ace':
				try:
					total += int(card.rank.value)
				except ValueError:
					total += 10
			else:
				aces.append(card)


		for ace in aces:
			if total > 10:
				total += 1
			else:
				if total + 11 + len(aces) - 1 > 21:
					total += 1
				else:
					total += 11
			
		return total

class BJPlayer(Player):
	def __init__(self, name, mention, id, hand=None, empty=False, wager=0, status = None):
		super().__init__(name, mention, id, hand, empty, wager, status)
		self.hand = hand or BJHand()
		self.originalWager = wager


		
class BJTable(Table):
	def __init__(self):
		super().__init__()
		self.emptySeat = BJPlayer('        ', 'NA', 'NA', empty=True)

class BlackjackTable:
	def __init__(self, ctx, economy, conn, deck=None, defaultBet=100):
		self.started = False
		self.blocked = False
		self.winners = ''
		self.playerCache = set()
		self.economy = economy
		self.conn = conn
		self.defaultBet = defaultBet
		self.view = None
		self.msg: discord.Message = None
		self.ctx = ctx
		self.deck = deck or Deck(count=6)
		self.currPlayer = 0
		self.dealer = BJPlayer('Dealer', 'Dealer', 1)
		self.table = BJTable()
		self.table.addPlayer(0, 0, self.dealer)
		self.players = [self.dealer]


	def getPlayer(self, id) -> BJPlayer:
		for p in self.players:
			if p.id == id:
				return p
		
		return None

	async def createTable(self):
		self.view = BlackjackInteraction(self)
		self.msg = await self.ctx.send(self.table.compileTable(not self.started), view=self.view)
		
		wager = None
		if self.ctx.args[-1] and (self.ctx.args[-1].isdecimal() or self.ctx.args[-1].lower() in {"all", "allin", "all-in", 'a'}):
			try:
				wager = int(self.ctx.args[-1])
			except ValueError:
				wager = self.ctx.args[-1]

		await self.addPlayer(self.ctx.author, wager=wager)
		await self.view.wait()
		return

	async def displayBet(self, user: discord.User, interaction: Interaction):
		player = self.getPlayer(user.id)
		try:
			betMsg: WebhookMessage = await interaction.followup.send(content=f"Your bet is {player.wager:,d} CC", ephemeral=True)
		except ValueError:
			pass

	async def adjustBet(self, player: BJPlayer):
		if type(player.wager) is int:
			accountBalance = await self.economy.getAccValue(self.ctx, player, self.conn)
			if player.wager > accountBalance:
				player.wager = accountBalance
				player.originalWager = accountBalance

	async def reset(self, winners):
		self.view.clear_items()
		for p in self.players:
			if p.id != 1:
				p.hand = BJHand()
				p.wager = p.originalWager
				self.playerCache.add(p)
		self.started = False
		
		if len(self.deck.cards) < ((self.deck.initialCount * 52) / 2):
			self.deck.rebuild()

		self.players = [self.players[0], self.dealer]
		self.players[0].wager = self.players[0].originalWager

		self.table = BJTable()
		self.table.addPlayer(0, 0, self.dealer)
		self.table.addPlayerInNextEmpty(self.players[0])
		await self.adjustBet(self.players[0])


		self.view.add_item(StartButton())
		self.view.add_item(JoinButton())
		self.view.add_item(LeaveButton())
		self.view.add_item(BetButton())
		self.view.add_item(ViewBetButton())
		
		oldMsg = self.msg
		self.msg = await self.ctx.send(f'{self.winners}{self.table.compileTable(not self.started)}', view=self.view)
		await oldMsg.delete()

	async def getBet(self, user, returnVal=False, provided=None, limit=None):
		await self.economy.ensureAccount(self.ctx, user.id, self.conn)
		
		def check(m: discord.Message):
			return m.author.id == user.id and (m.content.isdecimal() or m.content.lower() in {"all", "all in", "all-in", 'a'}) and m.channel == self.ctx.channel

		if not provided:
			try:
				prompt = await self.ctx.send(f'{user.mention} Enter bet')
				msg = await self.ctx.bot.wait_for('message', check=check, timeout=30)
				await prompt.delete()
				if msg.content.lower() in {"all", "allin", "all-in", 'a'}:
					bet = await self.economy.getAccValue(self.ctx, user, self.conn)
				else:
					bet = int(msg.content)
				try:
					await msg.delete()
				except discord.errors.NotFound:
					pass
			except asyncio.TimeoutError:
				await prompt.edit(f'{user.name} timed out waiting for bet', delete_after=3)
				return -2
		else:
			if str(provided).lower() in {"all", "allin", "all-in", 'a'}:
				bet = await self.economy.getAccValue(self.ctx, user, self.conn)
			else:
				bet = provided
			

		if not await self.economy.checkValue(user.id, bet, self.conn):
			await self.ctx.send(f'{user.mention} You do not have {bet} in your account', delete_after=3)
			return -1

		if limit and bet > limit:
			await self.ctx.send(f'{user.mention} You do not have {bet} in your account', delete_after=3)
			return -1


		if not returnVal:
			self.getPlayer(user.id).wager = bet
			self.getPlayer(user.id).originalWager = bet
			await self.msg.edit(content=f'{self.winners}{self.table.compileTable(not self.started)}')
			self.blocked = False
		else:
			return bet

	def searchCache(self, id) -> BJPlayer:
		for p in self.playerCache:
			if p.id == id:
				return p
		
		raise ValueError

	async def registerBets(self):
		conn = self.conn
		async with conn.transaction():
			for p in self.players:
				if p.id != 1:
					await self.adjustBet(p)
					await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", p.id, p.wager, 1, datetime.datetime.now(), "Blackjack wager")

	async def removePlayer(self, user):
		for i in range(len(self.players)):
			if self.players[i].id == user.id:
				self.players.pop(i)
				self.table.removePlayerByID(user.id)
				self.table.fillEmpty(protected=0)

				if len(self.players) == 3:
					self.table.swapPlayer(0, 1, 0, 0)

				break
		else:
			return
		
		if len(self.players) <= 1:
			await self.endTable()
		else:
			await self.msg.edit(content=f'{self.winners}{self.table.compileTable(not self.started)}')

	async def addPlayer(self, user, tableMax=6, wager=None):
		self.blocked = True
		if user.id not in [p.id for p in self.players] and len(self.players) - 1 < tableMax:
			try:
				newPlayer = self.searchCache(user.id)
				await self.adjustBet(newPlayer)
				inCache = True
			except ValueError:
				inCache = False
				newPlayer = BJPlayer(user.name, user.mention, user.id, wager="-----")
				
			self.players.insert(len(self.players) - 1, newPlayer)
		
			self.table.addPlayerInNextEmpty(newPlayer)

			if len(self.players) == 4:
				self.table.swapPlayer(0, 0, 0, 1)

			await self.msg.edit(content=f'{self.winners}{self.table.compileTable(not self.started)}')
			
			if not inCache and not wager:
				bet = await self.getBet(user, returnVal=True)
				breaker = 0
				while bet < 0 and breaker < 100:
					if bet == -2:
						await self.removePlayer(user)
						break
					else:
						bet = await self.getBet(user, returnVal=True)
					breaker += 1

				newPlayer.wager = bet
				newPlayer.originalWager = bet
				await self.msg.edit(content=f'{self.winners}{self.table.compileTable(not self.started)}')
			elif wager:
				await self.getBet(user, provided=wager)

			self.blocked = False

		elif len(self.players) - 1 < tableMax:
			self.table.blocked = False
			await self.ctx.send('Table is full', delete_after=3)
		else:
			self.table.blocked = False

	def hit(self):
		self.players[self.currPlayer].hand.addCard(self.deck.draw())

	async def hitPlayer(self):
		self.hit()
		if not self.checkScore():
			await self.nextPlayer()
		else:
			self.view.clear_items()
			self.view.add_item(HitButton())
			self.view.add_item(StayButton())
			await self.msg.edit(content=f"{self.players[self.currPlayer].mention}'s Turn\n{self.table.compileTable(not self.started)}", view=self.view)
		
	async def nextPlayer(self):
		self.currPlayer += 1
		if self.currPlayer != len(self.players) - 1: 
			if self.checkScore():
				self.view.clear_items()
				self.view.add_item(HitButton())
				self.view.add_item(StayButton())
				self.view.add_item(DDButton())
				oldMsg = self.msg
				self.msg = await self.ctx.send(f"{self.players[self.currPlayer].mention}'s Turn\n{self.table.compileTable(not self.started)}", view=self.view)
				await oldMsg.delete()
				asyncio.ensure_future(self.timePlayer())
			else:
				await self.nextPlayer()
		else:
			await self.endRound()

	def checkScore(self):
		if self.currPlayer != len(self.players) - 1:
			return self.players[self.currPlayer].hand.calculateValue() < 21
		else:
			return self.players[self.currPlayer].hand.calculateValue() < 17

	async def playRound(self):
		self.started = True
		self.view.clear_items()
		await self.registerBets()

		resend = True
		self.dealer.hand = BJHand()
		for i in range(2):
			for p in self.players:
				if p == self.dealer and i == 1:
					p.hand.addCard(self.deck.draw(hidden=True))
					break
				else:
					p.hand.addCard(self.deck.draw())

				if resend:
					resend = False
					oldMsg = self.msg
					self.msg = await self.ctx.send(f'{self.winners}Dealing Cards...\n{self.table.compileTable(self.started)}', view=self.view)
					await oldMsg.delete()
				else:
					await self.msg.edit(content=f'{self.winners}Dealing Cards...\n{self.table.compileTable(self.started)}')
				
				await asyncio.sleep(1)

		self.currPlayer = -1
		await self.nextPlayer()

		# oldMsg = self.msg
		# self.msg = await self.ctx.send(f'{self.winners}{self.table.compileTable(not self.started)}', view=self.view)
		# await oldMsg.delete()
		# asyncio.ensure_future(self.timePlayer())

	async def timePlayer(self):
		currTurn = self.currPlayer
		for i in range(90):
			if self.currPlayer == currTurn:
				await asyncio.sleep(.5)
			else:
				break
		else:
			await self.nextPlayer()

	async def doubleDown(self):
		player = self.players[self.currPlayer]
		accBal = await self.economy.getAccValue(self.ctx, player, self.conn)
		if not accBal:
			await self.ctx.send(f"{player.mention} You have no money to double down with (lol poor)", delete_after=3)
			return
		
		newWager = player.wager
		if newWager > accBal:
			newWager = accBal
		
		await self.conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", player.id, newWager, 1, datetime.datetime.now(), "Blackjack Double Down")
		player.wager += newWager

		await self.ctx.send(f"{player.mention} doubled down", delete_after=3)

		self.hit()
		await self.msg.edit(content=f"{player.mention}'s Turn\n{self.table.compileTable(not self.started)}")

		await self.nextPlayer()


	async def endTable(self):
		self.currPlayer = -1
		self.view.clear_items()
		self.view.stop()
		await self.msg.edit(content=f'{self.winners}{self.table.compileTable(not self.started)}', view=self.view)

	async def endRound(self):
		self.view.clear_items()

		self.currPlayer = len(self.players) - 1
		self.dealer.hand.unhide(1)
		await self.msg.edit(content=f"{self.players[self.currPlayer].mention}'s Turn\n{self.table.compileTable(not self.started)}", view=self.view)
		while self.checkScore():
			self.hit()
			await asyncio.sleep(1)
			await self.msg.edit(content=f"{self.players[self.currPlayer].mention}'s Turn\n{self.table.compileTable(not self.started)}")

		self.currPlayer += 1

		winners = []
		for i in range(len(self.players) - 1):
			player = self.players[i]
			playerScore = player.hand.calculateValue()
			dealerScore = self.dealer.hand.calculateValue()
			winner = True
			if dealerScore > 21:
				if playerScore == 21:
					payout = int(player.wager * 1.5) + player.wager
				elif playerScore < 21:
					payout = int(player.wager * 2)
				else: 
					winner = False
			else:
				if playerScore == dealerScore:
					payout = int(player.wager)
				elif playerScore < 21 and playerScore > dealerScore:
					payout = int(player.wager * 2)
				elif playerScore == 21 and playerScore > dealerScore:
					payout = int(player.wager * 1.5) + player.wager
				else:
					winner = False
			
			if winner:		
				await self.conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, payout, player.id, datetime.datetime.now(), "Blackjack payout")
				winners.append(f"{player.mention} ({payout:,d})")
		
		await self.economy.updateAccounts([u.id for u in self.players if u.id != 1], self.conn)
		self.winners = f"{' '.join(winners) or 'Dealer'} won!\n"
		await self.msg.edit(content=f'{self.winners}{self.table.compileTable(not self.started)}', view=self.view)
		
		await asyncio.sleep(1)
		self.currPlayer = 0

		await self.reset(winners)

class CardgameCog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.economy = self.bot.get_cog("EconCog")

	
	@commands.command(name='blackjack', aliases=['bj'])
	async def blackjack(self, ctx, wager=None):
		async with self.bot.db.acquire() as conn:
			t = BlackjackTable(ctx, self.economy, conn)
			await t.createTable()


async def setup(bot):
	await bot.add_cog(CardgameCog(bot))
