import discord
import asyncio
import asyncpg
from discord.ext import commands
from discord import app_commands
from enum import Enum
import time
from datetime import timezone, timedelta, datetime
from discord.ext.commands.cooldowns import BucketType
import pytz
import hashlib
import random
from requests.api import delete
import requests
import json
from resources import queries, helpers
import pickle

cutoffTime = 0


abbreviations = {'ATL': 'Atlanta Reign', 'BOS': 'Boston Uprising','CDH': 'Chengdu Hunters', 'DAL': 'Dallas Fuel', 'FLA': 'Florida Mayhem', 'GZC': 'Guangzhou Charge','HZS': 'Hangzhou Spark', 'HOU': 'Houston Outlaws', 'LDN': 'London Spitfire', 'GLA': 'Los Angeles Gladiators', 'VAL': 'Los Angeles Valiant', 'NYE': 'New York Excelsior', 'SFS': 'San Francisco Shock', 'DYN': 'Seoul Dynasty', 'INF': 'Seoul Infernal', 'SHD': 'Shanghai Dragons', 'TOR': 'Toronto Defiant', 'LVE': 'Vegas Eternal', 'VAN': 'Vancouver Titans', 'WAS': 'Washington Justice', 'PHI': 'Philadelphia Fusion', 'PAR': 'Paris Eternal', 'DRM': 'Dreamers', 'RHO': 'Rhodes', 'PAN': 'PANTHERA', 'O2B': 'O2 Blast', 'SPG': 'Sin Prisa Gaming', 'PKF': 'Poker Face'}
customAbbreviations = {'atl': 'ATL', 'atlanta': 'ATL', 'reign': 'ATL', 'rain': 'ATL', 'bos': 'BOS', 'boston': 'BOS',
		       'uprising': 'BOS', 'cdh': 'CDH', 'chengdu': 'CDH', 'hunters': 'CDH', 'dal': 'DAL', 'fuel': 'DAL',
			   'dallas': 'DAL', 'df': 'DAL', 'optic': 'DAL','fla': 'FLA', 'florida': 'FLA', 'mayhem': 'FLA',
			   'flm': 'FLA','gzc': 'GZC', 'guangzhou': 'GZC', 'charge': 'GZC', 'herbalife': 'GZC', 'hzs': 'HZS',
			   'hangzhou': 'HZS', 'spark': 'HZS', 'hou': 'HOU', 'houston': 'HOU', 'outlaws': 'HOU', 'ldn': 'LDN',
			   'london': 'LDN', 'spitfire': 'LDN', 'gla': 'GLA', 'lag': 'GLA', 'gladiators': 'GLA', 'glads': 'GLA',
			   'val': 'VAL', 'lav': 'VAL', 'valiant': 'VAL', 'nye': 'NYE', 'nyc': 'NYE', 'nyxl': 'NYE', 'ny': 'NYE',
			   'excelsior': 'NYE', 'sfs': 'SFS', 'sf': 'SFS', 'shock': 'SFS', 'dyn': 'DYN', 'dynasty': 'DYN', 'seo':
			   'DYN','seoul dyn': 'DYN','inf': 'INF', 'seoul inf': 'INF', 'infernal': 'INF', 'sin': 'INF','phi': 'INF',
			   'shd': 'SHD', 'shanghai': 'SHD', 'dragons': 'SHD', 'tor': 'TOR', 'toronto': 'TOR', 'defiant': 'TOR',
			   'at': 'TOR','van': 'VAN', 'vancouver': 'VAN', 'titans': 'VAN', 'lve': 'LVE', 'lv': 'LVE', 'veg': 'LVE',
			   'vegas': 'LVE', 'eternal': 'LVE','par': 'LVE', 'was': 'WAS', 'dc': 'WAS', 'washington': 'WAS',
			   'justice': 'WAS', 'drm': 'DRM', 'dream': 'DRM', 'dreamers': 'DRM', 'o2': 'O2B', 'blast': 'O2B', 
			   'o2b': 'O2B', 'sin': 'SPG', 'spg': 'SPG', 'prisa': 'SPG', 'sinprisa': 'SPG', 'rho': 'RHO', 'pan':'PAN', 'pkf': 'PKF', 'poker': 'PKF'}

# Add whatever to these, we can be generous with aliasing as long as they aren't confusing or ambiguous
abbrevs = {'ATL', 'BOS', 'CDH', 'DAL', 'FLA', 'GZC', 'HZS', 'HOU', 'LDN', 'GLA', 'VAL', 'NYE', 'SFS','DYN','INF','SHD', 'TOR', 'VAN', 'LVE','WAS', 'PAR', 'PHI', 'DRM', 'RHO', 'PAN', 'O2B', 'SPG','PKF'}
shortNames =  {'Dallas Fuel': 'Dallas Fuel', 'Philadelphia Fusion': 'Philly Fusion', 'Houston Outlaws': 'Houston Outlaws', 'Boston Uprising': 'Boston Uprising', 'New York Excelsior': 'NY Excelsior', 'San Francisco Shock': 'SF Shock', 'Los Angeles Valiant': 'LA Valiant', 'Los Angeles Gladiators': 'LA Gladiators', 'Florida Mayhem': 'Florida Mayhem', 'Shanghai Dragons': 'Shanghai Dragons', 'Seoul Dynasty': 'Seoul Dynasty', 'London Spitfire': 'London Spitfire', 'Chengdu Hunters': 'Chengdu Hunters', 'Hangzhou Spark': 'Hangzhou Spark', 'Paris Eternal': 'Paris Eternal', 'Toronto Defiant': 'Toronto Defiant', 'Vancouver Titans': 'Vancouver Titans', 'Washington Justice': 'Washington Justice', 'Atlanta Reign': 'Atlanta Reign', 'Guangzhou Charge': 'Guangzhou Charge', "Seoul Infernal": "Seoul Infernal", 'Vegas Eternal': 'Vegas Eternal', 'Dreamers':'Dreamers', 'Poker Face': 'Poker Face', 'PANTHERA': 'PANTHERA', 'O2 Blast': 'O2 Blast', 'Sin Prisa Gaming': 'Sin Prisa'}

sp = '\U0000202F'
tb = '\U00002001'

