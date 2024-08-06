import discord
import asyncio
import asyncpg
from discord.ext import commands
import json
import requests
from bs4 import BeautifulSoup
from zipfile import ZipFile
from io import BytesIO
import pandas as pd
import os
from resources import helpers, queries
import pickle


TOKEN = os.getenv('TOKEN')
DBPASS = os.getenv('DBPASS')
DBHOST = os.getenv('DBHOST')
DBUSER= os.getenv('DBUSER')

abbreviations = {'DAL': 'Dallas Fuel', 'PHI': 'Philadelphia Fusion', 'HOU': 'Houston Outlaws', 'BOS': 'Boston Uprising', 'NYE': 'New York Excelsior', 'SFS': 'San Francisco Shock', 'VAL': 'Los Angeles Valiant', 'GLA': 'Los Angeles Gladiators', 'FLA': 'Florida Mayhem', 'SHD': 'Shanghai Dragons', 'SEO': 'Seoul Dynasty', 'LDN': 'London Spitfire', 'CDH': 'Chengdu Hunters', 'HZS': 'Hangzhou Spark', 'PAR': 'Paris Eternal', 'TOR': 'Toronto Defiant', 'VAN': 'Vancouver Titans', 'WAS': 'Washington Justice', 'ATL': 'Atlanta Reign', 'GZC': 'Guangzhou Charge'}
customAbbreviations = {'cdh': 'CDH', 'hzs': 'HZS', 'hou': 'HOU', 'tor': 'TOR', 'bos': 'BOS', 'par': 'PAR', 'atl': 'ATL', 'dal': 'DAL', 'gla': 'GLA', 'gzc': 'GZC', 'seo': 'SEO', 'ldn': 'LDN', 'shd': 'SHD', 'van': 'VAN', 'val': 'VAL', 'was': 'WAS', 'phi': 'PHI', 'fla': 'FLA', 'nye': 'NYE', 'sfs': 'SFS', 'lag': 'GLA', 'lav': 'VAL', 'nyc': 'NYE', 'nyxl': 'NYE', 'ny': 'NYE', 'df': 'DAL', 'dc': 'WAS', 'fuel': 'DAL', 'dallas': 'DAL', 'philly': 'PHI', 'philadelphia': 'PHI', 'fusion': 'PHI', 'houston': 'HOU', 'outlaws': 'HOU', 'boston': 'BOS', 'uprising': 'BOS', 'excelsior': 'NYE', 'sf': 'SFS', 'shock': 'SFS', 'valiant': 'VAL', 'gladiators': 'GLA', 'florida': 'FLA', 'mayhem': 'FLA', 'shanghai': 'SHD', 'dragons': 'SHD', 'seoul': 'SEO', 'dynasty': 'SHD', 'london': 'LDN', 'spitfire': 'LDN', 'chengdu': 'CDH', 'hunters': 'CDH', 'hangzhou': 'HZS', 'spark': 'HZS', 'paris': 'PAR', 'eternal': 'PAR', 'toronto': 'TOR', 'defiant': 'TOR', 'vancouver': 'VAN', 'titans': 'VAN', 'washington': 'WAS', 'justice': 'WAS', 'atlanta': 'ATL', 'reign': 'ATL', 'rain': 'ATL', 'guangzhou': 'GZC', 'charge': 'GZC', 'glads': 'GLA', 'flm': 'FLA'}

# Add whatever to these, we can be generous with aliasing as long as they aren't confusing or ambiguous
abbrevs = {'CDH', 'HZS', 'HOU', 'TOR', 'BOS', 'PAR', 'ATL', 'DAL', 'GLA', 'GZC', 'SEO', 'LDN', 'SHD', 'VAN', 'VAL', 'WAS', 'PHI', 'FLA', 'NYE', 'SFS'}
shortNames =  {'Dallas Fuel': 'Dallas Fuel', 'Philadelphia Fusion': 'Philly Fusion', 'Houston Outlaws': 'Houston Outlaws', 'Boston Uprising': 'Boston Uprising', 'New York Excelsior': 'NY Excelsior', 'San Francisco Shock': 'SF Shock', 'Los Angeles Valiant': 'LA Valiant', 'Los Angeles Gladiators': 'LA Gladiators', 'Florida Mayhem': 'Florida Mayhem', 'Shanghai Dragons': 'Shanghai Dragons', 'Seoul Dynasty': 'Seoul Dynasty', 'London Spitfire': 'London Spitfire', 'Chengdu Hunters': 'Chengdu Hunters', 'Hangzhou Spark': 'Hangzhou Spark', 'Paris Eternal': 'Paris Eternal', 'Toronto Defiant': 'Toronto Defiant', 'Vancouver Titans': 'Vancouver Titans', 'Washington Justice': 'Washington Justice', 'Atlanta Reign': 'Atlanta Reign', 'Guangzhou Charge': 'Guangzhou Charge'}



