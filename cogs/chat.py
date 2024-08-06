from ast import arguments
from types import MemberDescriptorType
from typing import Optional
from urllib import response
import discord
import asyncio
import asyncpg
from discord.errors import NotFound
from discord.ext import commands, tasks
from discord import app_commands
import time
import datetime
from datetime import timezone, timedelta
from discord.permissions import Permissions
from discord.ext.commands.cooldowns import BucketType
import random
import hashlib

from pandas import options
from resources import helpers, queries
import os
from collections import defaultdict
import pickle
import markovify
import re


emojiLetters = [
				"\N{REGIONAL INDICATOR SYMBOL LETTER A}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER B}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER C}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER D}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER E}", 
				"\N{REGIONAL INDICATOR SYMBOL LETTER F}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER G}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER H}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER I}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER J}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER K}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER L}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER M}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER N}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER O}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER P}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER Q}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER R}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER S}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER T}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER U}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER V}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER W}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER X}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER Y}",
				"\N{REGIONAL INDICATOR SYMBOL LETTER Z}"
			]


class Dropdown(discord.ui.Select):
	def __init__(self, options, text, response, args):
		super().__init__(placeholder=text, min_values=1, max_values=1, options=options)
		self.args: dict = args
		self.response = response

	async def callback(self, interaction: discord.Interaction):
		if isinstance(self.response, str):
			await interaction.response.send_message(self.response)
		elif callable(self.response):
			for item, value in self.args.items():
				if isinstance(value, MemberDescriptorType):
					if value.__name__ == 'user':
						self.args[item] = interaction.user
					elif value.__name__ == 'data':
						self.args[item] = interaction.data['values'][0]
			
			await self.response(**self.args)
		else:
			return

class DView(discord.ui.View):
	def __init__(self, dropdowns):
		super().__init__()

	# Adds the dropdown to our view object.
		for drop in dropdowns:
			self.add_item(drop)


class RandomButton(discord.ui.Button):
	def __init__(self, user=None, resend=False):
		super().__init__(style=discord.ButtonStyle.secondary, emoji='\U0001F504', row=0)
		self.user = user
		self.resend = resend


	async def callback(self, interaction: discord.Interaction):
		assert self.view is not None
		if self.view.owner and interaction.user != self.view.owner:
			return

		asyncio.ensure_future(self.view.pages[self.view.index].setProp('embed', 'randomStar', kwargs={'user': self.user}, resend=self.resend))


