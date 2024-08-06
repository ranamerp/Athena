import discord
import asyncio
import asyncpg
from discord import app_commands
from discord.ext import commands, tasks
import datetime
from datetime import time, timedelta
from discord.ext.commands.cooldowns import BucketType
from random import *
import os
from os.path import join, dirname
from dotenv import load_dotenv
from matplotlib.image import thumbnail
from resources import helpers
import numpy as np
import matplotlib.pyplot as plt
import io

sp = '\U0000202F'
class StockCog(commands.Cog):
    """Commands relating to the OWL Stock Market"""
    def __init__(self, bot):
        self.bot = bot
        self.updateMarket.start()

    async def insertMarket(self, conn, stocks, winner, loser, percent, note, date=None):
        for stock in stocks:
            if date==None:
                date = datetime.datetime.now()
            team = stock['teamshort']
            currentprice = stock['updatedprice']
            ticker = stock['ticker']
            if loser == team:
                price = currentprice - round(stock['updatedprice'] * percent, 2)
            elif winner == team:
                price = currentprice + round(stock['updatedprice'] * percent, 2)
            else:
                continue
            if ticker == 5:
                nextval = 0
            else:
                nextval = ticker + 1
            ticker = int(stock['ticker'])
            await conn.execute("UPDATE economy.market SET updatedprice=$1, lastupdated=$2, ticker=$4 WHERE teamshort=$3", price, datetime.datetime.now(), team, nextval)
            await conn.execute("INSERT INTO economy.history (teamshort, date, oldprice, volume, newprice, note) VALUES ($1, $2, $3, $4, $5, $6)", team, date, currentprice, 0, price, note)
            if ticker == 5:
                await self.currentmarket(conn, stock['currentprice'], team, stock['highprice'], stock['lowprice'])
            elif "Match Result" in note:
                await self.currentmarket(conn, price, team, stock['highprice'], stock['lowprice'], avgflag=False)
            else:
                continue

    async def currentmarket(self, conn, currentprice, team, highprice=0, lowprice = 0, avgflag = True):
        if avgflag:
            hist = await conn.fetch("SELECT oldprice, newprice, note FROM economy.history WHERE teamshort = $1 AND note NOT LIKE '%Match%' AND note NOT LIKE '%Currentprice%' ORDER BY date DESC LIMIT 5;", team)
            #diffs = []
            buys = []
            sels = []
            buy = 0
            sell = 0
            for item in hist:
                old = item['oldprice']
                new = item['newprice']
                note = item['note']
                diff = new - old
                if note == 'Buy':
                    buy += 1
                    buys.append(diff)
                elif note == 'Sell':
                    sell += 1
                    sels.append(diff)
                else:
                    continue
                
                
            
            if buy > sell:
                new = 0.01 * (sum(buys) / len(buys))
                if new > 0.05 * currentprice:
                    newprice = currentprice + (0.05 * currentprice)
                else:
                    newprice = currentprice + new
            elif sell > buy:
                new = 0.01 * (sum(sels) / len(sels))
                if new > 0.05 * currentprice:
                    newprice = currentprice - (0.05 * currentprice)
                else:
                    newprice = currentprice - new
            else:
                newprice = currentprice
            
        else:
            newprice = currentprice

        if newprice < 0:
            newprice = 0

        if highprice != 0 and newprice > highprice:
            highprice = newprice
            await conn.execute("UPDATE economy.market set currentprice =$1, updatedprice = $1, highprice=$2 WHERE teamshort = $3", newprice, highprice, team)
        elif lowprice != 0 and newprice < lowprice:
            lowprice = newprice
            await conn.execute("UPDATE economy.market set currentprice =$1, updatedprice = $1, lowprice=$2 WHERE teamshort = $3", newprice, lowprice, team)
        else:
            await conn.execute("UPDATE economy.market set currentprice=$1, updatedprice = $1 WHERE teamshort = $2", newprice, team)
        
        await conn.execute("INSERT INTO economy.history (teamshort, date, oldprice, volume, newprice, note) VALUES ($1, $2, $3, $4, $5, $6);", team, datetime.datetime.now(), currentprice, 0, newprice, "Currentprice Update")
        return

    async def marketupdate(self):
        async with self.bot.db.acquire() as conn:
            stocks = await conn.fetch("SELECT teamshort, currentprice, openprice FROM economy.market ORDER BY teamshort;")
            async with conn.transaction():
                for stock in stocks:
                    await conn.execute("UPDATE economy.market SET openprice=$1 where currentprice = $1 and teamshort = $2", stock['currentprice'], stock['teamshort'])
        print("Market succesfully updated")
   
    @tasks.loop(time=[time(0, 0, 0)])
    async def updateMarket(self):
        await self.marketupdate()

    @commands.command(name='updatemarket', hidden=True)
    @commands.has_permissions(ban_members=True)
    async def callUpdate(self, ctx:commands.Context):
        await self.marketupdate()
    
    @updateMarket.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()


    @commands.hybrid_command(name='market')
    @app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
    async def market(self, ctx: commands.Context, sort:str = None):
        """Get current market values"""
        #ADD ABILITY TO SORT BY TEAM,PRICE,AND CHANGE
        changeFlag = False
        if sort == "team":
            param = "teamshort"
        elif sort == "change":
            changeFlag = True
            param = 'teamshort'
        else:
            param = "currentprice DESC"

        async with self.bot.db.acquire() as conn:
            stocks = await conn.fetch(f"SELECT teamshort, currentprice, openprice FROM economy.market ORDER BY {param};")
            color = await helpers.getColor(conn, ctx.author.id)

        embedStr = f"__`{'Team':{sp}^{7}}`__ __`{'Price':{sp}^{9}}`__ __`{'Change':{sp}^{12}}`__\n"
        changelist = []
        for stock in stocks:
            team = stock['teamshort']
            currentprice = int(stock['currentprice'])
            openprice = int(stock['openprice'])
            teamlogo = discord.utils.get(self.bot.emojis, name=team)
            if openprice > currentprice:
                chang = ((openprice - currentprice) / openprice) * 100
                change = str(round(chang, 2)) + "%"
                #changeemoji = '\u2B07\uFE0F'
                changeemoji = '\uD83D\uDCC9'
                changenote = chang * -1
            elif openprice < currentprice:
                chang = ((currentprice - openprice) / openprice) * 100
                change = str(round(chang, 2)) + "%"
                #changeemoji = '\u2B06\uFE0F'
                changeemoji = '\uD83D\uDCC8'
                changenote = chang
            else:
                change = 0
                changeemoji = '\u2796'
                changenote = change
            stri = f"{teamlogo} `{team:{sp}^{4}}` `{currentprice:{sp}^{9}}` {changeemoji} `{change:{sp}^{8}}`\n"
            if changeFlag:
                
                changelist.append((changenote, stri))
                changelist.sort(key=lambda y: y[0])
            else:
                embedStr += stri

        if changeFlag:
            changelist.reverse()
            for i in changelist:
                
                embedStr += i[1]

        embed = discord.Embed(title="Current Market Values", description=embedStr, colour=color)
        await ctx.send(embed=embed)


    @commands.hybrid_command(name='portfolio')
    @app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
    async def portfolio(self, ctx: commands.Context, who: str=None, sort: str=None):
        """Get your current portfolio"""
        if who != None:
            try:
                user = await commands.UserConverter().convert(ctx, who)
            except commands.BadArgument:
                await ctx.send("User not found")
                return
        else:
            user = ctx.author
        
        changeFlag = False
        if sort == "team":
            param = "teamshort"
        elif sort == "change":
            changeFlag = True
            param = 'teamshort'
        else:
            param = "value DESC"

        async with self.bot.db.acquire() as conn:
            portfolio = await conn.fetch(f"SELECT teamshort, sum(totalprice) as value, sum(count) as count FROM economy.portfolio WHERE userid=$1 GROUP BY teamshort ORDER BY {param};", user.id)
            stocks = await conn.fetch("SELECT teamshort, currentprice FROM economy.market ORDER BY teamshort;")
            color = await helpers.getColor(conn, ctx.author.id) 

        embedStr = f"__`{'Team':{sp}^{7}}`__ __`{'Price':{sp}^{9}}`__ __`{'Change':{sp}^{12}}`__\n"
        
        totalvalue = 0
        initvalue = 0
        changelist = []
        if len(portfolio) < 1:
            await ctx.send("Portfolio not found!", delete_after=5)
            return
        for stock in portfolio:
            team = stock['teamshort']
            value = stock['value']
            initvalue += value
            numstock = stock['count']
            teamlogo = discord.utils.get(self.bot.emojis, name=team)
            for item in stocks:
                if item['teamshort'] == team:
                    currentvalue = item['currentprice'] * numstock
                    currentvalue = round(currentvalue, 2)
            
            changeprice = currentvalue - value
            chang = ((changeprice) / value) * 100
            change = str(round(abs(chang), 2)) + "%"
            if changeprice < 0:
                changeemoji = '\uD83D\uDCC9'
            elif changeprice > 0:
                changeemoji =  '\uD83D\uDCC8'
            else:
                changeemoji = '\u2796'
            totalvalue += currentvalue
            stri = f"{teamlogo} `{team:{sp}^{4}}` `{currentvalue:{sp}^{9}}` {changeemoji} `{change:{sp}^{8}}`\n"

            if changeFlag:
                changelist.append((chang, stri))
                changelist.sort(key=lambda y: y[0])
            else:
                embedStr += stri

        if changeFlag:
            changelist.reverse()
            for i in changelist:
                embedStr += i[1]   
        
        totalcha = totalvalue - initvalue
        totalchange = (abs(totalcha) / initvalue) * 100
        totalchange = str(round(totalchange, 2)) + "%"
        if totalcha < 0:
            changeemoji = '\uD83D\uDCC9'
        elif totalcha > 0:
            changeemoji = '\uD83D\uDCC8'
        else:
            changeemoji = '\u2796'

        embedStr += f"**`{'Total':{sp}^{7}}`** **`{round(totalvalue,2):{sp}^{9}}`** {changeemoji} **`{totalchange:{sp}^{8}}`**\n"
        embed = discord.Embed(title=f"{user.name}'s Portfolio", description=embedStr, color=color)
        await ctx.send(embed=embed)      

    @commands.hybrid_command(name='stock')
    @app_commands.guilds(discord.Object(id=183001948356739072), discord.Object(id=268750007740399616))
    async def stock(self, ctx: commands.Context, team: str, filter: str = None):
        """Get info about a team stock"""
        team = await helpers.getOWL(team)
        if team is None:
            await ctx.send("Invalid team!", delete_after=3)
            return

        async with self.bot.db.acquire() as conn:
            marketprice = await conn.fetchrow("SELECT teamname, teamshort, currentprice, highprice, lowprice FROM economy.market where teamshort=$1", team)
            today = datetime.date.today()
            match filter:
                case "day":
                    startdate = today - timedelta(days=1)
                    dayStr = filter.capitalize()
                case "week":
                    startdate = today -  timedelta(days=today.weekday())
                    dayStr = filter.capitalize()
                case "month":
                    startdate = datetime.date.today().replace(day=1)
                    dayStr = filter.capitalize()
                case "season":
                    q = await conn.fetchrow("SELECT startdate from athena.weeks WHERE week_number=1;")
                    startdate = q['startdate']
                    dayStr = filter.capitalize()
                #Stage is default case
                case _:
                    events = {'kickoffclash': 'Kickoff Clash', 'kickoff': 'Kickoff Clash', 'clash': 'Kickoff Clash', 'kc': 'Kickoff Clash', 'kick': 'Kickoff Clash', 'midseasonmadness': 'Midseason Madness', 'mid': 'Midseason Madness', 'midseason':'Midseason Madness', 'mad': 'Midseason Madness', 'madness': 'Midseason Madness', 'mm': 'Midseason Madness', 'summershowdown': "Summer Showdown", 'summer': "Summer Showdown", 'showdown': "Summer Showdown", 'ss': "Summer Showdown", 'countdowncup': "Countdown Cup", 'countdown': "Countdown Cup", 'cup': "Countdown Cup", 'cc': "Countdown Cup"}
                    if filter in events:
                        param = events.get(filter)
                        q = await conn.fetchrow(f"""SELECT min(week_number) as week, startdate, event FROM athena.weeks WHERE event = '{param}'
                                                GROUP BY startdate, event ORDER BY week LIMIT 1;""")
                    else:
                        param = "(select event from athena.weeks WHERE week_number = (SELECT week_number FROM athena.weeks WHERE startdate < NOW() AND enddate > NOW()))"
                        q = await conn.fetchrow(f"""SELECT min(week_number) as week, startdate, event FROM athena.weeks WHERE event = 
                        (select event from athena.weeks WHERE week_number = (SELECT week_number FROM athena.weeks WHERE startdate < NOW() AND enddate > NOW()))
                        GROUP BY startdate, event ORDER BY week LIMIT 1;""")
                    startdate = q['startdate']
                    dayStr = q['event']
                    
            stock = await conn.fetch("SELECT date, oldprice, newprice FROM economy.history WHERE teamshort=$1 AND date >$2 AND (note LIKE $3 OR note LIKE '%Match Result%') ORDER BY date;", team, startdate, '%Currentprice Update%')
            if len(stock) < 3:
                await ctx.send("Not enough data to show!", delete_after=3)
                return
            firstprice = stock[0]['oldprice']
            finalprice = stock[len(stock)-1]['newprice']
            fullteam = marketprice['teamname']
            currentprice = round(marketprice['currentprice'], 2)
            lowprice = round(marketprice['lowprice'], 2)
            highprice = round(marketprice['highprice'], 2)
            teaminfo = await conn.fetchrow("SELECT image, team_color FROM stats.teaminfo WHERE team_name=$1", fullteam)
            image = teaminfo['image']
            color = teaminfo['team_color']
            colorint = int(color.decode('utf-8'), 16)
            colorstr = "#" + str(color.decode('utf-8')[2:])
            if finalprice > firstprice:
                change = round(((finalprice - firstprice) / firstprice)* 100, 2)
                changestr = "+" + str(change)
                graphcolor = 'green'
            elif finalprice < firstprice:
                change = round(((firstprice - finalprice) / firstprice * 100), 2)
                changestr = "-" + str(change)
                graphcolor = 'red'
            else:
                change = 0
                changestr = str(change)
                graphcolor = colorstr

            values = []
            dates = []
            data_stream = io.BytesIO()
            for s in stock:
                values.append(s['newprice'])
                dates.append(s['date'])

            lowest = min(values)
            highest = max(values)
            fig, ax = plt.subplots(1,1)
            ax.plot(dates, values, color=graphcolor, marker='.')
            ax.set_title(f"{dayStr} chart for {fullteam}", color="white")
            ax.set_xlabel("Dates", color="white")
            plt.xticks(fontsize=8)
            ax.set_ylabel("Price", color="white")
            ax.set_ylim(ymin=lowest - 50, ymax= highest + 100)
            ax.tick_params(color=colorstr, labelcolor='white')
            for spine in ax.spines.values():
                spine.set_edgecolor(colorstr)
            plt.setp(ax.get_xticklabels(), rotation=45)
            plt.savefig(data_stream, format='png', transparent=True)
            plt.close()
            data_stream.seek(0)
            chart = discord.File(data_stream, filename="chart.png")
            embedStr = f"Current Market Price: **{currentprice}** ({changestr}%)\nHighest Price(All-Time): **{highprice}**\nLowest price(All-Time): **{lowprice}**"
            embed = discord.Embed(title=f"Stock info for {fullteam}", description=embedStr, color=colorint)
            embed.set_image(url="attachment://chart.png")
            embed.set_thumbnail(url=image)
            await ctx.send(embed=embed, file=chart)


async def setup(bot):
	await bot.add_cog(StockCog(bot))