class StatsCog(commands.Cog):
    """Commands relating to the Overwatch League and various different stats pulled from the StatsLab."""

    def __init__(self, bot):
        self.bot = bot
        self.token = ''
        #asyncio.ensure_future(self.addDB())
    
    async def filter(ctx):
        command = ctx.command.name
        aliases = ctx.command.aliases
        chan = ctx.message.channel.name
        pkl = open("resources/commands.pkl", 'rb')
        banned_commands = pickle.load(pkl)
        if command in banned_commands[chan] or any(item in banned_commands[chan] for item in aliases):
            return False
        else:
            return True

    async def get_token(self):
        #need to change this to use env variables
        data = { 'grant_type': 'client_credentials' }
        response = requests.post('https://us.battle.net/oauth/token', data=data, auth=('b63fd0741ed448b4a1dadf78bfe0a185', 'Mu409VfwMmlc4dcR9rYLw9abunhp7JhF'))
        token = json.loads(response.text)
        self.token = token['access_token']

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
    
    class query:
        async def get_map_stats(self, conn, year, teamname, maptype):
            self.wins = await conn.fetchrow(queries.MAPSTATWINS, year, teamname, maptype)
            self.loss = await conn.fetchrow(queries.MAPSTATLOSS, year, teamname, maptype)
            return self.wins, self.loss
        
        async def get_stat(self, conn, year, playername, statname, heroname = 'All Heroes'):
            stat = await conn.fetchrow(queries.STAT, year, playername, statname, heroname)
            
            try:
                number = stat[0]
                rank = stat[1]
            except TypeError:
                number = 0
                rank = 0
            
            return number, rank

    @commands.command(name="stats")
    #need to use command groups for this. look at how the store does it
    async def stats(self, ctx, playername, year=2021, hero=None):
        """ 
        Commands to find stats from the Overwatch League.
        Syntax is ~stats [player/team] [year] [hero]
        Parameters:
        player/team: This lets you look at the stats for either a specific player or an entire team. Team abbreviations are allowed. Player names are not case sensative but do require the proper spelling (ex. Violet must be Viol2t.) 

        year: Optional. Defaults to 2021. Filters the stats by year. 

        hero: Optional. Defaults to All Heroes. Filters the stats to a specific hero. (Not compatible with Team)
        
        """
        tembed = discord.Embed(title=f'Stats', description='Loading...', colour=0xff8900)

        queryobj = StatsCog
        async with self.bot.db.acquire() as conn:
            try:
                teamname = abbreviations[await StatsCog.CustomAbb().convert(ctx, playername)]
                msg = await ctx.send(embed=tembed)

                async with conn.transaction():
                    wins = await conn.fetchrow(queries.STATWIN, year, teamname)
                    losses = await conn.fetchrow(queries.STATLOSS, year, teamname)

                    teaminfo = await conn.fetchrow("""
                        select * from stats.teaminfo where team_name = $1
                        """, teamname)

                    try:
                        win = wins[0]
                        rank = wins[1]
                    except TypeError:
                        win = 0
                        if losses[0] == 0:
                            rank = 0
                        else:
                            rank = 20

                    

                    control = await queryobj.query.get_map_stats(self, conn, year, teamname, 'CONTROL')
                    contwins= control[0]['count']
                    contloss= control[1]['count']
                    try:
                        contper = contwins / (contwins + contloss)
                    except ZeroDivisionError:
                        if contwins == 0:
                            contper= 0
                        else:
                            contper=1

                    escort = await queryobj.query.get_map_stats(self, conn, year, teamname, 'PAYLOAD')
                    escwins = escort[0]['count']
                    escloss = escort[1]['count']
                    try:
                        escper = escwins / (escwins + escloss)
                    except ZeroDivisionError:
                        if escwins == 0:
                            escper= 0
                        else:
                            escper = 1

                    assault = await queryobj.query.get_map_stats(self, conn, year, teamname, 'ASSAULT')
                    asswins = assault[0]['count']
                    assloss = assault[1]['count']
                    try:
                        assper = asswins / (asswins + assloss)
                    except ZeroDivisionError:
                        if asswins == 0:
                            assper = 0
                        else:
                            assper = 1

                    hybrid = await queryobj.query.get_map_stats(self, conn, year, teamname, 'HYBRID')
                    hybwins = hybrid[0]['count']
                    hybloss = hybrid[1]['count']
                    try:
                        hybper = hybwins / (hybwins + hybloss)
                    except ZeroDivisionError:
                        if hybwins == 0:
                            hybper= 0
                        else:
                            hybper = 1

                    map5wins = await conn.fetchrow(queries.MAP5WINS, year, teamname)
                    map5loss = await conn.fetchrow(queries.MAP5LOSS, year, teamname)
                    map5wins = map5wins['count']
                    map5loss = map5loss['count']
                    try:
                        map5per = map5wins / (map5wins + map5loss)
                    except ZeroDivisionError:
                        if map5wins == 0:
                            map5per= 0
                        else:
                            map5per = 1

                    name = teaminfo[0]
                    div = teaminfo[1]
                    image = teaminfo[2]
                    color = int(teaminfo[3].decode('utf-8'), 16)

                    embedstring = f'Division:**{div}**\n {year} Record: **{win}-{losses[0]} (Rank {rank})** \n\n **__Control Record:__**\n{contwins}-{contloss} ({int(contper* 100)}%)\n **__Escort Record:__**\n{escwins}-{escloss} ({int(escper* 100)}%)\n **__Assault Record:__**\n{asswins}-{assloss} ({int(assper* 100)}%)\n **__Hybrid Record:__**\n{hybwins}-{hybloss} ({int(hybper* 100)}%)\n **__Map 5 Record:__**\n{map5wins}-{map5loss} ({int(map5per* 100)}%)'
                    title = f"Team info for {name}"

            except commands.BadArgument:
                async with conn.transaction():
                    try:
                        info = await conn.fetchrow("SELECT * from stats.playerinfo where lower(name) = $1 and rosteryear = $2", playername.lower(), year)
                        name = info[0]
                        realname = info[1]
                        image = info[2]
                        team = info[3]
                        role = info[4]
                    except KeyError or TypeError:
                        await ctx.send("Player or Team not found!", delete_after = 5)
                        return
                
                    msg = await ctx.send(embed=tembed)
                    try:
                        heroquery = await conn.fetchrow("""
                                        select hero_name, SUM(stat_amount) AS playtime from stats.player_stats where lower(player_name) = $1 and stat_name = 'Time Played' 
                                        and hero_name != 'All Heroes' and EXTRACT(year from start_time) = $2 GROUP BY hero_name ORDER BY playtime DESC LIMIT 1""", playername.lower(), year)
                        bestHero = heroquery[0]
                        playtime = str(round(heroquery[1]/3600,2))
                    except TypeError:
                        bestHero = "Not Found"
                        playtime = 0
                    
                    embedstring = f"""Real Name: **{realname}** \n Role: **{role}** \n Team: **{team}**\n Most Played Hero ({year}): **{bestHero} ({playtime} hours)**\n"""
                    title = f"Stats for {name}"
                    colorq = await conn.fetchrow("""
                        select team_color from stats.teaminfo where team_name = $1
                        """, team)
                    color = int(colorq[0].decode('utf-8'), 16)
                    
                    if role == "Damage" or role == "Offense":
                        finalblows = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Final Blows')
                        elims = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Eliminations')
                        damage = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Hero Damage Done')
                        solokills = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Solo Kills')
                        deaths = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Deaths')
                        embedstring += f"""
                                        **__Final Blows Per 10:__**\n{round(finalblows[0],2)} (Ranked {finalblows[1]})
                                        **__Eliminations Per 10:__**\n{round(elims[0],2)} (Ranked {elims[1]})
                                        **__Damage Done Per 10:__**\n{round(damage[0], 2)} (Ranked {damage[1]})
                                        **__Solo Kills Per 10:__**\n{round(solokills[0],2)} (Ranked {solokills[1]})
                                        **__Deaths Per 10:__**\n{round(deaths[0],2)} (Ranked {deaths[1]})"""

                    elif role == "Tank":
                        taken = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Damage Taken')
                        elims = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Eliminations')
                        damage = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Hero Damage Done')
                        blocked = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Damage Blocked')
                        deaths = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Deaths')
                        embedstring += f"""
                                        **__Damage Taken Per 10:__**\n{round(taken[0], 2)} (Ranked {taken[1]})
                                        **__Eliminations Per 10:__**\n{round(elims[0], 2)} (Ranked {elims[1]})
                                        **__Damage Done Per 10:__**\n{round(damage[0], 2)} (Ranked {damage[1]})
                                        **__Damage Blocked Per 10:__**\n{round(blocked[0],2)} (Ranked {blocked[1]})
                                        **__Deaths Per 10:__**\n{round(deaths[0],2)} (Ranked {deaths[1]})"""

                    elif role == "Support":
                        healing = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Healing Done')
                        elims = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Eliminations')
                        taken = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Damage Taken')
                        assists = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Assists')
                        deaths = await queryobj.query.get_stat(self, conn, year, playername.lower(), 'Deaths')
                        embedstring += f"""
                                        **__Healing Done Per 10:__**\n{round(healing[0], 2)} (Ranked {healing[1]})
                                        **__Eliminations Per 10:__**\n{round(elims[0], 2)} (Ranked {elims[1]})
                                        **__Damage Taken Per 10:__**\n{round(taken[0], 2)} (Ranked {taken[1]})
                                        **__Assists Per 10:__**\n{round(assists[0],2)} (Ranked {assists[1]})
                                        **__Deaths Per 10:__**\n{round(deaths[0],2)} (Ranked {deaths[1]})""" 
                    else:
                        await ctx.send("Role not found!", delete_after=5)
                        return
 

        embed = discord.Embed(title=title, description=embedstring, colour=color)
        embed.set_thumbnail(url=image)
        await msg.edit(embed=embed)

    @commands.command(name="statsleaderboard", aliases = ['statslb', 'slb'])
    async def statsleaderboard(self, ctx, statname, year=2021, hero=None):
        """
        A leaderboard of players on a specific stat. 
        Syntax is ~slb [statname] [year] [hero(Optional)]

        """

        sp = '\U0000202F'
        tb = '\U00002001'
        if hero == None:
            hero= "All Heroes"

        async with self.bot.db.acquire() as conn:
            records = await conn.fetch(queries.STATLB, year, hero, statname)
            
        try:
            ml=max(len(p['player_name']) for p in records)
            rl = len(f"{len(records)}.")
            wl = max(len(str(round(p['per10'], 2))) for p in records)
        except ValueError:
            await ctx.send("Unable to fetch leaderboard (Remember that everything is case sensitive!") 
            return

        embeds = []
        i = 0
        page = 1

        while i < len(records):
            leaderboardString = f"__`{'Name':{sp}^{rl + ml + 3}}`__\uFEFF__`{ 'Amount':{sp}<{wl}}`__\n"    
            j = 0
            while j < 10 and i < len(records):
                r = records[i]
                leaderboardString += f"`{str(i + 1) + '.':{sp}<{rl}}`\uFEFF**`{r['player_name']:{sp}<{ml}}{tb * 2}`**\uFEFF`{round(r['per10'], 2):{sp}<{wl + 1}}`\n"
                j += 1
                i += 1
            embeds.append(discord.Embed(title=f"{statname} per 10 ({page}/{(int(len(records) / 10)) + (int(len(records) % 10 > 0))})", description=leaderboardString, colour=0xff8900))
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
                                ], return_when=asyncio.FIRST_COMPLETED, timeout=122)
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

    @commands.command(name="statslist", aliases = ['statsl', 'sl'])
    async def statslist(self, ctx, hero=None):
        sp = '\U0000202F'
        tb = '\U00002001'
        if hero == None:
            hero = "all heroes"
        
        async with self.bot.db.acquire() as conn:
            async with conn.transaction():
                normalstats = await conn.fetch(queries.STATLIST, "All Heroes".lower())
                normalstats = [p["stat_name"] for p in normalstats]
                
                
                records = await conn.fetch(queries.STATLIST, hero.lower())
                stats = [p["stat_name"] for p in records if p['stat_name'] not in normalstats]
                try:
                    hero = records[0]['hero_name']
                except IndexError:
                    await ctx.send("Unable to find hero")
                    return

        
        try:
            ml=max(len(p) for p in stats)
            rl = len(f"{len(stats)}.")
        except ValueError:
            await ctx.send("Unable to fetch stats") 
            return
        embeds = []
        i = 0
        page = 1
        
        while i < len(stats):
            leaderboardString = f"__`{'Name':{sp}^{rl + ml + 3}}`__\n"    
            j = 0
            while j < 10 and i < len(stats):
                r = stats[i]
                leaderboardString += f"`{str(i + 1) + '.':{sp}<{rl}}`\uFEFF**`{r:{sp}<{ml}}{tb * 2}`**\uFEFF\n"
                j += 1
                i += 1
            embeds.append(discord.Embed(title=f"{hero} Unique Stats ({page}/{(int(len(records) / 10)) + (int(len(records) % 10 > 0))})", description=leaderboardString, colour=0xff8900))
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
                                ], return_when=asyncio.FIRST_COMPLETED, timeout=122)
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

    @commands.command(name='team', aliases = ['roster'])
    async def roster(self, ctx, teamname, year=2022):
        try:
            teamname = abbreviations[await StatsCog.CustomAbb().convert(ctx, teamname)]
        except commands.BadArgument:
            await ctx.send("Team not found!", delete_after = 5)
            return
        
        async with self.bot.db.acquire() as conn:
            async with conn.transaction():
                query = await conn.fetch("""select playerinfo.name, playerinfo.real_name, playerinfo.role from stats.playerinfo where playerinfo.team_name = $1 and rosteryear = $2
                                                order by role, real_name""", teamname, year)
            
                wins = await conn.fetchrow(queries.STATWIN, year, teamname)
                losses = await conn.fetchrow(queries.STATLOSS, year, teamname)
                teaminfo = await conn.fetchrow("select * from stats.teaminfo where team_name = $1", teamname)

        div = teaminfo[1]
        image = teaminfo[2]
        color = teaminfo[3]

        try:
            win = wins[0]
            rank = wins[1]
        except TypeError:
            win = 0
            if losses[0] == 0:
                rank = 0
            else:
                rank = 20
        
            
        rosterstr = f'{year} Record: ** {win}-{losses[0]}  (Rank {rank}) ** \n Division: **{div}**\n\n'

        for i in query:
            namesplit = i['real_name'].split()
            try:
                firstname = namesplit[0]
                lastname = ' '.join(namesplit[1:])
            except IndexError:
                firstname = ' '
                lastname = ' '

            if i['role'] == "Damage" or i['role'] == "Offense":
                rosterstr += f'⚔️ {firstname} **"{i["name"]}"** {lastname}\n'
            elif i['role'] == "Support":
                rosterstr += f'💉 {firstname} **"{i["name"]}"** {lastname}\n'
            else:
                rosterstr += f'🛡️ {firstname} **"{i["name"]}"** {lastname}\n'

        
        embed = discord.Embed(title=f"Roster for {teamname}", description=rosterstr, colour=int(color.decode('utf-8'), 16))
        embed.set_thumbnail(url=image)
        await ctx.send(embed=embed) 


    @commands.command(name='updaterosters', hidden=True)
    @commands.has_permissions(ban_members=True)
    async def updaterosters(self, ctx):
        api = f'https://us.api.blizzard.com/owl/v1/owl2?access_token={self.token}'
        response = requests.get(api)
        while response.status_code == 401:
            await self.get_token()
            api = f'https://us.api.blizzard.com/owl/v1/owl2?access_token={self.token}'
            response = requests.get(api)

        

        items = json.loads(response.text)
        
        async with self.bot.db.acquire() as conn:
            #Teams
            print("Getting teams")
            teams = items["teams"]
            async with conn.transaction():
                for t in teams.items():
                    team = t[1]
                    try:
                        id= team['id']
                        name = team['name']
                        code = team['code']
                        logo = team['logo']
                        try:
                            primary_color = team['primaryColor']
                            secondary_color = team['secondaryColor']
                        except KeyError:
                            primary_color = "FA9C1D"
                            secondary_color = "4A4C4E"
                        check = await conn.fetchrow("SELECT exists (SELECT id FROM stats.teams WHERE id = $1 LIMIT 1);", id)
                        if not check['exists']:
                            await conn.execute("INSERT INTO stats.teams VALUES ($1, $2, $3, $4, $5, $6)", id, name, code, logo, primary_color, secondary_color)
                        else:	
                            await conn.execute("UPDATE stats.teams SET id=$1, name = $2, code=$3, logo=$4, primary_color=$5, secondary_color=$6 WHERE id=$1", id, name, code, logo, primary_color, secondary_color)
                    except KeyError as e:
                        print("Error with team: ", team)
                        print(e)
                        pass					
            
            #Players
            print("Getting players")
            players = items["players"]
            async with conn.transaction():
                for p in players.items():
                    try:
                        player = p[1]
                        id = player['id']
                        name = player['name']
                        number = player['number']
                        full_name = player['givenName'] + " " + player['familyName']
                        try:
                            role = player['role']
                        except KeyError:
                            role = None
                        current_team = await conn.fetchrow("SELECT name from stats.teams where id=$1", player['currentTeam'])
                        if current_team != None:
                            current_team = current_team["name"]
                        else:
                            current_team = None
                        try:
                            image = player['headshotUrl']
                        except KeyError:
                            image = "https://images.blz-contentstack.com/v3/assets/blt321317473c90505c/bltcdcb764c3287821b/601b44aa3689c30bf149261e/Generic_Player_Icon.png"
                        check = await conn.fetchrow("SELECT exists (SELECT id FROM stats.players WHERE id = $1 LIMIT 1);", id)
                        if not check['exists']:
                            await conn.execute("INSERT INTO stats.players VALUES ($1, $2, $3, $4, $5, $6, $7)", id, number, name, full_name, role, current_team, image)
                        else:
                            await conn.execute("UPDATE stats.players SET id=$1, number=$2, name=$3, full_name=$4, role=$5, current_team=$6, image=$7 WHERE id=$1", id, number, name, full_name, role, current_team, image)
                    except KeyError as e:
                        print("Error with player: ", player)
                        print(e)
                        pass
            print("Done!")
        # players = []
        # page = requests.get('https://overwatchleague.com/en-us/players')
        # soup = BeautifulSoup(page.text, 'html.parser')
        # data = json.loads(soup.find(name='script', id='__NEXT_DATA__').contents[0])
        # playerList = data['props']['pageProps']['blocks'][1]['playerList']['tableData']['data']
        # async with self.bot.db.acquire() as conn:
        #     async with conn.transaction():
        #         query = await conn.fetch("SELECT * FROM stats.playerinfo")
        #         added = []
        #         for player in playerList:
        #             if any(player['name'].lower() == i['name'].lower() for i in query):
        #                 realname = player['realName']
        #                 image = player['headshot']
        #                 await conn.execute('UPDATE stats.playerinfo SET image=$3, real_name=$4  where lower(name) = $1 and team_name = $2 and rostered = True', player['name'].lower(), player['teamName'], image, realname)
        #             else:
        #                 name = player['name']
        #                 added.append(name)
        #                 realname = player['realName']
        #                 image = player['headshot']
        #                 team = player['teamName']
        #                 role = player['role']
        #                 rostered = True
        #                 rosteryear = 2022
        #                 await conn.execute('INSERT INTO stats.playerinfo VALUES($1, $2, $3, $4, $5, $6, $7)', name, realname, image, team, role, rostered, rosteryear)
        #     await ctx.send("Players Updated! Added {}".format(added), delete_after = 5)

        
    @commands.command(name='updatestats', hidden=True)
    @commands.has_permissions(ban_members=True)
    async def updatestats(self, ctx):
        
        async with self.bot.db.acquire() as conn:
            matches = await conn.fetch("SELECT id from stats.matches;")
            matchlen = len(matches)
            print(f"Getting stats for {matchlen} matches!")
            index = 1
            teammap = {}
            for row in await conn.fetch("SELECT id, name FROM stats.teams;"):
                teammap[row["id"]] = row["name"]
            
            playermap = {}
            for row in await conn.fetch("SELECT id, name FROM stats.players;"):
                playermap[row["id"]] = row["name"]
            
            await conn.execute("CREATE TEMPORARY TABLE temp_stats (LIKE stats.playerstats INCLUDING CONSTRAINTS)")

            for match in matches:
                print(f"Getting match {index} of {matchlen}")

                api = f'https://us.api.blizzard.com/owl/v1/matches/{match["id"]}?access_token={self.token}'
                response = requests.get(api)
                while response.status_code == 401:
                    await self.get_token()
                    api = f'https://us.api.blizzard.com/owl/v1/matches/{match["id"]}?access_token={self.token}'
                    response = requests.get(api)

                items = json.loads(response.text)

                matchdf = pd.DataFrame(columns=["match_id", "map_id", "map_name", "map_type", "map_number", "team_name", "player_name", "hero_name", "stat_name", "stat_amount"])
                match_id = items['id']
                games = items['games']

                
                # Get overall team stats, then get player stats
                for g in games.items():
                    game = g[1]
                    if game['state'] != 'concluded':
                        continue
                    map_id = game['id']
                    map_name = game['map'].replace('-', " ").title()
                    map_type = game['mapType'].title()
                    map_number = game['number']
                    teams = game['teams']
                    players = game['players']
                    for t in teams.items():
                        team = t[1]
                        team_name = teammap[team['id']]
                        player_name = team_name
                        stats = team['teamStats']
                        hero_name = "Team Stats"
                        for stat in stats:
                            stat_name = ''.join([' ' + c if c.isupper() else c for c in stat]).split()
                            stat_name = ' '.join(stat_name).title()
                            stat_amount = stats[stat]
                            stat_row = [match_id, map_id, map_name, map_type, map_number, team_name, player_name, hero_name, stat_name, stat_amount]
                            matchdf = pd.concat([matchdf, pd.DataFrame([stat_row], columns=matchdf.columns)], ignore_index=True)
                            # check = await conn.fetchrow("SELECT exists(SELECT * FROM stats.playerstats WHERE match_id=$1 AND map_id=$2 AND team_name=$3 AND player_name=$4 AND hero_name=$5 AND stat_name=$6 AND stat_amount=$7);", 
                            #                             match_id, map_id, team_name, player_name, hero_name, stat_name, stat_amount)
                            # if not check['exists']:
                            #     await conn.execute("INSERT INTO stats.playerstats VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);", 
                            #                        match_id, map_id, map_name, map_type, map_number, team_name, player_name, hero_name, stat_name, stat_amount)

                    for p in players.items():
                        player = p[1]
                        team_name = teammap[int(player['teamId'])]
                        player_name = playermap[player['id']]
                        #All Heroes
                        for stat in player['stats']:
                            hero_name = "All Heroes"
                            stat_name = ''.join([' ' + c if c.isupper() else c for c in stat]).split()
                            stat_name = ' '.join(stat_name).title()
                            stat_amount = player['stats'][stat]
                            stat_row = [match_id, map_id, map_name, map_type, map_number, team_name, player_name, hero_name, stat_name, stat_amount]
                            matchdf = pd.concat([matchdf, pd.DataFrame([stat_row], columns=matchdf.columns)], ignore_index=True)
                            # check = await conn.fetchrow("SELECT exists(SELECT * FROM stats.playerstats WHERE match_id=$1 AND map_id=$2 AND team_name=$3 AND player_name=$4 AND hero_name=$5 AND stat_name=$6 AND stat_amount=$7);",
                            #                     match_id, map_id, team_name, player_name, hero_name, stat_name, stat_amount)
                            # if not check['exists']:
                            #     await conn.execute("INSERT INTO stats.playerstats VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);", 
                            #                        match_id, map_id, map_name, map_type, map_number, team_name, player_name, hero_name, stat_name, stat_amount)

                        #Individual
                        for hero in player['heroes'].items():
                            hero_name = hero[0].replace('-', " ").title()
                            statdic = hero[1]
                            for s in statdic:
                                stat_name = ''.join([' ' + c if c.isupper() else c for c in s]).split()
                                stat_name = ' '.join(stat_name).title()
                                stat_amount = statdic[s]
                                stat_row = [match_id, map_id, map_name, map_type, map_number, team_name, player_name, hero_name, stat_name, stat_amount]
                                matchdf = pd.concat([matchdf, pd.DataFrame([stat_row], columns=matchdf.columns)], ignore_index=True)
                                # check = await conn.fetchrow("SELECT exists(SELECT * FROM stats.playerstats WHERE match_id=$1 AND map_id=$2 AND team_name=$3 AND player_name=$4 AND hero_name=$5 AND stat_name=$6 AND stat_amount=$7);",
                                #                 match_id, map_id, team_name, player_name, hero_name, stat_name, stat_amount)
                                # if not check['exists']:
                                #     await conn.execute("INSERT INTO stats.playerstats VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);", 
                                #                        match_id, map_id, map_name, map_type, map_number, team_name, player_name, hero_name, stat_name, stat_amount)
                
                async with conn.transaction():
                    await conn.copy_records_to_table('temp_stats', records=matchdf.values.tolist(), columns=list(matchdf.columns))

                    await conn.execute(f"""
                        INSERT INTO stats.playerstats
                        SELECT *
                        FROM temp_stats t
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM stats.playerstats s
                            WHERE s.match_id = t.match_id
                            AND s.map_id = t.map_id
                            AND s.map_name = t.map_name
                            AND s.team_name = t.team_name
                            AND s.player_name = t.player_name
                            AND s.hero_name = t.hero_name
                            AND s.stat_name = t.stat_name
                            AND s.stat_amount = t.stat_amount
                        );
                    """)

                    await conn.execute("DELETE FROM temp_stats;")

                index += 1
            
            print("Stats gathered!")

    
    @commands.command(name='editplayer', hidden=True)
    @commands.has_permissions(ban_members=True)
    async def editplayer(self, ctx, playername, oldteamname, oldyear, newteam, newyear):
        try:
            oldteam = abbreviations[await StatsCog.CustomAbb().convert(ctx, oldteamname)]
            newteam = abbreviations[await StatsCog.CustomAbb().convert(ctx, newteam)]
        except commands.BadArgument:
            await ctx.send("Team not found!", delete_after = 5)
            return
        async with self.bot.db.acquire() as conn:
            async with conn.transaction():    
                await conn.execute("UPDATE stats.playerinfo SET team_name = $1, rosteryear=$2 WHERE lower(name) = $3 and team_name = $4 and rosteryear = $5", newteam, int(newyear), playername.lower(), oldteam, int(oldyear))
                query = await conn.fetchrow("SELECT * from stats.playerinfo where lower(name) = $1 and team_name=$2 and rosteryear=$3", playername.lower(), newteam, int(newyear))
                await ctx.send(query, delete_after=30)

    
    @commands.command(name='add', hidden=True)
    @commands.has_permissions(ban_members=True)
    async def addplayer(self, ctx, playername, team, role, rostered, year):
        if rostered=='true':
            rostered=True
        else:
            rostered=False

        try:
            team = abbreviations[await StatsCog.CustomAbb().convert(ctx, team)]
        except commands.BadArgument:
            await ctx.send("Team not found!", delete_after = 5)
            return
        async with self.bot.db.acquire() as conn:
            async with conn.transaction():  
                await conn.execute("INSERT INTO stats.playerinfo (name, team_name, role, rostered, rosteryear) VALUES ($1, $2, $3, $4, $5)", playername, team, role, rostered, int(year)) 
                await ctx.send ("Successfully added player!", delete_after=5)
 


async def setup(bot):
    await bot.add_cog(StatsCog(bot))