class PredictionsCog(commands.Cog):
	""" Commands relating to Predictions about the Overwatch League"""
	def __init__(self, bot):
		self.bot = bot
		self.stock = self.bot.get_cog("StockCog")
		self.cutoff = 0
		self.monitored: set = set()
		self.matches: set = set()
		self.timedOutUsers: set = set()



	async def cooldownUser(self, user_id):
		self.timedOutUsers.add(user_id)
		await asyncio.sleep(15)
		self.timedOutUsers.discard(user_id)


	class Match:
		def __init__(self, bot, matchObj, htreact: discord.reaction.Reaction, atreact: discord.reaction.Reaction, msg: discord.message.Message):
			self.bot = bot
			self.matchObj = matchObj
			self.htreact = htreact
			self.atreact = atreact
			self.msg = msg

		async def addPred(self, user, conn):
			self.msg = await self.msg.channel.fetch_message(self.msg.id)
			choseHT = False
			choseAT = False
			homereact = None
			awayreact = None
			htr = [u async for u in self.htreact.users()]
			if user == htr[0].id:
				homereact = htr[0]
			if homereact != None:
				choseHT = True

			atr = [u async for u in self.atreact.users()]
			if user == atr[0].id:
				awayreact = atr[0]
			if awayreact != None:
				choseAT = True

			
			if choseHT and choseAT:
				value = 0
			elif choseHT:
				winner = self.matchObj["htshort"]
				loser = self.matchObj["atshort"]
				value = 1
			elif choseAT:
				winner = self.matchObj["atshort"]
				loser = self.matchObj["htshort"]
				value = 1
			else:
				value = 0
			
			if value == 1:
				stocks = await conn.fetch("SELECT teamshort, currentprice, updatedprice, highprice, lowprice, ticker FROM economy.market WHERE teamshort=$1 OR teamshort=$2", winner, loser)
				percent = (0.15 * 0.01)
				await self.stock.insertMarket(conn, stocks, winner, loser, percent, "Prediction")
				await conn.execute("DELETE FROM athena.predictions WHERE user_id = $1 AND match_id = $2;", user, self.matchObj["id"])
				await conn.execute("INSERT INTO athena.predictions (user_id, winner, winner_score, loser, loser_score, match_id) VALUES ($1, $2, $3, $4, $5, $6);", user, winner, None, loser, None, self.matchObj["id"])
			return value
	class CustomAbb(commands.Converter):
		async def convert(self, ctx, teamAbb):
			try:
				team = customAbbreviations[teamAbb.lower()]
			except KeyError:
				team = teamAbb.lower()
			except AttributeError:
				team = teamAbb.lower()
			if team in abbrevs:
				return team
			else:
				raise commands.BadArgument

	class shortNames(commands.Converter):
		async def convert(self, ctx, teamName):
			try:
				return shortNames[teamName]
			except KeyError:
				return teamName
			except AttributeError:
				return teamName


	@commands.hybrid_command(name='predall', aliases=['pa', 'predictall'])
	@commands.has_permissions(ban_members=True)
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def predall(self, ctx: commands.context, day: int=None):
		"""
		Shows matches for a gameday, and allows you to make quick win-lose predictions.
		~predall [day(optional)]
		ALT: pa/predictall

		Shows the matches for the specified gameday in the current matchweek, allowing you to make predictions on which team wins via emotes that appear. 
		To make a prediction, select the teams you predict will win and select the green checkmark emote. Not specifying the day brings up the next gameday by default.
		EXAMPLE: ~predall 2
		"""
		if len(self.monitored) >= 5:
			await ctx.send("There are already several messages tracking reactions, please use one of them or wait a bit and try again", delete_after=5)
			return

		

		cutoff = datetime.now() + timedelta(minutes=cutoffTime)
		
		async with self.bot.db.acquire() as conn:
			matches = await conn.fetch(queries.UPCOMINGMATCHESINWEEK, int(cutoff.timestamp() * 1000))
		if not matches:
			await ctx.send("Matchweek has ended! Come back tomorrow to enter predictions for the next week")
			return

		indexes = set([m["rank"] for m in matches])



		if day == None:
			day = min(indexes)

		day = int(day)
		if day not in indexes:
			await ctx.send("Invalid day", delete_after=3)
			return


		tempembed = discord.Embed(title=f"{matches[0]['startdate'].strftime('%A, %B %e')} - Day {day} of {max(indexes)}", description="Loading...", colour=0x494949)
		msg = await ctx.send(embed=tempembed)
		self.monitored.add(msg.id)

		daystring = ""
		teams = []
		teamNames = []
		dayStamp=""
		# Remove channel reaction perms for everyone before doing this
		for m in matches:
			if m["rank"] == day:
				dayStamp = m["startdate"]
				if m["htshort"] not in teamNames:
					htlogo = m["htshort"]
				else:
					htlogo = m["htshort"] + '2'

				teamNames.append(htlogo)
				htlogoObj = discord.utils.get(self.bot.emojis, name=htlogo)
				teams.append(htlogoObj)


				if m["atshort"] not in teamNames:
					atlogo = m["atshort"]
				else:
					atlogo = m["atshort"] + '2'

				teamNames.append(atlogo)
				atlogoObj = discord.utils.get(self.bot.emojis, name=atlogo)
				teams.append(atlogoObj)

				#local
				#times =  pytz.timezone("US/Eastern").fromutc(m["startdate"]).strftime("%#I:%M %p %Z") + " / " +  (m["startdate"].strftime("%#I:%M %p UTC"))
				
				#prod
				times =  pytz.timezone("US/Eastern").fromutc(m["startdate"]).strftime("%-I:%M %p %Z") + " / " +  (m["startdate"].strftime("%-I:%M %p UTC"))

				logo1 = discord.utils.get(self.bot.emojis, name=m["htshort"])
				logo2 = discord.utils.get(self.bot.emojis, name=m["atshort"])
				if logo1 == None:
						logo1 = discord.utils.get(self.bot.emojis, name="OWC")

				if logo2 == None:
					logo2 = discord.utils.get(self.bot.emojis, name="OWC")

				daystring += f"*{times}*\n{logo1} **{m['htname']}** vs **{m['atname']}** {logo2}\n\n"
				await msg.add_reaction(htlogoObj)
				await msg.add_reaction(atlogoObj)
				msg = await ctx.fetch_message(msg.id)
				self.matches.add(self.Match(self.bot, m, discord.utils.get(msg.reactions, emoji=htlogoObj), discord.utils.get(msg.reactions, emoji=atlogoObj), msg))

		embed = discord.Embed(title=f"{dayStamp.strftime('%A, %B %e')} - Day {day} of {max(indexes)}", description=daystring, colour=0xff8900)
		await msg.edit(embed=embed)

		await msg.add_reaction("\U00002705") # Checkmark
		# Restore perms here

		await asyncio.sleep(120)
		self.monitored.discard(msg.id)
		rmset = set()
		for m in self.matches:
			if m.msg.id == msg.id:
				rmset.add(m)
		self.matches -= rmset
		await msg.clear_reactions()


	@commands.hybrid_command(name='pred', aliases=['p', 'predict'])
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def pred(self, ctx: commands.context, team1: str, score: str, team2: str=None):
		"""
		Make detailed map predictions
		~pred [team1] [team1_score]-[team2_score] [team2]
		ALT: p/predict
		Allows you to specify the map wins for a match in the current matchweek. 
		The command accepts full team names, common abbreviations, single words from team names, and single word city names.
		You can also randomize your score by using "random" as a score keyword

		EXAMPLES: 
		~pred fuel 3-0 gla
		~pred dal 1-3
		~pred sfs random van
		"""
		t1 = team1
		t2 = team2
		try:
			t1 = await PredictionsCog.CustomAbb().convert(ctx, t1)
		except commands.BadArgument:
			await ctx.send("Invalid team!", delete_after=5)
			return
		if t2 != None:
			try:
				t2 = await PredictionsCog.CustomAbb().convert(ctx, t2)
			except commands.BadArgument:
				await ctx.send("Invalid team!", delete_after=5)
				return

		if score == 'random':
			loserScore = random.randint(0,2)
			scores = [3, loserScore]
			score = f'3-{loserScore}'
		else:
			scores = [int(score[0]), int(score[2])]

	
		r = range(0,5)
		if (scores[0] not in r or scores[1] not in r) or (scores[0] == scores[1]) or (max(scores) not in {3,4}):
			await ctx.send(f"{ctx.author.mention} Invalid map score!", delete_after=5)
			return

		if scores[0] > scores[1]:
			winner = t1
			winnerScore = scores[0]
			loser = t2
			loserScore = scores[1]
		else:
			winner = t2
			winnerScore = scores[1]
			loser = t1
			loserScore = scores[0]
		async with self.bot.db.acquire() as conn:
			timeobj = datetime.utcnow() + timedelta(minutes=cutoffTime)
			matches = await conn.fetch(queries.UPCOMINGMATCHESINWEEK, int(timeobj.timestamp() * 1000))
			stocks = await conn.fetch("SELECT teamshort, currentprice, updatedprice, highprice, lowprice, ticker FROM economy.market ORDER BY teamshort;")
			match loserScore:
				case 0:
					percent = (0.25 * 0.01)
				case 1:
					percent = (0.20* 0.01) 
				case 2:
					percent = (0.15 * 0.01)

			async with conn.transaction():
				for m in matches:
					if t2 == None:
						if t1 in {m['htshort'], m['atshort']}:
							if winner == None:
								if loser == m['htshort']:
									winner = m['atshort']
								else:
									winner = m['htshort']
							else:
								if winner == m['htshort']:
									loser = m['atshort']
								else:
									loser = m['htshort']
							await self.stock.insertMarket(conn, stocks, winner, loser, percent, "Prediction")
							await conn.execute("DELETE FROM athena.predictions WHERE user_id = $1 AND match_id = $2;", ctx.author.id, m["id"])
							await conn.execute("INSERT INTO athena.predictions (user_id, winner, winner_score, loser, loser_score, match_id) VALUES ($1, $2, $3, $4, $5, $6);", ctx.author.id, winner, winnerScore, loser, loserScore, m["id"])
							await ctx.send(f"{ctx.author.mention} predicted the {abbreviations[winner]} to defeat the {abbreviations[loser]} {max(scores)}-{min(scores)}", delete_after=7)
							break
					else:
						if {t1, t2} <= {m['htshort'], m['atshort']}:
							await self.stock.insertMarket(conn, stocks, winner, loser, percent, "Prediction")
							await conn.execute("DELETE FROM athena.predictions WHERE user_id = $1 AND match_id = $2;", ctx.author.id, m["id"])
							await conn.execute("INSERT INTO athena.predictions (user_id, winner, winner_score, loser, loser_score, match_id) VALUES ($1, $2, $3, $4, $5, $6);", ctx.author.id, winner, winnerScore, loser, loserScore, m["id"])
							await ctx.send(f"{ctx.author.mention} predicted the {abbreviations[winner]} to defeat the {abbreviations[loser]} {max(scores)}-{min(scores)}", delete_after=7)
							break
				else:
					await ctx.send(f"{ctx.author.mention} No upcoming match with that team(s) found", delete_after=5)


	@commands.hybrid_command(name='preds', aliases=['predictions'])
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def predictions(self, ctx: commands.context, who: str=None):
		"""
		Show a user’s predictions
		~preds [user(optional)]
		ALT: ps/predicts/predictions
		Shows a specified user’s current predictions, one gameday at a time. A user can be specified using their username, discord ID, and mentions. 
		If no user is specified it returns the predictions of the calling user.
		EXAMPLE: ~preds TeeHaychZee#1975
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
			allpreds = await conn.fetch(queries.USERPREDS, user.id)
			if not allpreds:
				await ctx.send("No predictions found, use /predall or /pred to add some!", delete_after=5)
				return
			color = await helpers.getColor(conn, user.id)


		indexes = set([p["rank"] for p in allpreds])

		empty = discord.utils.get(self.bot.emojis, name="empty")

		nextup = False
		idx = -1
		count = 0
		embeds = []
		dayStamp = ""
		for i in range(len(indexes)):

			embed = discord.Embed(title="No Predictions", colour=color)
			if not nextup:
				idx += 1 
			for p in allpreds[count:]:
				if p["rank"] == i + 1:
					dayStamp = datetime.utcfromtimestamp(p["starttime"] / 1000)
					embed.title = f"{user.name}'s Predictions For {dayStamp.strftime('%A, %B %e')}"
					logo1 = discord.utils.get(self.bot.emojis, name=p["htshort"])
					logo2 = discord.utils.get(self.bot.emojis, name=p["atshort"])
					if logo1 == None:
						logo1 = discord.utils.get(self.bot.emojis, name="OWC")

					if logo2 == None:
						logo2 = discord.utils.get(self.bot.emojis, name="OWC")
					if p["htshort"] == p["pwinner"]:
						wlogo = logo1
						wshort = p["htshort"]
					else:
						wlogo = logo2
						wshort = p["atshort"]

					if p['state'] == 'pending':
						embed.add_field(name=f"**{logo1} {await PredictionsCog.shortNames().convert(ctx, p['htname'])} vs {await PredictionsCog.shortNames().convert(ctx, p['atname'])} {logo2}**", value=f"{empty}{empty}{empty}{empty}Winner: {wlogo} **{wshort}** \u202F {p['winner_score']}{p['loser_score']}", inline=False)
					else:
						if p['htscore'] > p['atscore']:
							embed.add_field(name=f"**{logo1} __{await PredictionsCog.shortNames().convert(ctx, p['htname'])}__ {p['htscore']} - {p['atscore']} {await PredictionsCog.shortNames().convert(ctx, p['atname'])} {logo2}**", value=f"{empty}{empty}{empty}{p['indicator']} \u202F Winner: {wlogo} **{wshort}** \u202F {p['winner_score']}{p['loser_score']}", inline=False)
						else:
							embed.add_field(name=f"**{logo1} {await PredictionsCog.shortNames().convert(ctx, p['htname'])} {p['htscore']} - {p['atscore']} __{await PredictionsCog.shortNames().convert(ctx, p['atname'])}__ {logo2}**", value=f"{empty}{empty}{empty}{p['indicator']} \u202F Winner: {wlogo} **{wshort}** \u202F {p['winner_score']}{p['loser_score']}", inline=False)

					if p['state'] != "concluded":
						nextup = True
					
					count += 1
				else:
					break
			embeds.append(helpers.Page({'embed': embed}))
					
		currSort = idx
		choices = await ctx.send(**embeds[currSort].msg)
		if len(embeds) > 1:
			await choices.edit(view=helpers.Pagnation(currSort, embeds, choices, wraps=False, owner=ctx.author))


	@commands.hybrid_command(name='viewpred', aliases=['vp', 'vpred', 'vpreds', 'viewpreds'])
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def viewpred(self, ctx: commands.context, team1: str, team2: str=None, who:str=None):
		"""
		View predictions for a specific team or matchup
		~viewpreds [team1] [team2(optional)] [user(optional)]
		ALT: vp/vpred/vpreds/viewpred
		Shows your predictions for the specified match. If [team2] is not specified it shows all your predictions for [team1]. 
		A user can be specified using their username, discord ID, and mentions. 
		If no user is specified it returns the predictions of the calling user.
		EXAMPLE: ~viewpreds dallas AngieTheCat
		"""

		try:
			t1 = await PredictionsCog.CustomAbb().convert(ctx, team1)
		except commands.BadArgument:
			await ctx.send("Invalid team", delete_after=5)
			return

		titleString = shortNames[abbreviations[t1]]
		if team2 != None:
			try:
				t2 = await PredictionsCog.CustomAbb().convert(ctx, team2)
			except commands.BadArgument:
				t2 = team2

			if who == None:
				if t2 not in abbrevs:
					try:
						user = await commands.UserConverter().convert(ctx, t2)
					except commands.BadArgument:
						await ctx.send("User not found")
						return
					t2 = None
				else:
					user = ctx.author
					titleString = f"{shortNames[abbreviations[t1]]} vs {shortNames[abbreviations[t2]]}"
			else:
				try:
					user = await commands.UserConverter().convert(ctx, who)
					titleString = f"{shortNames[abbreviations[t1]]} vs {shortNames[abbreviations[t2]]}"
				except commands.BadArgument:
					await ctx.send("User not found")
					return
		else:
			t2 = None
			user = ctx.author

		async with self.bot.db.acquire() as conn:
			allpreds = await conn.fetch(queries.USERPREDS, user.id)
			if not allpreds:
				await ctx.send("No predictions found, use /predall or /predict to add some!", delete_after=5)
				return
			color = await helpers.getColor(conn, user.id)
		

		indexes = set([p["rank"] for p in allpreds])

		empty = discord.utils.get(self.bot.emojis, name="empty")


		nextup = False
		idx = -1
		embeds = []
		readPred = False
		i = 0
		k = -1
		while i < len(allpreds):
			j = 0
			k += 1
			while j < 1 and i < len(allpreds):	
				readPred = False
				p = allpreds[i]
				if t2 == None:
					if  t1 in {p['htshort'], p['atshort']}:
						readPred = True
				else:
					if {t1, t2} <= {p['htshort'], p['atshort']}:
						readPred = True

				if readPred:
					embed = discord.Embed(title="No Preds Found", colour=color)
					embed.title = f"{user.name}'s Predictions For {titleString}"
					logo1 = discord.utils.get(self.bot.emojis, name=p["htshort"])
					logo2 = discord.utils.get(self.bot.emojis, name=p["atshort"])
					if logo1 == None:
						logo1 = discord.utils.get(self.bot.emojis, name="OWC")

					if logo2 == None:
						logo2 = discord.utils.get(self.bot.emojis, name="OWC")
					if p["htshort"] == p["winner"]:
						wlogo = logo1
						wshort = p["htshort"]
					else:
						wlogo = logo2
						wshort = p["atshort"]


					if p['state'] == 'pending':
						embed.add_field(name=f"**{logo1} {await PredictionsCog.shortNames().convert(ctx, p['htname'])} vs {await PredictionsCog.shortNames().convert(ctx, p['atname'])} {logo2}**", value=f"{empty}{empty}{empty}{empty}Winner: {wlogo} **{wshort}** \u202F {p['winner_score']}{p['loser_score']}", inline=False)
					else:
						if p['htscore'] > p['atscore']:
							embed.add_field(name=f"**{logo1} __{await PredictionsCog.shortNames().convert(ctx, p['htname'])}__ {p['htscore']} - {p['atscore']} {await PredictionsCog.shortNames().convert(ctx, p['atname'])} {logo2}**", value=f"{empty}{empty}{empty}{p['indicator']} \u202F Winner: {wlogo} **{wshort}** \u202F {p['winner_score']}{p['loser_score']}", inline=False)
						else:
							embed.add_field(name=f"**{logo1} {await PredictionsCog.shortNames().convert(ctx, p['htname'])} {p['htscore']} - {p['atscore']} __{await PredictionsCog.shortNames().convert(ctx, p['atname'])}__ {logo2}**", value=f"{empty}{empty}{empty}{p['indicator']} \u202F Winner: {wlogo} **{wshort}** \u202F {p['winner_score']}{p['loser_score']}", inline=False)
					
					if p['state'] != "concluded":
						idx += 1
						nextup = True

					embeds.append(helpers.Page({'embed': embed}))
					j += 1
				
				i += 1
				if not nextup and readPred:
					idx += 1

		currSort = idx
		choices = await ctx.send(**embeds[currSort].msg)
		if len(embeds) > 1:
			await choices.edit(view=helpers.Pagnation(currSort, embeds, choices, wraps=False, owner=ctx.author))


	@commands.hybrid_command(name='allpreds', aliases=['ap', 'allpred', 'apred', 'apreds'])
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def allpreds(self, ctx: commands.context, team1: str=None, team2: str=None):
		"""
		View all predictions for a matchup
		~allpreds [team1] [team2]
		ALT: ap/apred/apreds/allpred
		Shows all predictions made by users for the specified matchup
		EXAMPLE: ~allpreds dal gla
		"""
		if team1 is None and team2 is None:
			q= """
			WITH allpreds AS (
				SELECT 
					matches.*, 
					DENSE_RANK() OVER(ORDER BY DATE_PART('doy', matches.startdate)) AS rank,
					predictions.user_id, 
					predictions.winner, 
					predictions.loser, 
					predictions.match_id, 
					(CASE WHEN predictions.winner_score IS NULL THEN ' ' ELSE CONCAT(predictions.winner_score::char, '-') END) winner_score, 
					(CASE WHEN predictions.loser_score IS NULL THEN '  ' ELSE predictions.loser_score::char END) loser_score, 
					(CASE WHEN predictions.winner_score IS NULL THEN CONCAT(predictions.winner, ' W-L: ') ELSE CONCAT(predictions.winner, ' ', predictions.winner_score::char, '-', predictions.loser_score::char, ': ') END) scoreline
				FROM 
					athena.matches INNER JOIN athena.predictions ON matches.id = predictions.match_id
				WHERE
					week_number = (SELECT MIN(week_number) FROM athena.weeks WHERE enddate > NOW()) 
			)
			SELECT 
				allpreds.id, allpreds.week_number, rank, allpreds.htshort, allpreds.atshort, count(CASE WHEN allpreds.winner = allpreds.htshort THEN 1 END) as "homecount", count(CASE WHEN allpreds.winner = allpreds.atshort THEN 1 END) as "awaycount"
			FROM
				allpreds
			GROUP BY
				allpreds.id, allpreds.week_number, rank, allpreds.htshort, allpreds.atshort
			ORDER BY 
				id, rank
			"""
			async with self.bot.db.acquire() as conn:
				allpreds = await conn.fetch(q)
			indexes = set([p["rank"] for p in allpreds])
			embeds = []
			count = 0
			for i in range(len(indexes)):
				predStr = ''
				for p in allpreds[count:]:
					if p['rank'] == i + 1:
						home = await PredictionsCog.CustomAbb().convert(ctx, p['htshort'])
						away = await PredictionsCog.CustomAbb().convert(ctx, p['atshort'])
						homeemote = discord.utils.get(self.bot.emojis, name=home)
						if homeemote is None:
							homeemote = discord.utils.get(self.bot.emojis, name='OWC')
						awayemote = discord.utils.get(self.bot.emojis, name=away)
						if awayemote is None:
							awayemote = discord.utils.get(self.bot.emojis, name='OWC')
						total = int(p['homecount'] + p['awaycount'])
						homeper = int((p['homecount'] /total) * 100)
						awayper = int((p['awaycount'] /total) * 100)
						predStr += f"{homeemote} **{homeper}% - {awayper}%** {awayemote}  **({total} predictions)**\n\n"
						count += 1
					else:
						break
				
				embeds.append(helpers.Page({'embed': discord.Embed(title=f"All Predictions - Day {i + 1} of {max(indexes)}", description=predStr, colour=0xff8900)}))
			currSort = 0
			choices = await ctx.send(**embeds[currSort].msg) 
			if len(embeds) > 1:
				await choices.edit(view=helpers.Pagnation(currSort, embeds, choices, wraps=False))

		else:	
			try:
				t1 = await PredictionsCog.CustomAbb().convert(ctx, team1)
			except commands.BadArgument:
				await ctx.send("Invalid team", delete_after=5)
				return

			try:
				t2 = await PredictionsCog.CustomAbb().convert(ctx, team2)
			except commands.BadArgument:
				await ctx.send("Invalid team", delete_after=5)
				return
			


			emotes = {t1: discord.utils.get(self.bot.emojis, name=t1), t2: discord.utils.get(self.bot.emojis, name=t2)}
			empty = discord.utils.get(self.bot.emojis, name="empty")

			async with self.bot.db.acquire() as conn:
				allpreds = await conn.fetch(queries.ALLPREDSFORMATCH, t1, t2)

			names = {}
			t1count = 0
			t2count = 0
			
			s = ['W-L: ', '3-0: ', '3-1: ', '3-2: ']
			scorelines = {f"{t1} All: ": 0, f"{t2} All: ": 0}
			for l in s:
				scorelines[f"{t1} {l}"] = 0
				scorelines[f"{t2} {l}"] = 0

			for p in allpreds:
				user = await commands.UserConverter().convert(ctx, str(p['user_id']))
				names[p['user_id']] = user.name[:11]
				try:
					scorelines[f"{p['winner']} All: "] += 1
					scorelines[p['scoreline']] += 1
				except KeyError as e:
					pass
				
			ml = max(len(str(s)) for s in scorelines.values())
			embeds = []
			keys = list(scorelines.keys())
			first = True
			statsString = f"{emotes[t1]} **{int(scorelines[keys[0]]/len(allpreds) * 100)}%** - **{int(scorelines[keys[1]]/len(allpreds) * 100)}% {emotes[t2]}{empty}({len(allpreds)} predictions)**\n\n"
			for i in range(0, len(scorelines), 2):
				e1 = empty
				e2 = empty
				if first:
					e1 = emotes[t1]
					e2 = emotes[t2]
					first = False
				statsString += f"{e1} **`{keys[i][4:]}`**`{scorelines[keys[i]]:{sp}<{ml}} {'(' + str(int(scorelines[keys[i]]/len(allpreds) * 100)) + '%)':{sp}<{5}}`{empty}{e2} **`{keys[i + 1][4:]}`**`{scorelines[keys[i + 1]]:{sp}<{ml}} {'(' + str(int(scorelines[keys[i + 1]]/len(allpreds) * 100)) + '%)':{sp}<{5}}`\n"
						
			
			#statsString += f"`{keys[i][4:]}{scorelines[keys[i]]:{sp}<{ml}}({int(scorelines[keys[i]]/len(allpreds) * 100)}{'%)':{sp}<{ml}}{tb * 6}{keys[i + 1][4:]}{scorelines[keys[i + 1]]:{sp}<{ml}}({int(scorelines[keys[i + 1]]/len(allpreds) * 100)}{'%)':{sp}<{ml}}`\n"
			# statsString += f"`**{keys[i][4:]}**{scorelines[keys[i]]:{sp}<{ml}}{tb * 6}**{keys[i + 1][4:]}**{scorelines[keys[i + 1]]:{sp}<{ml}}`\n"
		
			embeds.append(helpers.Page({'embed': discord.Embed(title = f"{emotes[t1]} {shortNames[abbreviations[t1]]} vs {shortNames[abbreviations[t2]]} {emotes[t2]}", description = statsString, colour=0xff8900)}))
			
			t1per = int(scorelines[keys[0]]/len(allpreds) * 100)
			t2per = int(scorelines[keys[1]]/len(allpreds) * 100)

			tNames = list(names.values())
			teamNames = [shortNames[abbreviations[t1]], shortNames[abbreviations[t2]]]

			ml = max(len(s) for s in tNames)
			tl = max(len(s) for s in teamNames)

			i = 0
			while i < len(allpreds):
				dayString = f"{emotes[t1]} **{t1per}%** - **{t2per}%** {emotes[t2]} {empty} **({len(allpreds)} predictions)**\n"
				j = 0
				while j < 5 and i < len(allpreds):
					p = allpreds[i]				
					
					dayString += f"**`{names[p['user_id']]:{sp}<{ml}}{tb * 2}`** {emotes[p['winner']]} \uFEFF`{shortNames[abbreviations[p['winner']]]:{sp}<{tl}}{sp}{tb}{p['winner_score']}{p['loser_score']}`\n"
					j += 1
					i += 1
				
				embeds.append(helpers.Page({'embed':discord.Embed(title=f"Predictions for {emotes[t1]} {shortNames[abbreviations[t1]]} vs {shortNames[abbreviations[t2]]} {emotes[t2]}", description=dayString, colour=0xff8900)}))
					
			
			currSort = 0
			choices = await ctx.send(**embeds[currSort].msg)
			if len(embeds) > 1:
				await choices.edit(view=helpers.Pagnation(currSort, embeds, choices, wraps=False, owner=ctx.author))


	@commands.hybrid_command(name='predrandom', aliases=['pr', 'predictrandom', 'predrand'])
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def predrand(self, ctx:commands.context, day: int=None):
		"""
		RNG wins
		~predrand [day(optional)]
		ALT: pr/predrandom/predictrandom
		Allows you to randomise all your predictions for a specified gameday in the current matchweek. 
		Both the winner/loser and map score will be randomised. If a day is not specified all matches in the current match week will be randomised.
		EXAMPLE: ~predrand 3

		"""
		async with self.bot.db.acquire() as conn:
			timeobj = datetime.utcnow() + timedelta(minutes=cutoffTime)
			matches = await conn.fetch(queries.UPCOMINGMATCHESINWEEK, int(timeobj.timestamp() * 1000))
			stocks = await conn.fetch("SELECT teamshort, currentprice, updatedprice, highprice, lowprice, ticker FROM economy.market")

			indexes = set([m["rank"] for m in matches])
			if day != None:
				flag = True
				day = int(day)
				if day not in indexes:
					await ctx.send("Invalid day", delete_after=3)
					return
			else:
				flag = False


			async with conn.transaction():
				for m in matches:
					if datetime.utcnow() > datetime.utcfromtimestamp(m["starttime"] / 1000) - timedelta(minutes=cutoffTime):
						continue
					if flag:
						if m['rank']==day:
							choices = ['htshort', 'atshort']
							choice = m[random.choice(choices)]
							try:
								winner= await PredictionsCog.CustomAbb().convert(ctx, choice)
							except commands.BadArgument:
								pass
							if winner == m['htshort']:
								loser = m['atshort']
							elif winner == m['atshort']:
								loser = m['htshort']
							else:
								await ctx.send("Invalid Team!")
								return
							score = [3, random.randint(0,2)]
							match min(score):
								case 0:
									percent = (0.25 * 0.01)
								case 1:
									percent = (0.20* 0.01) 
								case 2:
									percent = (0.15 * 0.01)
							
							await self.stock.insertMarket(conn, stocks, winner, loser, percent, "Prediction")
							await conn.execute("DELETE FROM athena.predictions WHERE user_id = $1 AND match_id = $2;", ctx.author.id, m["id"])
							await conn.execute("INSERT INTO athena.predictions (user_id, winner, winner_score, loser, loser_score, match_id) VALUES ($1, $2, $3, $4, $5, $6);", ctx.author.id, winner, max(score), loser, min(score), m["id"])
					else:
						choices = ['htshort', 'atshort']
						choice = m[random.choice(choices)]

						try:
							winner= await PredictionsCog.CustomAbb().convert(ctx, choice)
						except commands.BadArgument:
							pass

						if winner == m['htshort']:
							loser = m['atshort']
						elif winner == m['atshort']:
							loser = m['htshort']
						else:
							await ctx.send("Invalid Team!")
							return
						score = [3, random.randint(0,2)]
						match min(score):
							case 0:
								percent = (0.25 * 0.01)
							case 1:
								percent = (0.20* 0.01) 
							case 2:
								percent = (0.15 * 0.01)
						await self.stock.insertMarket(conn, stocks, winner, loser, percent, "Prediction")
						
						await conn.execute("DELETE FROM athena.predictions WHERE user_id = $1 AND match_id = $2;", ctx.author.id, m["id"])
						await conn.execute("INSERT INTO athena.predictions (user_id, winner, winner_score, loser, loser_score, match_id) VALUES ($1, $2, $3, $4, $5, $6);", ctx.author.id, winner, max(score), loser, min(score), m["id"])
	
		if flag:		
			await ctx.send(f"{ctx.author.mention} has made random predictions on day {day}! Use /predictions to find out what they are", delete_after=5)
		else:
			await ctx.send(f"{ctx.author.mention} has made random predictions! Use /predictions to find out what they are", delete_after=5)


	#@commands.hybrid_command(name='leaderboard', aliases=['lb'])
	#@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	@commands.command(name='leaderboard', aliases=['lb'])
	async def leaderboard(self, ctx, *, args="event winner"):
		"""
		Prediction leaderboards
		~leaderboard [type(optional)] [sort order(optional)]
		ALT: lb
		Shows users sorted by the most winner predictions gotten right for the current ongoing Overwatch League event by default if type and sort order are not clarified.

		[type]:
		all
		ALT: a

		event
		ALT: e

		current week
		ALT: wk

		[sort order]:
		winner
		ALT: winners, w

		winner %
		ALT: winner%, winners%, w%

		maps
		ALT: map, m

		map %
		ALT: map%, maps%, m%

		EXAMPLE: ~lb all win%
		"""

		await ctx.send("Currently disabled for bug fixes.")
		return
		args = args.split()
		#FIX LEADERBOARD
		# route all mappings through dictionaries to ensure a consistent format after the initial parse
		sorts = {"winner": "winner", "winners": "winner", "winner%": "winner%", "winners%": "winner%", "w": "winner", "w%": "winner%", "maps": "maps", "map": "maps", "maps%": "maps%", "map%": "maps%", "m": "maps", "m%": "maps%", "total": "total", "t": "total"}
		windows = {"all": "all", "a": "all", "event": "event", "e": "event", "week": "week", "wk": "week"}
		events = {'kickoffclash': 'Kickoff Clash', 'kickoff': 'Kickoff Clash', 'clash': 'Kickoff Clash', 'kc': 'Kickoff Clash', 'kick': 'Kickoff Clash', 'midseasonmadness': 'Midseason Madness', 'mid': 'Midseason Madness', 'midseason':'Midseason Madness', 'mad': 'Midseason Madness', 'madness': 'Midseason Madness', 'mm': 'Midseason Madness', 'summershowdown': "Summer Showdown", 'summer': "Summer Showdown", 'showdown': "Summer Showdown", 'ss': "Summer Showdown", 'countdowncup': "Countdown Cup", 'countdown': "Countdown Cup", 'cup': "Countdown Cup", 'cc': "Countdown Cup"}
		try:
			window = max(w.lower() for w in args if w.lower() in set(windows.keys()))
			args.remove(window)
			window = windows[window]
		except ValueError:
			window = "event"

		try:
			sortorder = max(w.lower() for w in args if w.lower() in set(sorts.keys()))
			args.remove(sortorder)
			sortorder = sorts[sortorder]
		except ValueError:
			sortorder = "winner"

		async with self.bot.db.acquire() as conn:
			specific = ''.join(args)
			if not specific:
				#get this based on distinct items in matches db
				if window == "event":
					event = await conn.fetch(f"SELECT event FROM athena.weeks WHERE enddate > NOW() ORDER BY week_number LIMIT 1;")
					specific = event[0]['event']
				#remove this due to not much use
				elif window == "week":
					week = await conn.fetch(f"SELECT MIN(week_number) AS num FROM athena.weeks WHERE enddate > NOW();")
					specific = week[0]['num']
			#remove due to inactive
			elif specific.isdecimal():
				if int(specific) < 1 or int(specific) > 19:
					await ctx.send("Invalid week (1-19)")
					return
				else:
					specific = int(specific)
			else:
				try:
					specific = events[specific]
				except KeyError:
					await ctx.send("An option was invalid")
					return

			if sortorder == "winner":
				sort = "winner_correct DESC, maps_correct DESC, user_id DESC"
				eventCutoff = 0
			elif sortorder == "winner%":
				sort = "winner_percent DESC, total DESC, user_id DESC"
				eventCutoff = 5
			elif sortorder == "maps":
				sort = "maps_correct DESC, total DESC, user_id DESC"
				eventCutoff = 0
			elif sortorder == "maps%":
				sort = "maps_percent DESC, total DESC, user_id DESC"
				eventCutoff = 5
			else:
				sort = "total DESC, user_id DESC"
				eventCutoff = 5

			if window == "all":
				title = "All Season"
				records = await conn.fetch(f"{queries.LBALLSEASON} {sort};", self.cutoff)
			elif window == "event":
				title = f"the {specific}"
				records = await conn.fetch(f"{queries.LBCURRENTEVENT} {sort};", eventCutoff, specific)
				if not records:
					await ctx.send("There is no leaderboard for that event yet!")
					return
			#remove
			elif window == "week":
				title = f"Week {specific}"
				records = await conn.fetch(f"{queries.LBWEEK} {sort};", 0, specific)
				if not records:
					await ctx.send("There is no leaderboard for that week yet!")
					return

		
		
		names = {}
		for p in records:
			user = await commands.UserConverter().convert(ctx, str(p['user_id']))
			names[p['user_id']] = user.name[:11]
		
		tNames = list(names.values())
		ml = max(len(s) for s in tNames)
		rl = len(f"{len(records)}.")
		tl = max(len(str(s["total"])) for s in records)
		wl = max(len(str(s["winner_correct"])) for s in records)
		nl = max(len(str(s["maps_correct"])) for s in records)

		embeds = []
		i = 0
		page = 1
		while i < len(records):
			leaderboardString = f"__`{'Name':{sp}^{rl + ml + 2}}`__\uFEFF__`{'Correct':{sp}<{wl + 7}}{'Total':{sp}^{tl}}`__\n"
			j = 0
			while j < 5 and i < len(records):
				r = records[i]
				if sortorder in {"maps", "map", "m", "map%", "maps%", "m%"}:
					leaderboardString += f"`{str(i + 1) + '.':{sp}<{rl}}`\uFEFF**`{names[r['user_id']]:{sp}<{ml}}{tb * 2}`**\uFEFF`{r['maps_correct']:{sp}<{wl}}{tb * 3}{str(r['maps_percent']) +'%':{sp}<{3}}{tb * 3}{r['total']:{sp}<{tl}}`\n"
					leaderboardString += f"`{' ':{sp}<{rl}}`\uFEFF`{' ':{sp}<{ml}}{tb * 2}`\uFEFF`{r['winner_correct']:{sp}<{wl}}{tb * 3}{str(r['winner_percent']) +'%':{sp}<{3}}{tb * 3}{' ':{sp}<{tl}}`\n"
				else:
					leaderboardString += f"`{str(i + 1) + '.':{sp}<{rl}}`\uFEFF**`{names[r['user_id']]:{sp}<{ml}}{tb * 2}`**\uFEFF`{r['winner_correct']:{sp}<{wl}}{tb * 3}{str(r['winner_percent']) +'%':{sp}<{3}}{tb * 3}{r['total']:{sp}<{tl}}`\n"
					leaderboardString += f"`{' ':{sp}<{rl}}`\uFEFF`{' ':{sp}<{ml}}{tb * 2}`\uFEFF`{r['maps_correct']:{sp}<{wl}}{tb * 3}{str(r['maps_percent']) +'%':{sp}<{3}}{tb * 3}{' ':{sp}<{tl}}`\n"
				j += 1
				i += 1
			
			embeds.append(helpers.Page({'embed': discord.Embed(title=f"Leaderboard for {title} {page}/{int(len(records) / 5)}", description=leaderboardString, colour=0xff8900)}))
			page += 1

		currSort = 0
		choices = await ctx.send(**embeds[currSort].msg)
		if len(embeds) > 1:
			await choices.edit(view=helpers.Pagnation(currSort, embeds, choices, wraps=False, owner=ctx.author))

	@commands.hybrid_command(name='predstats', aliases=['ps'])
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def predstats(self, ctx: commands.context, who: str=None):
		"""
		Prediction Statistics
		~predstats 
		ALT: ps
		View your prediction statistics across the season. 
		A user can be specified using their username, discord ID, and mentions. 
		If no user is specified it returns the predictions of the calling user.

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
			statline = await conn.fetchrow(queries.USERPREDSTATS, user.id, self.cutoff)

			if not statline:
				await ctx.send(f"Less than {self.cutoff} predictions found for that user (can't calculate stats)")
				return

			embed = discord.Embed(title=f"**{user.name}**'s Prediction Stats", description=f"Total Predictions: {statline['total']}\nWinners Correct: {statline['winner_correct']} ({statline['winner_percent']}%)\nMaps Correct: {statline['maps_correct']} ({statline['maps_percent']}%)\nWinners Rank: {statline['winner_rank']}\nMaps Rank: {statline['maps_rank']}\n", color=await helpers.getColor(conn, user.id))

		await ctx.send(embed=embed)

	@commands.command(name='editpred', aliases=['editpredict'], hidden=True)
	@commands.has_permissions(ban_members=True)
	async def editpred(self, ctx, t1, score, t2=None, who=None):
		try:
			t1 = await PredictionsCog.CustomAbb().convert(ctx, t1)
		except commands.BadArgument:
			await ctx.send("Invalid team!", delete_after=5)
			return
		if t2 != None:
			try:
				t2 = await PredictionsCog.CustomAbb().convert(ctx, t2)
			except commands.BadArgument:
				await ctx.send("Invalid team!", delete_after=5)
				return
		
		if who != None:
			try:
				user = await commands.UserConverter().convert(ctx, who)
			except commands.BadArgument:
				await ctx.send("User not found")
				return
		else:
			user = ctx.author

		if score == 'random':
			loserScore = random.randint(0,2)
			scores = [3, loserScore]
			score = f'3-{loserScore}'
		else:
			scores = [int(score[0]), int(score[2])]

	
		r = range(0,5)
		if (scores[0] not in r or scores[1] not in r) or (scores[0] == scores[1]) or (max(scores) not in {3,4}):
			await ctx.send(f"{ctx.author.mention} Invalid map score!", delete_after=5)
			return

		if scores[0] > scores[1]:
			winner = t1
			winnerScore = scores[0]
			loser = t2
			loserScore = scores[1]
		else:
			winner = t2
			winnerScore = scores[1]
			loser = t1
			loserScore = scores[0]

		async with self.bot.db.acquire() as conn:
			timeobj = datetime.utcnow() + timedelta(minutes=cutoffTime)
			matches = await conn.fetch(queries.UPCOMINGMATCHESINWEEK, int(timeobj.timestamp() * 1000))
			stocks = await conn.fetch("SELECT teamshort, currentprice, updatedprice, highprice, lowprice, ticker FROM economy.market")
			match loserScore:
				case 0:
					percent = (0.25 * 0.01)
				case 1:
					percent = (0.20* 0.01) 
				case 2:
					percent = (0.15 * 0.01)

			async with conn.transaction():
				for m in matches:
					
					if t2 == None:
						if t1 in {m['htshort'], m['atshort']}:
							if winner == None:
								if loser == m['htshort']:
									winner = m['atshort']
								else:
									winner = m['htshort']
							else:
								if winner == m['htshort']:
									loser = m['atshort']
								else:
									loser = m['htshort']
							await self.stock.insertMarket(conn, stocks, winner, loser, percent, "Prediction")
							await conn.execute("DELETE FROM athena.predictions WHERE user_id = $1 AND match_id = $2;", user.id, m["id"])
							await conn.execute("INSERT INTO athena.predictions (user_id, winner, winner_score, loser, loser_score, match_id) VALUES ($1, $2, $3, $4, $5, $6);", user.id, winner, winnerScore, loser, loserScore, m["id"])
							await ctx.send(f"{user.mention} predicted the {abbreviations[winner]} to defeat the {abbreviations[loser]} {max(scores)}-{min(scores)}", delete_after=7)
							break
					else:
						if {t1, t2} <= {m['htshort'], m['atshort']}:
							await self.stock.insertMarket(conn, stocks, winner, loser, percent, "Prediction")
							await conn.execute("DELETE FROM athena.predictions WHERE user_id = $1 AND match_id = $2;", user.id, m["id"])
							await conn.execute("INSERT INTO athena.predictions (user_id, winner, winner_score, loser, loser_score, match_id) VALUES ($1, $2, $3, $4, $5, $6);", user.id, winner, winnerScore, loser, loserScore, m["id"])
							await ctx.send(f"{user.mention} predicted the {abbreviations[winner]} to defeat the {abbreviations[loser]} {max(scores)}-{min(scores)}", delete_after=7)
							break
				else:
					await ctx.send(f"{ctx.author.mention} No upcoming match with that team(s) found", delete_after=5)

	@commands.hybrid_command(name="syncpreds")
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def syncpreds(self, ctx: commands.context, preds_link=None, all=None):
		"""
		Sync Predictions
		-syncpreds
		Alt: -sync, -sp
		Sync your predictions in Athena by placing in associated OWL Website Predictions Link
		The bot should automatically scrape the API and get the associated prediction data
		"""

		if preds_link is None:
			await ctx.send("Please enter an OWL website username or preds link", delete_after=5)
			return
		
		if "https://pickem.overwatchleague.com" in preds_link: 
			link_parts = preds_link.split('/')
			try:
				link_parts.remove("en-us")
			except ValueError:
				pass
			owl_username = link_parts[4]
		else:
			owl_username = preds_link.lower()
		
				

		response = requests.get(f"https://pickem.overwatchleague.com/api/view?username={owl_username}")
		if response.status_code == 404:
			await ctx.send("Username not found!", delete_after=5)
			return 
		elif response.status_code != 200:
			await ctx.send("API Error, unable to sync preds!", delete_after=5)
			return
		else:
			pass 
		predictions_data = json.loads(response.text)

		# needs to go through each match, get matchup id, get that match from json, get those scores, and then apply it to db. 
		async with self.bot.db.acquire() as conn:
			if all != None:
				matches = await conn.fetch(queries.ALLMATCHES)
				msg = await ctx.send("Syncing predictions, this may take a while!")
			else:
				timeobj = datetime.utcnow() + timedelta(minutes=cutoffTime)
				matches = await conn.fetch(queries.UPCOMINGMATCHESINWEEK, int(timeobj.timestamp() * 1000))
				msg = await ctx.send("Syncing predictions...")
			
			stocks = await conn.fetch("SELECT teamshort, currentprice, updatedprice, highprice, lowprice, ticker FROM economy.market")
			async with conn.transaction():
				for m in matches:
					flag = False
					if datetime.utcnow() > datetime.utcfromtimestamp(m["starttime"]/1000) - timedelta(minutes=cutoffTime):
						if all == None:
							flag = True
					
					if flag == True:
						continue

					matchupid = m['pickem_id']
					ht = m['htid']
					at = m['atid']
					for pred in predictions_data['predictions']:
						if pred['matchup_id'] == matchupid:
							pht = pred['homecard_id']
							pat = pred['awaycard_id']
							if ht == pht and at == pat:
								homescore = pred['homecard_score']
								awayscore = pred['awaycard_score']
							elif ht ==pat and at == pht:
								homescore = pred['awaycard_score']
								awayscore = pred['homecard_score']
							else:
								continue

							if homescore < awayscore:
								winner = m['atshort']
								loser = m['htshort']
								break
							elif awayscore < homescore:
								winner = m['htshort']
								loser = m['atshort']
								break
							else:
								print("Lol something fucked")
								continue

					try:				
						score = [homescore, awayscore]
						match min(score):
							case 0:
								percent = (0.25 * 0.01)
							case 1:
								percent = (0.20* 0.01) 
							case 2:
								percent = (0.15 * 0.01)
						
						await self.stock.insertMarket(conn, stocks, winner, loser, percent, "Prediction")
						await conn.execute("DELETE FROM athena.predictions WHERE user_id = $1 AND match_id = $2;", ctx.author.id, m["id"])
						await conn.execute("INSERT INTO athena.predictions (user_id, winner, winner_score, loser, loser_score, match_id) VALUES ($1, $2, $3, $4, $5, $6);", ctx.author.id, winner, max(score), loser, min(score), m["id"])
					except UnboundLocalError:
						pass
	
			await msg.edit(content = f"Predictions are synced for {ctx.author.mention}")
			await asyncio.sleep(5)
			await msg.delete()




		

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload: discord.raw_models.RawReactionActionEvent):
		if payload.user_id == self.bot.user.id:
			return

		if payload.message_id in self.monitored and payload.emoji.name == "\U00002705" and payload.user_id not in self.timedOutUsers:
			member = self.bot.get_user(payload.user_id)
			chan = self.bot.get_channel(payload.channel_id)
			added = 0
			msg = await chan.send(f"{member.mention} Processing your predictions...")
			for m in self.matches:
				if datetime.utcnow() > m.matchObj["startdate"] - timedelta(minutes=cutoffTime):
					continue
				if m.msg.id == payload.message_id:
					async with self.bot.db.acquire() as conn:
						added += await m.addPred(payload.user_id, conn)

			await msg.edit(content=f"{member.mention} Successfully predicted {added} matches", delete_after=15)

			asyncio.ensure_future(self.cooldownUser(payload.user_id))


async def setup(bot):
	await bot.add_cog(PredictionsCog(bot))
