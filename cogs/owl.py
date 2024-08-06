import discord
import asyncio
import asyncpg
from discord import app_commands
from discord.ext import commands, tasks
import time
from time import gmtime, strftime
import datetime
from datetime import timezone, timedelta
from discord.ext.commands.cooldowns import BucketType
import pytz
import requests
import json
import pickle
from resources import queries, helpers

tz = strftime("%z", gmtime())

class OwlCog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.economy = self.bot.get_cog("EconCog")
		self.stock = self.bot.get_cog("StockCog")
		self.token = ''
		self.poller.start()
	
	async def get_token(self):
		#need to change this to use env variables
		data = { 'grant_type': 'client_credentials' }
		response = requests.post('https://us.battle.net/oauth/token', data=data, auth=('INSERT_TOKENS_HERE', 'REMOVING_THIS_TOKEN'))
		token = json.loads(response.text)
		self.token = token['access_token']
		



	async def oldpollMatches(self):
		if tz not in {"-0000", "+0000", "GMT", "UTC"}:
			print(tz)
			#return

		async with self.bot.db.acquire() as conn:
			nq = await conn.fetch("SELECT * FROM athena.weeks WHERE startdate <= NOW() ORDER BY week_number ASC;")
			if not nq:
				print("Attempted to poll weekly schedule but no matching week was found")
				return
			headers = {
				'authority': 'pk0yccosw3.execute-api.us-east-2.amazonaws.com',
				'origin': 'https://overwatchleague.com',
				'x-origin': 'overwatchleague.com',
				'accept': '*/*',
				'sec-fetch-site': 'cross-site',
				'sec-fetch-mode': 'cors',
				'referer': 'https://overwatchleague.com/',
				'accept-encoding': 'gzip, deflate, br',
				'accept-language': 'en-US,en;q=0.9',
			}
			for week in nq:
				n = week['week_number']
				params = (
				('stage', 'regular_season'),
				('page', '{}'.format(n)),
				('season', '2023'),
				('locale', 'en-us'),
				)
				
				response = requests.get(f'https://pk0yccosw3.execute-api.us-east-2.amazonaws.com/production/v2/content-types/schedule/blt27f16f110b3363f7/week/{n}?locale=en-us', headers=headers, params=params)
				week = json.loads(response.text)
				mIndexQuery = await conn.fetchrow("SELECT COUNT(id) FROM athena.matches WHERE week_number < $1;", n)

				response = requests.get('https://pickem.overwatchleague.com/api/view?username=teehaychzee')
				pickem = json.loads(response.text)

				mIndex = mIndexQuery['count'] + 1
				count = 0
				for item in week["data"]["tableData"]["events"]:
					for match in item["matches"]:
						async with conn.transaction():
							if match['isEncore']:
								continue
							try:
								htscore = match['scores'][0]
								atscore = match['scores'][1]
							except IndexError:
								htscore = None
								atscore = None
							await conn.execute("UPDATE athena.matches SET htname=$1, htscore=$2, atname=$3, atscore=$4, htshort=$5, atshort=$6, status=$7, startdate=$9, week_number=$10 WHERE id = $8;", match["competitors"][0]["name"], htscore, match["competitors"][1]["name"], atscore, match["competitors"][0]["abbreviatedName"], match["competitors"][1]["abbreviatedName"], match["status"], mIndex, datetime.datetime.fromtimestamp(match["startDate"]/1000.0), n)
							atid = await conn.fetchrow("Select id from athena.teams WHERE team_name = $1;", match["competitors"][0]["name"])
							htid = await conn.fetchrow("Select id from athena.teams WHERE team_name = $1;", match["competitors"][1]["name"])
							for i in pickem['predictions']:
								if i['matchup_id'] >= 534:
									try:
										if i['homecard_id'] == htid["id"] and i['awaycard_id'] == atid["id"]:
											check = await conn.fetchrow("SELECT exists (SELECT matchup_id FROM athena.matches WHERE matchup_id = $1 LIMIT 1);", i['matchup_id'])
											if not check['exists']:
												matchupID = i['matchup_id']
												await conn.execute("UPDATE athena.matches SET matchup_id = $1 WHERE id=$2 AND matchup_id IS NULL;", matchupID, mIndex)
									except Exception as e:
										#print(e)
										pass
							if match["status"] == 'CONCLUDED':
								preds = await conn.fetch(queries.PAIDOUT, mIndex)
								stocks = await conn.fetch("SELECT teamshort, currentprice, updatedprice, highprice, lowprice, ticker FROM economy.market WHERE teamshort=$1 OR teamshort=$2 ORDER BY teamshort;", match["competitors"][0]["abbreviatedName"], match["competitors"][1]["abbreviatedName"])
								historycheck = await conn.fetch("SELECT teamshort, note FROM economy.history WHERE note LIKE '%' || $1 ||'%';", str(mIndex))
								if len(historycheck) > 0:
									pass
								else:
									if htscore > atscore:
										winner = match["competitors"][0]["abbreviatedName"]
										loser = match["competitors"][1]["abbreviatedName"]
										score = atscore
									else:
										winner = match["competitors"][1]["abbreviatedName"]
										loser = match["competitors"][0]["abbreviatedName"]
										score = htscore
									
									match score:
										case 0:
											percent = (0.05)
										case 1:
											percent = (0.04) 
										case 2:
											percent = (0.02)

									await self.stock.insertMarket(conn, stocks, winner, loser, percent, f"Match Result for ID {mIndex}", datetime.datetime.fromtimestamp(match["startDate"]/1000.0))
									
								for p in preds:
									if p['indicator'] == 'm':
										await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, 500, p['user_id'], datetime.datetime.now(), "Correct Maps Prediction")
									elif p['indicator'] == 'w':
										await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, 250, p['user_id'], datetime.datetime.now(), "Correct Winner Prediction")

									await conn.execute("UPDATE athena.predictions SET paidout = TRUE WHERE id = $1", p['pred_id'])
								
								await self.economy.updateAccounts([p['user_id'] for p in preds], conn)
							mIndex += 1
							count += 1
						
		print(f"Updated {count} matches")


	async def pollMatches(self, all=None):

		startTime = time.time()


		#OWL API
		api = f'https://us.api.blizzard.com/owl/v1/owl2?access_token={self.token}'
		response = requests.get(api)
		while response.status_code == 401:
			await self.get_token()
			api = f'https://us.api.blizzard.com/owl/v1/owl2?access_token={self.token}'
			response = requests.get(api)

		
		items = json.loads(response.text)

		#PICKEM API
		currentseason = str(datetime.datetime.now().year)
		pickems = []
		response = requests.get("https://pickem.overwatchleague.com/api/seasons")
		seasons = json.loads(response.text)
		now = datetime.datetime.utcnow().isoformat(' ', 'seconds')
		for item in seasons:
			if item['name'] == currentseason:
				for s in item['stages']:
					#get all the pickem matches related to the current season
					response = requests.get(f"https://pickem.overwatchleague.com/api/events?season={currentseason}&stage={s['slug']}")
					pickemmatches = json.loads(response.text)
					for pickem in pickemmatches:
						if pickem['slug'] == "crystal":
							continue
						pickems += pickem['matchups']

		
		async with self.bot.db.acquire() as conn:
			#Stages and Matches
			print("Getting matches")
			stages = items["segments"]
			for s in stages.items():
				stage = s[1]
				stageyear = stage['seasonId']
				if all != None:
					if all != stageyear:
						continue
					elif all == "all":
						pass
					
				sid = stage["id"]
				try:
					end = stage['lastMatchStart']
				except KeyError:
					continue
				
				if all == None:
					now = int(((datetime.datetime.utcnow() - timedelta(hours=48)) - datetime.datetime(1970, 1, 1)).total_seconds() * 1000)
					if end < now:
						continue
				
				stagereq = f"https://us.api.blizzard.com/owl/v1/segments/{sid}?access_token={self.token}"
				res = requests.get(stagereq)
				stagetext = json.loads(res.text)
				matches = stagetext['matches']

				if len(matches) > 0:
					async with conn.transaction():
						count = 0
						for m in matches.items():
							try:
								match = m[1]
								id = match['id']
								season = int(match['seasonId'])
								state = match['state']
								stagename = s[0]
								#for all, add a flag to input
								start = match['startTimestamp']
								end = match['endTimestamp']
								startweek =  int(((datetime.datetime.utcnow() - timedelta(days=7)) - datetime.datetime(1970, 1, 1)).total_seconds() * 1000)
								endweek = int(((datetime.datetime.utcnow() + timedelta(days=7)) - datetime.datetime(1970, 1, 1)).total_seconds() * 1000)
								
								if all == None:
									if not (startweek < start < endweek):
										continue

								teams = list(match['teams'].keys())
								dbteams = await conn.fetch("SELECT id, name, code, pickem_id FROM stats.teams ORDER BY name ASC;")
								try:
									t1 = teams[0]
								except IndexError:
									continue
								try:
									t1score = match['teams'][t1]['score']
								except KeyError:
									if state != 'pending':
										t1score = 0
									else:
										t1score = None
								try:
									t2 = teams[1]
								except IndexError:
									t2 = "TBD"
								try:
									t2score = match['teams'][t2]['score']
								except KeyError:
									if state != 'pending':
										t2score = 0
									else:
										t2score = None

								t1flag = False
								t2flag = False
								for t in dbteams:
									if t1flag and t2flag:
										break
									if str(t['id']) == t1:
										t1 = t['name']
										t1short = t['code']
										t1pick = t['pickem_id']
										try:
											if t['id'] == match['winner']:
												winner = t1short
										except KeyError:
											winner = None
										t1flag = True
									elif str(t['id']) == t2:
										t2 = t['name']
										t2short = t['code']
										t2pick = t['pickem_id']
										try:
											if t['id'] == match['winner']:
												winner = t2short
										except KeyError:
											winner = None
										t2flag = True
									
								
								if t1 == teams[0]:
									t1 = "TBD"
									t1short = "TBD"
									t1pick = None
									winner = None
								
								if t2 == "TBD" or t2 == teams[1]:
									t2 = "TBD"
									t2short = "TBD"
									t2pick = None
									winner = None


								#Get pickem id
								pickemid = None
								if len(pickems) > 0:
									for p in pickems:
										
										if pickemid != None:
											break

										ht = p['homecard_id']
										at = p['awaycard_id']
										starttimestamp = datetime.datetime.utcfromtimestamp((start / 1000))
										pickemtime = datetime.datetime.strptime(p['start_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
										if t1pick == ht and t2pick == at:
											if (starttimestamp - timedelta(minutes=60)) < pickemtime < (starttimestamp + timedelta(minutes=60)):
												pickemid = int(p['id'])
												break
										elif t2pick == ht and t1pick ==at:
											if (starttimestamp - timedelta(minutes=60)) < pickemtime < (starttimestamp + timedelta(minutes=60)):
												pickemid = int(p['id'])
												break
										else:
											continue
										
										

								check = await conn.fetchrow("SELECT exists (SELECT id FROM stats.matches WHERE id = $1 LIMIT 1);", id)
								if not check['exists']:
									await conn.execute("INSERT INTO stats.matches VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14);",id, season, stagename, t1, t1short, t1score, t2, t2short, t2score, winner, start, end, state, pickemid)
								else:
									await conn.execute("UPDATE stats.matches SET htname=$2, htshort= $3, htscore=$4, atname=$5, atshort= $6, atscore=$7, winner=$8, state=$9, starttime=$10, endtime=$11, pickem_id=$12  WHERE id=$1;", id, t1, t1short, t1score, t2, t2short, t2score, winner, state, start, end, pickemid)
								
								#Payout preds and stocks
								preds = await conn.fetch(queries.PAIDOUT, id)
								stocks = await conn.fetch("SELECT teamshort, currentprice, updatedprice, highprice, lowprice, ticker FROM economy.market WHERE teamshort=$1 OR teamshort=$2 ORDER BY teamshort;",t1short, t2short)
								historycheck = await conn.fetch("SELECT teamshort, note FROM economy.history WHERE note LIKE '%' || $1 ||'%';", str(id))
								if len(historycheck) > 0:
									pass
								elif state != 'concluded':
									pass
								else:
									if winner == t1short:
										loser = t2short
										score = t2score
									elif winner == t2short:
										loser = t1short
										score = t1score
									
									match score:
										case 0:
											percent = (0.05)
										case 1:
											percent = (0.04) 
										case 2:
											percent = (0.02)
										case 3:
											percent = (0.01)

									await self.stock.insertMarket(conn, stocks, winner, loser, percent, f"Match Result for ID {id}", datetime.datetime.fromtimestamp(start/1000.0))
									
								for p in preds:
									if p['indicator'] == 'm':
										await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, 500, p['user_id'], datetime.datetime.now(), "Correct Maps Prediction")
									elif p['indicator'] == 'w':
										await conn.execute("INSERT INTO economy.transactions (sender_id, amount, reciever_id, date, notes) VALUES ($1, $2, $3, $4, $5);", 1, 250, p['user_id'], datetime.datetime.now(), "Correct Winner Prediction")

									await conn.execute("UPDATE athena.predictions SET paidout = TRUE WHERE id = $1", p['pred_id'])
								
								await self.economy.updateAccounts([p['user_id'] for p in preds], conn)
								count += 1
							except Exception as e:
								print("Exception: ", e)
								print("Type of error: ", type(e))
								print("Match Object: ", m)
								print("ending function!!!!")
								print(" ")
								continue
					print(f"Finished data for {sid}! Updated {count} rows!")

		endTime = time.time()
		finalTime = endTime - startTime
		#print(f"Updated {count} rows!")
		print(f"Done! This took {finalTime} seconds!")
			

	def cog_unload(self):
		self.poller.cancel()

	@tasks.loop(hours=1.0)
	async def poller(self):
		print("Starting to poll")
		await self.pollMatches()

	@poller.before_loop
	async def before_poller(self):
		await self.bot.wait_until_ready()

	@commands.command(name='refresh', hidden=True)
	@commands.has_permissions(ban_members=True)
	async def callPoller(self, ctx):
		msg = await ctx.send("Refreshing!")
		await self.pollMatches()
		await msg.edit(content="Finished refreshing!", delete_after=5)

	@commands.command(name='forcepoll', hidden=True)
	@commands.has_permissions(ban_members=True)
	async def forcePoll(self, ctx, all=None):
		msg = await ctx.send("Getting all data!")
		await self.pollMatches(all)
		await msg.edit(content="Finished refreshing!", delete_after=5)


	@commands.hybrid_command(name='owl')
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def owltimer(self, ctx: commands.context):
		'''Time remaining until the start of the Overwatch League Season'''
		# Hard Coded Date, Needs to be changed yearly
		startdate = datetime.datetime(2023, 4, 27, 19, 0, 0)
		now = datetime.datetime.utcnow()
		start = startdate - now
		days = start.days
		hours, remainder = divmod(start.seconds, 3600)
		minutes, seconds = divmod(remainder, 60)

		# Send message, future tense if difference is posititve, past tense if difference is negative
		# Season number is hard coded, needs to be updated yearly
		
		if start.total_seconds() > 0:
			await ctx.send(f"{int(days)} days, {int(hours)} hours, {int(minutes)} minutes, and {int(seconds)} seconds until Overwatch League Season 6!")
		else:
			start = now - startdate
			days = start.days
			hours, remainder = divmod(start.seconds, 3600)
			minutes, seconds = divmod(remainder, 60)
			await ctx.send(f"Overwatch League Season 6 started {int(days)} days, {int(hours)} hours, {int(minutes)} minutes, and {int(seconds)} seconds ago!")

	@commands.hybrid_command(name='oldschedule')
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def oldschedule(self, ctx: commands.context, team: str=None, day: str=None):
		'''Get this week's Overwatch League schedule'''
		customAbbreviations = {'cdh': 'CDH', 'hzs': 'HZS', 'hou': 'HOU', 'tor': 'TOR', 'bos': 'BOS', 'lve': 'VEG', 'veg': 'VEG', 'atl': 'ATL', 'dal': 'DAL', 'gla': 'GLA', 'gzc': 'GZC', 'dyn': 'DYN', 'ldn': 'LDN', 'shd': 'SHD', 'van': 'VAN', 'val': 'VAL', 'was': 'WAS', 'phi': 'PHI', 'fla': 'FLA', 'nye': 'NYE', 'sfs': 'SFS', 'lag': 'GLA', 'lav': 'VAL', 'nyc': 'NYE', 'nyxl': 'NYE', 'ny': 'NYE', 'df': 'DAL', 'dc': 'WAS', 'fuel': 'DAL', 'dallas': 'DAL', 'inf': 'INF', 'seoul inf': 'INF', 'infernal': 'INF', 'houston': 'HOU', 'outlaws': 'HOU', 'boston': 'BOS', 'uprising': 'BOS', 'excelsior': 'NYE', 'sf': 'SFS', 'shock': 'SFS', 'valiant': 'VAL', 'gladiators': 'GLA', 'florida': 'FLA', 'mayhem': 'FLA', 'shanghai': 'SHD', 'dragons': 'SHD', 'dyn': 'DYN', 'dynasty': 'DYN', 'london': 'LDN', 'spitfire': 'LDN', 'chengdu': 'CDH', 'hunters': 'CDH', 'hangzhou': 'HZS', 'spark': 'HZS', 'vegas': 'LVE', 'eternal': 'LVE', 'toronto': 'TOR', 'defiant': 'TOR', 'vancouver': 'VAN', 'titans': 'VAN', 'washington': 'WAS', 'justice': 'WAS', 'atlanta': 'ATL', 'reign': 'ATL', 'rain': 'ATL', 'guangzhou': 'GZC', 'charge': 'GZC', 'glads': 'GLA', 'flm': 'FLA', 'drm': 'DRM', 'dream': 'DRM', 'dreamers': 'DRM', 'o2': 'O2B', 'blast': 'O2B', 'o2b': 'O2B', 'sin': 'SPG', 'spg': 'SPG', 'prisa': 'SPG', 'sinprisa': 'SPG', 'rho': 'RHO', 'pan':'PAN', 'pkf': 'PKF', 'poker': 'PKF'}

		if team != None:
			try:
				day = int(team)
			except ValueError:
				try:
					team = customAbbreviations.get(team.lower())
				except KeyError:
					await ctx.send("Team not found!", delete_after=3)
				async with self.bot.db.acquire() as conn:
					matches = await conn.fetch("WITH currweek AS (SELECT matches.*, DATE_PART('doy', matches.startdate) AS day, DENSE_RANK() OVER(ORDER BY DATE_PART('week', matches.startdate)) AS rank FROM athena.matches WHERE week_number <= (SELECT MIN(week_number) FROM athena.weeks WHERE enddate > NOW()) AND (htshort = $1 OR atshort = $1)) SELECT * FROM currweek ORDER BY day, startdate;", team)
					timeunit = 'Week'
			else:
				async with self.bot.db.acquire() as conn:
					matches = await conn.fetch("WITH currweek AS (SELECT matches.*, DATE_PART('doy', matches.startdate) AS day, DENSE_RANK() OVER(ORDER BY DATE_PART('doy', matches.startdate)) AS rank FROM athena.matches WHERE week_number = (SELECT MIN(week_number) FROM athena.weeks WHERE enddate > NOW())) SELECT * FROM currweek ORDER BY day, startdate;")
					timeunit = 'Day'
		else:
			async with self.bot.db.acquire() as conn:
				matches = await conn.fetch("WITH currweek AS (SELECT matches.*, DATE_PART('doy', matches.startdate) AS day, DENSE_RANK() OVER(ORDER BY DATE_PART('doy', matches.startdate)) AS rank FROM athena.matches WHERE week_number = (SELECT MIN(week_number) FROM athena.weeks WHERE enddate > NOW())) SELECT * FROM currweek ORDER BY day, startdate;")
				timeunit = 'Day'

		if len(matches) <= 0:
			await ctx.send("There are no matches for the upcoming week!", delete_after=5)

		indexes = set([m["rank"] for m in matches])
		if day != None:
			try:
				day = int(day)
			except ValueError:
				await ctx.send("Invalid day", delete_after=3)
				return
		
			if day not in indexes:
				await ctx.send("Invalid day", delete_after=3)
				return
		
		nextup = -1
		count = 0
		embeds = []
		dayStamp = ""
		for i in range(len(indexes)):
			daystring = ""
			for m in matches[count:]:
				if m["rank"] == i + 1:
					dayStamp = m["startdate"]
					#switch this when working locally
					#times =  pytz.timezone("US/Eastern").fromutc(m["startdate"]).strftime("%#I:%M %p %Z") + " / " +  (m["startdate"].strftime("%#I:%M %p UTC"))
					#this is for prod
					times =  pytz.timezone("US/Eastern").fromutc(dayStamp).strftime("%-I:%M %p %Z") + " / " +  (dayStamp.strftime("%-I:%M %p UTC"))
					logo1 = discord.utils.get(self.bot.emojis, name=m["htshort"])
					logo2 = discord.utils.get(self.bot.emojis, name=m["atshort"])

					if logo1 == None:
						logo1 = discord.utils.get(self.bot.emojis, name="OWC")

					if logo2 == None:
						logo2 = discord.utils.get(self.bot.emojis, name="OWC")
					
					if m['htscore'] != None:
						if m['htscore'] > m['atscore']:
							daystring += f"*{times}*\n{logo1} **{m['htname']}** ||**{m['htscore']}** - {m['atscore']}|| **{m['atname']}** {logo2}\n\n"
						else:
							daystring += f"*{times}*\n{logo1} **{m['htname']}** ||{m['htscore']} - **{m['atscore']}**|| **{m['atname']}** {logo2}\n\n"
					else:
						daystring += f"*{times}*\n{logo1} **{m['htname']}** vs **{m['atname']}** {logo2}\n\n"

					if nextup == -1 and m['status'] != "CONCLUDED":
						nextup = i

					count += 1
				else:
					break

			embeds.append(helpers.Page({'embed': discord.Embed(title=f"{dayStamp.strftime('%A, %B %e')} - {timeunit} {i + 1} of {max(indexes)}", description=daystring, colour=0xff8900)}))
		if day != None:
			currSort = day - 1
		else:
			currSort = nextup
		
		#await response.send_message(**embeds[currSort].msg)
		choices = await ctx.send(**embeds[currSort].msg)


		if len(embeds) > 1:
			#await interaction.edit_original_message(view=helpers.Pagnation(currSort, embeds, interaction, wraps=False))
			await choices.edit(view=helpers.Pagnation(currSort, embeds, choices, wraps=False))

	@commands.hybrid_command(name='schedule')
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def schedule(self, ctx: commands.context, team: str=None):
		#TODO: 
		# Create Dropdown that has weeks, schedule shows matches from that week
		# Add back team filtering
		# Link to match details function

		async with self.bot.db.acquire() as conn:
			#FOR NOW GOING 7 DAYS BACK, BE SURE TO CHANGE THIS LATER
			matches = await conn.fetch(queries.CURRENTWEEK)
			timeunit = "Day"

			if len(matches) <= 0:
				# WE WANT TO SHOW NEXT WEEK'S MATCHES
				#await ctx.send("There are no matches for the upcoming week!", delete_after=5)
				matches = await conn.fetch(queries.NEXTWEEK)

		indexes = set([m["rank"] for m in matches])

		
		nextup = -1
		count = 0
		embeds = []
		dayStamp = ""
		for i in range(len(indexes)):
			daystring = ""
			for m in matches[count:]:
				if m["rank"] == i + 1:
					dayStamp = int(m["starttime"] / 1000)
					times = f"<t:{dayStamp}:F>"
					logo1 = discord.utils.get(self.bot.emojis, name=m["htshort"])
					logo2 = discord.utils.get(self.bot.emojis, name=m["atshort"])

					if logo1 == None:
						logo1 = discord.utils.get(self.bot.emojis, name="OWC")

					if logo2 == None:
						logo2 = discord.utils.get(self.bot.emojis, name="OWC")
					
					if m['htscore'] != None:
						if m['htscore'] > m['atscore']:
							daystring += f"*{times}*\n{logo1} **{m['htname']}** ||**{m['htscore']}** - {m['atscore']}|| **{m['atname']}** {logo2}\n\n"
						else:
							daystring += f"*{times}*\n{logo1} **{m['htname']}** ||{m['htscore']} - **{m['atscore']}**|| **{m['atname']}** {logo2}\n\n"
					else:
						daystring += f"*{times}*\n{logo1} **{m['htname']}** vs **{m['atname']}** {logo2}\n\n"

					if nextup == -1 and m['state'] != "CONCLUDED":
						nextup = i

					count += 1
				else:
					break

			embeds.append(helpers.Page({'embed': discord.Embed(title=f"{datetime.datetime.fromtimestamp(dayStamp).strftime('%A, %B %e')} - {timeunit} {i + 1} of {max(indexes)}", description=daystring, colour=0xff8900)}))
			currSort = nextup
		
		#await response.send_message(**embeds[currSort].msg)
		choices = await ctx.send(**embeds[currSort].msg)


		if len(embeds) > 1:
			#await interaction.edit_original_message(view=helpers.Pagnation(currSort, embeds, interaction, wraps=False))
			await choices.edit(view=helpers.Pagnation(currSort, embeds, choices, wraps=False))

	@commands.hybrid_command(name='match')
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def matchdetails (self, ctx:commands.context, team1: str=None, team2: str=None):
		#This will need an input, making in none for now
		#Do we use a picture generator here, or do we do it all via discord like we've been?
		
		#Default screen should show match score, and map scores. Maybe vote on potm. Need to hit match api
		#Image needs to create shapes instead of a template. Should be dynamic based on number of played maps
		#experiment with pillow

		  
		print("Matches weee")

	@commands.hybrid_command(name='standings')
	@app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
	async def standings(self, ctx: commands.context, event: str=None):
		'''Get the current standings of the Overwatch League'''
		
		# At some point, we should look to add a dropdown. This can probably be done after the Kickoff Clash
		#events = {'kickoffclash': 'Kickoff Clash', 'kickoff': 'Kickoff Clash', 'clash': 'Kickoff Clash', 'kc': 'Kickoff Clash', 'kick': 'Kickoff Clash', 'midseasonmadness': 'Midseason Madness', 'mid': 'Midseason Madness', 'midseason':'Midseason Madness', 'mad': 'Midseason Madness', 'madness': 'Midseason Madness', 'mm': 'Midseason Madness', 'summershowdown': "Summer Showdown", 'summer': "Summer Showdown", 'showdown': "Summer Showdown", 'ss': "Summer Showdown", 'countdowncup': "Countdown Cup", 'countdown': "Countdown Cup", 'cup': "Countdown Cup", 'cc': "Countdown Cup", 'playoffs': "Playoffs"}
		# events = {'springstage': 'Spring Stage', 'spring': 'Spring Stage', 'spr': 'Spring Stage', 'midseasonmadness': 'Midseason Madness', 'mid': 'Midseason Madness', 'midseason':'Midseason Madness', 'mad': 'Midseason Madness', 'madness': 'Midseason Madness', 'mm': 'Midseason Madness', 'summerstage': "Summer Stage", 'summer': "Summer Stage", 'sum': "Summer Stage", 'playoffs': "Postseason","postseason": "Postseason","post": "Postseason"}
		# if event != None:
		# 	if event.lower() in events:
		# 		event = events.get(event)
		# 	else:
		# 		event = '2023 Regular Season'
		# else:
		# 	event = '2023 Regular Season'
		
		#get current segments from regular api (in future, use DB for this)
		#get standings based on what user provides (probably need mapping, but default to regular season) with standings api
		#iterate through divisions, to get standings

		

		event = "2023 Regular Season"
		embed = discord.Embed(title = f"Standings for the {event}", description="Loading...")
		msg= await ctx.send(embed=embed)

		#THIS SECTION NEEDS TO EVENTUALLY BE MOVED TO POLLING.
		sp = '\U0000202F'
		api = f'https://us.api.blizzard.com/owl/v1/owl2?access_token={self.token}'
		response = requests.get(api)
		while response.status_code == 401:
			await self.get_token()
			api = f'https://us.api.blizzard.com/owl/v1/owl2?access_token={self.token}'
			response = requests.get(api)

		items = json.loads(response.text)
		embedString = ''

		currentsegments = items['currentSegments']

		#for right now, default to regular season
		for seg in currentsegments:
			#in future, this should iterate so that it checks to match user input
			segment = seg.replace("ow2", "")
			if segment == "regular":
				currentseg = seg
			else:
				currentseg = "owl2-2023-regular"
			
		standapi =f'https://us.api.blizzard.com/owl/v1/segments/{currentseg}?access_token={self.token}'
		response = requests.get(standapi)
		standitems = json.loads(response.text)

		divisions = standitems['divisions']
		for div in divisions:
			division = div
			embedString += f'**{division.upper()}**\n'
			embedString +=f"__`{'Rank':{sp}^{2}}`__ __`{'Team':{sp}^{8}}`__ __`{'Record':{sp}^{8}}`__ __`{'Diff':{sp}^{3}}`__\n"
			for stand in standitems["standings"]:
				if stand['divisions'].get(div) != None:
					teamname = [i[1]['code'] for i in items['teams'].items() if str(i[0])==str(stand['teamId'])][0]
					teamlogo = discord.utils.get(self.bot.emojis, name=teamname)
					rank = stand['divisions'][division]["rank"]
					wins = stand['matchWins']
					losses = stand['matchLosses']
					diff = stand['gameDifferential']
					if diff > 0:
						diff = "+" + str(diff)
					embedString += f"`{str(rank) + '.':{sp}^{4}}` {teamlogo} `{teamname:{sp}^{5}}` `{str(wins) + '-' + str(losses):{sp}^{8}}` `{diff:{sp}^{4}}`\n"
			embedString += '\n'
					
		embed = discord.Embed(title = f"Standings for the {event}", description=embedString, colour=0xff8900)
		await msg.edit(embed=embed)

async def setup(bot):
	await bot.add_cog(OwlCog(bot))
