import discord
import asyncio
import asyncpg
from discord.ext import commands
from resources import helpers, queries
import random

class GamesCog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.lock = asyncio.Lock()
		self.reactionLock = asyncio.Lock()
		self.winner = None
		self.gameMsg = None
		self.target = None
		self.missed = set()
		self.losers = set()
		self.emotes = []
	@commands.command(name='shootingrange', aliases = ['asr'])
	async def shootingGallery(self, ctx):
		if self.gameMsg:
			return

		async with self.lock:
			unused = [random.choice(ctx.guild.emojis) for i in range(20)]
			self.emotes = list(unused)
			self.target = random.choice(unused)
			unused.append(self.target)
			
			random.shuffle(unused)
			used = []
			spins = 0

			self.gameMsg = await ctx.send(str(self.target))
			self.gameLive = True
			while not self.winner and spins < 200:
				if (len(used) > 1 and random.randint(1, 100) >= 60) or len(used) == 20:
					emote = random.choice(used)
					if self.winner: break
					await self.gameMsg.clear_reaction(emote)
					if self.winner: break
					used.remove(emote)
					unused.append(emote)
				elif unused:
					emote = random.choice(unused)
					unused.remove(emote)
					if self.winner: break
					await self.gameMsg.add_reaction(emote)
					if self.winner: break
					used.append(emote)
				else:
					await asyncio.sleep(.5)

				spins += 1

			if self.winner:
				await self.gameMsg.edit(content=f"{self.gameMsg.content}\n{self.winner.display_name} has won!")
			else:
				await self.gameMsg.edit(content=f"{self.gameMsg.content}\nGame Over!")

			self.gameMsg = None
			self.winner = None
			self.losers.clear()
			self.missed.clear()
			self.emotes = []



	@commands.Cog.listener()
	async def on_reaction_add(self, reaction, user):
		if user == self.bot.user:
			return

		if self.gameMsg and reaction.message == self.gameMsg:
			if self.winner == None:
				if user not in self.losers and reaction.emoji == self.target and self.bot.user in await reaction.users().flatten():
					async with self.reactionLock:
						if self.winner == None:
							self.winner = user
				elif user not in self.missed:
					self.missed.add(user)
					if reaction.emoji not in self.emotes:
						await self.gameMsg.clear_reaction(reaction.emoji)
					await reaction.message.channel.send(f"{user} missed!")
				elif user not in self.losers:
					self.losers.add(user)
					if reaction.emoji not in self.emotes:
						await self.gameMsg.clear_reaction(reaction.emoji)
					await reaction.message.channel.send(f"{user} lost!")
				
				

async def setup(bot):
	await bot.add_cog(GamesCog(bot))