class ChatCog(commands.Cog):
	"""Commands relating to chat functions"""

	def __init__(self, bot):
		self.bot = bot
		self.polls = set()
		self.monitored = set()
		self.emotechans = set()
		self.emoteusers = set()
		self.emotes = set()
		self.breakouts = {}
		self.raffles = []



	class Entry:
		def __init__(self, bot, msg, choices):
				self.bot = bot
				self.msg = msg
				self.choices = choices
		
		async def addPoll(self, user):
			self.msg = await self.msg.channel.fetch_message(self.msg.id)
			reacted = []
			for i in self.msg.reactions:
				users = await i.users().flatten()
				for item in users:
					if item.id ==user.id:
						reacted.append(i.emoji)
			if len(reacted) > 1:
				emoji = random.choice(reacted)
			elif len(reacted) == 0:
				return
			else:
				emoji = reacted[0]
			
			choice = self.choices[emojiLetters.index(emoji)]
			async with self.bot.db.acquire() as conn:
				await conn.execute("DELETE FROM temppoll WHERE name = $1", user.name)
				await conn.execute("INSERT INTO temppoll VALUES ($1, $2, $3);", user.name, choice, emoji)
	

	@commands.command(name='assignrole')
	@commands.has_permissions(ban_members=True)
	async def assign_role(self, ctx):
		#TODO: 
		# Figure out how to send interaction object to dropdown (so it remains modular)
		dropdowns = []
		dropdowns2 = []

		owlroles2 = {
			"name": "Secondary Overwatch League Roles", "ATL": "ATL", "BOS": "BOS", "CDH" : "CDH", "DAL": "DAL", "FLA" : "FLA", 
			"GZC": "GZC", "HZS": "HZS", "HOU": "HOU", "LDN": "LDN", "LAG": "GLA", "LAV": "VAL", "NYXL": "NYE", "PAR": "PAR", 
			"PHI": "PHI", "SFS": "SFS", "SEO": "SEO", "SHD": "SHD", "TOR": "TOR", "VAN": "VAN", "WAS": "WAS"
			}
		owlroles = {
			"name": "Primary Overwatch League Roles", "Atlanta Reign": "ATL", "Boston Uprising": "BOS", "Chengdu Hunters" : "CDH", "Dallas Fuel": "DAL", 
			"Florida Mayhem" : "FLA", "Guangzhou Charge": "GZC", "Hangzhou Spark": "HZS", "Houston Outlaws": "HOU", "London Spitfire": "LDN", 
			"Los Angeles Gladiators": "GLA", "Los Angeles Valiant": "VAL", "New York Excelsior": "NYE", "Paris Eternal": "PAR", "Philadelphia Fusion": "PHI", 
			"San Francisco Shock": "SFS", "Seoul Dynasty": "SEO", "Shanghai Dragons": "SHD", "Toronto Defiant": "TOR", "Vancouver Titans": "VAN", "Washington Justice": "WAS"
			}
		tier2 = {"name": "Tier 2 Roles", "Support T2/T3": "empty", "United States": "empty", "Element Mystic": "empty", "Runaway": "empty", 
			"O2 Blast": "empty", "Team Doge": "empty", "British Hurricane": "empty", "Team CC": "empty", "Mindfreak": "empty", "Dignity": "empty"
			}	
		newspings = {"name": "News Notification Roles", "OWL-News": "OWL", "Game-News": "OW", "All-Notify": "empty"}
		matchpings = {"name": "Match Notification Roles", "OWL-Notify": "OWL", "KRContenders": "flag_kr", "NAContenders": "flag_us", "EUContenders": "flag_eu", "AUContenders": "flag_au", "All-Matches": "empty", "All-Notify": "empty"}
		misc = {"name": "Miscellaneous Roles", "newcomer": "empty", "He/Him": "empty", "She/Her": "empty", "They/Them": "empty", "A Political": "empty"}

		lists = [owlroles, owlroles2, newspings, matchpings, tier2, misc]

		roles = ctx.guild.roles
		roles.reverse()
		for item in lists:
			options = []
			for role in roles:
				name = item["name"]
				if str(role) not in item:
					pass
				else:
					emoji = discord.utils.get(self.bot.emojis, name=item[str(role)])
					o = discord.SelectOption(label = str(role), emoji = emoji)
					options.append(o)

			
			drop = Dropdown(options, name, self.give_role, {"ctx": ctx, "member": discord.Interaction.user, "role": discord.Interaction.data})
			if len(dropdowns) < 5:
				dropdowns.append(drop)
			else:
				dropdowns2.append(drop)


		view = DView(dropdowns)
		try:
			await ctx.send("Choose a role:", view=view)
		except discord.errors.HTTPException as e:
			print(e)
			await ctx.send("No Roles Found")
			return

		if len(dropdowns2) > 0:
			view2 = DView(dropdowns2)
			await ctx.send("<:empty:776582076581150721>", view=view2)


	@commands.command(name='handmadebirds', aliases = ['hm', 'hmb', 'handmade'], hidden = True)
	@commands.has_permissions(ban_members=True)
	async def handmadebirds(self, ctx):
		await ctx.message.delete()
		bothook = discord.utils.get(await ctx.channel.webhooks(), name="Athena")
		if bothook == None:
			if len(self.bothooks[ctx.guild.id]) < 3:
				bothook = await ctx.channel.create_webhook(name="Athena")
			else:
				bothook = self.bothooks[ctx.guild.id][0]
				await bothook.edit(reason="Getting this man Handmade's @", channel=ctx.channel)

		handmade = await commands.UserConverter().convert(ctx, "286165861084168192")
		await bothook.send(content=f"`{handmade.mention}`", username=self.bot.user.name, avatar_url=self.bot.user.display_avatar.url, ephemeral=True)

	@commands.command(name='rule')
	@commands.has_permissions(ban_members=True)
	async def rule(self, ctx, number):
		channel = self.bot.get_channel(831798874670235678)
		#channel = self.bot.get_channel(350798346203561984)

		messages = await channel.history(limit=20).flatten()

		messages.reverse()

		for i, message in enumerate(messages):
			if f"**{number}.**" in message.content:
				await ctx.send(message.content)

	async def give_role(self, ctx, member, role):
		role = discord.utils.get(ctx.guild.roles, name=role)
		if role in member.roles:
			await member.remove_roles(role)
			return
		else:
			try:
				await member.add_roles(role)
			except AttributeError:
				await ctx.send("Role not found", delete_after=5)
				return
	
	@commands.command(name='temprole')
	@commands.has_permissions(ban_members=True)
	async def temprole(self, ctx, user, role, time):
		try:
			user = await commands.UserConverter().convert(ctx, user)
			member = ctx.guild.get_member(user.id)
		except commands.BadArgument:
			await ctx.send("User not found", delete_after=5)
			return
		units= {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
		sec = int(time[:-1]) * units[time[-1]]
		await self.give_role(ctx, member, role)
		await ctx.send(f'{user} has been given the role of {role} for {time}')
		await asyncio.sleep(sec)
		role = discord.utils.get(ctx.guild.roles, name=role)
		await member.remove_roles(role)
		
	@commands.command(name='emotemode')
	@commands.has_permissions(ban_members=True)
	async def emotemode(self, ctx, username=None):
		if username == None:
			if ctx.message.channel.id in self.emotechans:
				self.emotechans.discard(ctx.message.channel.id)
				await ctx.send("Emotemode Disabled")
			else:
				self.emotechans.add(ctx.message.channel.id)
				await ctx.send("<:Jarboy:1190771883726086224>")
		else:	
			try:
				userObj = await commands.MemberConverter().convert(ctx, username)
			except commands.BadArgument:
				await ctx.send("User not found")
				return
			
			if userObj.guild_permissions.ban_members:
				await ctx.send("Cannot place mods into emotemode")
				return

			if userObj.id in self.emoteusers:
				self.emoteusers.discard(userObj.id)
				await ctx.send(f"{userObj.name} is no longer in emotemode <:DEADAF:1206117964839911474>")
			else:
				self.emoteusers.add(userObj.id)
				await ctx.send(f"{userObj.name} is now in emotemode <:WICKED:808063832060461067>")
		
	@commands.command(name='poll')
	@commands.has_permissions(ban_members=True)
	async def poll(self, ctx, time, question, *choices):
		if len(self.monitored) > 0:
			await ctx.send("There is currently another poll active! ")
			return
		units= {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
		try:
			sec = int(time[:-1]) * units[time[-1]]
		except ValueError:
			await ctx.send("Incorrect Time unit. Please try again!")
			return

		async with self.bot.db.acquire() as conn:
			color = await helpers.getColor(conn, ctx.author.id)

			try:
				await conn.execute("CREATE TEMPORARY TABLE temppoll (name VARCHAR, choice VARCHAR, emoji TEXT);")
			except asyncpg.DuplicateTableError:
				await conn.execute("DROP TABLE temppoll")

		tempembed = discord.Embed(title=question, description="Loading...", colour=color)
		msg = await ctx.send(embed=tempembed)
		embedstr = ' '
		index = 0

		for choice in choices:
			embedstr += f'{emojiLetters[index]}   {choice}\n'
			await msg.add_reaction(emojiLetters[index])
			index += 1

		embed = discord.Embed(title=question, description=embedstr, colour=color)
		await msg.edit(embed = embed)
		self.polls.add(self.Entry(self.bot, msg, choices))
		self.monitored.add(msg.id)
		await asyncio.sleep(sec)
		await self.endpoll(ctx)
		
	@commands.command(name='endpoll', aliases=['ep'])
	@commands.has_permissions(ban_members=True)
	async def endpoll(self, ctx):
		try:
			msg = await ctx.fetch_message(self.monitored.pop())
		except discord.NotFound or KeyError:
			await ctx.send("No polls are currently running!")
			return
		except:
			await ctx.send("Unable to end polls!")
			return

		async with self.bot.db.acquire() as conn:
			await msg.clear_reactions()
			title = msg.embeds[0].title
			embedstr = ''
			pollresponses = await conn.fetch("SELECT * FROM temppoll;")
			pollcounts = await conn.fetch("SELECT choice, emoji, count(choice) from temppoll GROUP BY choice, emoji ORDER BY count desc")
			color = await helpers.getColor(conn, ctx.author.id)

			for i in pollcounts:
				embedstr += f"{i[1]}  {i[0]} : {i[2]}\n"
			embed = discord.Embed(title=title, description = embedstr, colour=color)
			await ctx.send(embed=embed)
			await conn.execute("DROP TABLE temppoll")
			self.polls.pop()

	async def getUserStarpost(self, user=None):
		async with self.bot.db.acquire() as conn:
			if user:
				newrandompost = await conn.fetchrow(queries.RANDOMSTARPOST, user.id)
			else:
				newrandompost = await conn.fetchrow(queries.ALLUSERRANDOMSTARPOST)

			newrandomchan = self.bot.get_channel(newrandompost['channel'])
			return await self.starboard(
						await newrandomchan.fetch_message(newrandompost['message']),
						conn,
						title=f"Random Starboard Post (⭐ {newrandompost['count']})"
					)
	
	async def starboard(self, message, conn, title=None, uniquebutton=None):
		username = str(message.author.id)
		#xchan = discord.utils.get(message.guild.channels, name="starboard")
		if title is None:
			title = ""

		messageContent = message.content

		color = await helpers.getColor(self.bot, username)

		embed = discord.Embed(title=title, description=messageContent, color=color)
		if message.embeds:
			em = message.embeds[0].to_dict()
			if 'twitter.com' in em['url'] or 'x.com' in em['url']:
				messageContent = f'{messageContent} \n\n {em["description"]}'
				embed = discord.Embed(title=title, description=messageContent, color=color)
				try:
					embed.set_image(url=em['image']['proxy_url'])
				except KeyError:
					pass
			elif 'youtube.com' in em['url']:
				embed.set_image(url=em['thumbnail']['proxy_url'])
			elif em['url'].lower().split('?')[0].endswith('gif'):
				embed.set_image(url=em['thumbnail']['proxy_url'])
			elif 'tenor.com' in em['url']:
				gifid = em['thumbnail']['url'].split('/')[3]
				gifid = gifid[:-1]
				gifid = gifid + 'C'
				url = f'https://c.tenor.com/{gifid}/tenor.gif'
				embed.set_image(url=url)
			else:
				pass
		
		if message.attachments:
			file = message.attachments[0]
			split = file.url.lower().split('?', 1)[0]
			if split.endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
				embed.set_image(url=file.url)
			else:
				embed.add_field(name='Attachment', value=f'[{file.filename}]({file.url})', inline=False)
	   
		embed.add_field(name="\u200b", value=f'[→Jump to original message]({message.jump_url})')
		embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.with_format('png'))
		embed.set_footer(text=message.created_at.strftime('%x'))
		
		# try:
		#	msg = await xchan.send(f'⭐ {count}  {channel.mention}', embed=embed)
		# except:
		#	msg = await xchan.send(message.content)
		if uniquebutton != None:
			return embed, uniquebutton
		else:
			return embed

	@commands.command(name='starstats', aliases=['star', 'stars'])
	async def starstats(self, ctx, who=None):
		if who != None:
			try:
				user = await commands.UserConverter().convert(ctx, who)
			except commands.BadArgument:
				await ctx.send("User not found")
				return
		else:
			user = ctx.author

		async with self.bot.db.acquire() as conn:
			items = await conn.fetchrow(queries.STARSTATS, user.id)
			if not items:
				await ctx.send("Unable to find star stats for this user!", delete_after=5)
				return

			randompost = await conn.fetchrow(queries.RANDOMSTARPOST, user.id)
			try:
				randomchan = self.bot.get_channel(randompost['channel'])
			except IndexError:
				await ctx.send("Unable to find star stats for this user!", delete_after=5)
				return

			starboardcount = await conn.fetchrow(queries.STARBOARDCOUNT)
			topstarpost = await conn.fetchrow(queries.TOPSTARPOST, user.id)
			topchan = self.bot.get_channel(topstarpost['channel'])
			averagestars = items['averagestars']
			numstarposts = items['count']
			maxstars = items['max']
			totalrecieved = items['totalrecieved']
			perstarboard = round(((numstarposts / starboardcount['count']) * 100),2)
			description = f"Average Stars Recieved: {averagestars} \n Number of Posts on Starboard: {numstarposts} \n Most Stars Recieved: {maxstars} \n Total Amount of Stars Recieved: {totalrecieved} \n Percent of posts on Starboard: {perstarboard}%"
			
			

			embeds = []
			embeds.append(helpers.Page({'embed': discord.Embed(title=f"**{user.name}**'s Star Stats", description=description)}))

			embeds.append(helpers.Page({'embed': await self.starboard(await randomchan.fetch_message(randompost['message']), conn, title=f"Random Starboard post by {user.name} (⭐ {randompost['count']})")}, buttons=[RandomButton(user=user)], funcs={'randomStar': self.getUserStarpost}))
			
			embeds.append(helpers.Page({'embed': await self.starboard(
						await topchan.fetch_message(topstarpost['message']),
						conn,
						title=f"{user.name}'s top starred post (⭐ {topstarpost['max']})"
					)}))

		currSort = 0
		choices = await ctx.send(**embeds[currSort].msg)
		await choices.edit(view=helpers.Pagnation(currSort, embeds, choices, wraps=False))

	@commands.command(name='starpost', aliases=['sp'])
	async def randomStar(self, ctx):

		async with self.bot.db.acquire() as conn:
			randompost = await conn.fetchrow(queries.ALLUSERRANDOMSTARPOST)
			try:
				randomchan = self.bot.get_channel(randompost['channel'])
			except IndexError:
				await ctx.send("Unable to find star stats for this user!", delete_after=5)
				return


			embed = (await self.starboard(
								await randomchan.fetch_message(randompost['message']),
								conn,
								title=f"Random Starboard post (⭐ {randompost['count']})"
							))

		embed = (helpers.Page({'embed': await self.starboard(await randomchan.fetch_message(randompost['message']), conn, title=f"Random Starboard Post (⭐ {randompost['count']})")}, buttons=[RandomButton(resend=True)], funcs={'randomStar': self.getUserStarpost}))


		currSort = 0
		choices = await ctx.send(**embed.msg)
		await choices.edit(view=helpers.Pagnation(currSort, [embed], choices, wraps=True))
		
	@commands.command(name="raffle")
	@commands.has_permissions(ban_members=True)
	async def raffle(self, ctx, time, title="Raffle"):
		async with self.bot.db.acquire() as conn:
			color = await helpers.getColor(conn, ctx.author.id)

		embed = discord.Embed(title = title, description = "Click on the reaction below to join the raffle!", color = color)
		msg = await ctx.send(embed=embed)
		await msg.add_reaction("\U00002705")
		self.monitored.add(msg.id)
		units= {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
		sec = int(time[:-1]) * units[time[-1]]
		await asyncio.sleep(sec)
		await msg.clear_reactions()
		finalchoice = random.choice(self.raffles)
		await ctx.send(f"The winner of the raffle is {finalchoice.mention}")
		self.monitored.remove(msg.id) 
	
	@commands.command(name="lock")
	@commands.has_permissions(ban_members=True)
	async def lock(self, ctx, time=None):
		channel = ctx.channel
		#xchan = discord.utils.get(message.guild.channels, name=channel.name)
		await channel.send("Channel lockdown initalized.")
		if channel.name == "politics":
			role = discord.utils.get(ctx.guild.roles, name='A Political')
		else:
			role = ctx.guild.default_role
		overwrite = channel.overwrites_for(role)
		overwrite.send_messages = False
		await channel.set_permissions(role, overwrite = overwrite)
		if time != None:
			units= {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
			sec = int(time[:-1]) * units[time[-1]]
			await asyncio.sleep(sec)
			await channel.send("Channel unlock initalized.")
			await self.unlock(ctx)

	@commands.command(name="unlock")
	@commands.has_permissions(ban_members=True)
	async def unlock(self, ctx):
		channel = ctx.channel
		#xchan = discord.utils.get(message.guild.channels, name=channel.name)
		await channel.send("Channel unlock initalized.")
		if channel.name == "politics":
			role = discord.utils.get(ctx.message.guild.roles, name='A Political')
		else:
			role = ctx.guild.default_role
		overwrite = channel.overwrites_for(role)
		overwrite.send_messages = None
		await channel.set_permissions(role, overwrite = overwrite)	

	@commands.command(name='broadcast')
	@commands.has_permissions(ban_members=True)
	async def broadcast(self, ctx:commands.Context, channel, *, message):
		chan = discord.utils.get(ctx.guild.channels, name=channel)
		if chan == None:
			await ctx.send("Unable to find channel!", delete_after=5)
			return
		await chan.send(message)

	@commands.command(name='editbroadcast')
	@commands.has_permissions(ban_members=True)
	async def editbroadcast(self, ctx:commands.Context, msgid, *, message):
		msg = await ctx.fetch_message(msgid)
		await msg.edit(message)

	@commands.command(name='lfg')
	@commands.has_permissions(ban_members=True)
	async def lfg(self, ctx:commands.Context):
		await ctx.send("Our LFG channel has been shut down due to inactivity. We would like to redirect you to OverwatchLFG, a discord server dedicated towards finding groups for ranked. If you know any other large servers that also server this purpose, please let us know in ⁠#server-suggestions and we'll consider adding them to the list.\n\ndiscord.gg/overwatchlfg",delete_after=15)

	
	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		if payload.user_id == self.bot.user.id:
			return

		
		if payload.emoji.name == "\U00002705":
			if payload.message_id in self.monitored:
				member = self.bot.get_user(payload.user_id)
				if member not in self.raffles:
					self.raffles.append(member)
		

		if payload.emoji.name in emojiLetters:
			if payload.message_id in self.monitored:
				member = self.bot.get_user(payload.user_id)
				for i in self.polls:
					await i.addPoll(member)
		
		if payload.emoji.name == "\U00002B50":
			msg = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
			star = [reaction for reaction in msg.reactions if reaction.emoji == '⭐']
			channel = self.bot.get_channel(payload.channel_id)
			starchannel = discord.utils.get(msg.guild.channels, name="starboard")
			timestamp = datetime.datetime.now()
			if star[0].count >= 6:
				async with self.bot.db.acquire() as conn:
					async with conn.transaction():
						message = await conn.fetchrow("SELECT boardmsg FROM discord.starboard where message=$1", payload.message_id)
						if message == None:
							embed = await self.starboard(msg, channel)
							try:
								bmsg = await starchannel.send(f'⭐ {star[0].count}  {channel.mention}', embed=embed)
							except:
								bmsg = await starchannel.send(message.content)
							
							boardid = bmsg.id
							await conn.execute("INSERT into discord.starboard VALUES ($1, $2, $3, $4, $5, $6)", payload.message_id, msg.author.id, payload.channel_id, star[0].count, boardid, timestamp)
						else:
							msgid = message[0]
							try:
								nmsg=await starchannel.fetch_message(msgid)
								await nmsg.edit(content=f'⭐ {star[0].count}  {channel.mention}')
								await conn.execute("UPDATE discord.starboard set count = $4 WHERE message=$1 and author = $2 and channel = $3 and boardmsg = $5", payload.message_id, msg.author.id, payload.channel_id, star[0].count, msgid)
							except discord.NotFound:
								embed = await self.starboard(msg, channel)
								try:
									bmsg = await starchannel.send(f'⭐ {star[0].count}  {channel.mention}', embed=embed)
								except:
									bmsg = await starchannel.send(message.content)
								
								boardid = bmsg.id
								await conn.execute("UPDATE discord.starboard SET count = $4, boardmsg = $5, timestamp = $6 WHERE message=$1 and author = $2 and channel = $3", payload.message_id, msg.author.id, payload.channel_id, star[0].count, boardid, timestamp)
				
	@commands.Cog.listener()
	async def on_raw_reaction_remove(self, payload):
		if payload.emoji.name == "\U00002B50":
			msg = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
			star = [reaction for reaction in msg.reactions if reaction.emoji == '⭐']
			channel = self.bot.get_channel(payload.channel_id)
			starchannel = discord.utils.get(msg.guild.channels, name="starboard")
			async with self.bot.db.acquire() as conn:
				if len(star) < 1 or star[0].count < 6:
					if len(star) == 0 :
						count = 0
					else:
						count = star[0].count

					async with conn.transaction():
						message = await conn.fetchrow("SELECT boardmsg FROM discord.starboard where message=$1", payload.message_id)
						if message != None:
							msgid = message[0]
							msg=await starchannel.fetch_message(msgid)
							await conn.execute("UPDATE discord.starboard set count = $4 WHERE message=$1 and author = $2 and channel = $3 and boardmsg = $5", payload.message_id, msg.author.id, payload.channel_id, count, msgid)
							await msg.delete()

				elif star[0].count >= 6:
					async with conn.transaction():
						message = await conn.fetchrow("SELECT boardmsg FROM discord.starboard where message=$1", payload.message_id)
						if message != None:
							msgid = message[0]
							nmsg=await starchannel.fetch_message(msgid)
							await nmsg.edit(content=f'⭐ {star[0].count}  {channel.mention}')
							await conn.execute("UPDATE discord.starboard set count = $4 WHERE message=$1 and author = $2 and channel = $3 and boardmsg = $5", payload.message_id, msg.author.id, payload.channel_id, star[0].count, msgid)

	@commands.Cog.listener()
	async def on_message(self, message):
		if isinstance(message.channel, discord.DMChannel) and message.author.id not in {143730443777343488, 136594603829755904}:
			return

		#if message.channel.name in {"general", "overwatch", "ow-esports", "other-games", "other-esports", "sports", "anime", "creative", "music", "politics"}:
		#	return

		if message.author == self.bot.user:
			return
		
		#Server-Suggestions
		if not isinstance(message.channel, discord.DMChannel) and message.channel.name == "server-suggestions":
				username = str(message.author.id)
				xchan = discord.utils.get(message.guild.channels, name="suggestions-backend")

				messageContent = message.content
				m = hashlib.md5()
				m.update(username.encode('utf-8'))
				colour = int(f"0x{m.hexdigest()[7:13]}", 0)

				embed = discord.Embed(title="", description=message.content, color=colour)
				embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.with_format('png'))
				embed.set_footer(text=message.created_at.strftime('%x - %X'))
				logMsg = f'Crossposted {message.author} at {datetime.datetime.now().strftime("%X on %x")}'


				if message.attachments:
					file = message.attachments[0]
					if file.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
						embed.set_image(url=file.url)
					else:
						embed.add_field(name='Attachment', value=f'[{file.filename}]({file.url})', inline=False)
				
				try:
					await xchan.send(embed=embed)
				except:
					await xchan.send(message.content)
				
				await asyncio.sleep(.5)
				await message.delete()
				print(logMsg)

		#assign-role
		if not isinstance(message.channel, discord.DMChannel) and message.channel.name == "assign-role":
			await asyncio.sleep(15)
			try:
				await message.delete()
			except discord.NotFound:
				pass
		
		#lft
		if not isinstance(message.channel, discord.DMChannel) and message.channel.name == "looking-for-team":
			if message.author.id == self.bot.user.id:
				return
			xchan = discord.utils.get(message.guild.channels, name="looking-for-team")
			messageContent = message.content
			if "LFT" not in messageContent or '```' in messageContent:
				await xchan.send(f"{message.author.mention} This message does not have the right formatting for this channel! Please make sure all messages in this channel use 'LFT' and are not in a codeblock!", delete_after=5)
				try:
					await message.delete()
				except discord.NotFound:
					pass
			elif messageContent.count('\n') > 20:
				await xchan.send(f"{message.author.mention} This message is too long for this channel! Please make sure all messages have a maximum of 20 lines!", delete_after=5)
				try:
					await message.delete()
				except discord.NotFound:
					pass
			elif messageContent.count('\n\n') > 2:
				await xchan.send(f"{message.author.mention} This message has too many uses of whitespace in between paragraphs! Please make sure to only use a maximum of 2 uses of whitespace between paragraphs!", delete_after=5)
				try:
					await message.delete()
				except discord.NotFound:
					pass
			else:
				pass
		
		#lfp
		if not isinstance(message.channel, discord.DMChannel) and message.channel.name == "looking-for-players":
			if message.author.id == self.bot.user.id:
				return
			xchan = discord.utils.get(message.guild.channels, name="looking-for-players")
			messageContent = message.content
			if "LFP" not in messageContent or '```' in messageContent:
				await xchan.send(f"{message.author.mention} This message does not have the right formatting for this channel! Please make sure all messages in this channel use 'LFP' and are not in a codeblock!", delete_after=5)
				try:
					await message.delete()
				except discord.NotFound:
					pass
			elif messageContent.count('\n') > 20:
				await xchan.send(f"{message.author.mention} This message is too long for this channel! Please make sure all messages have a maximum of 20 lines!", delete_after=5)
				try:
					await message.delete()
				except discord.NotFound:
					pass
			elif messageContent.count('\n\n') > 2:
				await xchan.send(f"{message.author.mention} This message has too many uses of whitespace in between paragraphs! Please make sure to only use a maximum of 2 uses of whitespace between paragraphs!", delete_after=5)
				try:
					await message.delete()
				except discord.NotFound:
					pass
			else:
				pass

		#community-content
		if not isinstance(message.channel, discord.DMChannel) and message.channel.name == "community-content":
			if message.author.id == self.bot.user.id:
				return
			xchan = discord.utils.get(message.guild.channels, name="community-content")
			messageContent = message.content

			if 'twitch.tv/' in messageContent:
				await xchan.send(f"{message.author.mention} Please post twitch streams in{discord.utils.get(message.guild.channels, name='streams').mention}!", delete_after=10)
				try:
					await message.delete()
				except discord.NotFound:
					pass   
		
		#mod-vote
		if not isinstance(message.channel, discord.DMChannel) and message.channel.name == "mod-vote":
			if message.author.id == self.bot.user.id:
				return
			await message.add_reaction("\U0001F44D")
			await message.add_reaction("\U0001F590")
			await message.add_reaction("\U0001F44E")
			
			
		#Athena shut it down
		if message.content.lower() == "athena shut it down" and message.author.guild_permissions.ban_members:
			await self.lock(message)

		#Athena open it up
		if message.content.lower() == "athena open it up" and message.author.guild_permissions.ban_members:
			await self.unlock(message)

		#word filters
		word_filter = ['https://twitter.com/Halofthoghts']
		if [word for word in word_filter if (word.lower() in message.content.lower())] and not message.author.guild_permissions.ban_members:
			await message.delete()
			
			
		if message.channel.id in self.emotechans:
			ctx = await self.bot.get_context(message)
			if not (ctx.author.guild_permissions.ban_members) and not (helpers.emoteParse(message.content)) or (message.attachments or message.embeds):
				await message.delete()

		if message.author.id in self.emoteusers:
			if not (helpers.emoteParse(message.content)) or (message.attachments or message.embeds):
				await message.delete()

		if message.author.id == 404434658890088451:
			await message.channel.send("soup")
		
		# await self.bot.process_commands(message)
		
	@commands.Cog.listener()
	async def on_message_edit(self, before, after):
		if after.channel.id in self.emotechans:
			ctx = await self.bot.get_context(after)
			if not (ctx.author.guild_permissions.ban_members) and not (helpers.emoteParse(after.content)) or (after.attachments or after.embeds):
				await after.delete()

		if after.author.id in self.emoteusers:
			if not (helpers.emoteParse(after.content)) or (after.attachments or after.embeds):
				await after.delete()

async def setup(bot):
	await bot.add_cog(ChatCog(bot))
