import requests
import json
import time 
import datetime 
import asyncpg
import asyncio
import os
from os.path import join, dirname
from dotenv import load_dotenv

DBPASS = os.getenv('DBPASS')
DBHOST = os.getenv('DBHOST')
DBUSER= os.getenv('DBUSER')
DBDATABASE= os.getenv('DBDATABASE')

async def get_week(n):
	headers = {
		'authority': 'wzavfvwgfk.execute-api.us-east-2.amazonaws.com',
		'origin': 'https://overwatchleague.com',
		'x-origin': 'overwatchleague.com',
		'accept': '*/*',
		'sec-fetch-site': 'cross-site',
		'sec-fetch-mode': 'cors',
		'referer': 'https://overwatchleague.com/en-us/schedule?stage=regular_season&week={}'.format(n),
		'accept-encoding': 'gzip, deflate, br',
		'accept-language': 'en-US,en;q=0.9',
	}
	params = (
		('stage', 'regular_season'),
		('page', '{}'.format(n)),
		('season', '2020'),
		('locale', 'en-us'),
	)
	response = requests.get('https://wzavfvwgfk.execute-api.us-east-2.amazonaws.com/production/owl/paginator/schedule', headers=headers, params=params)
	return json.loads(response.text)

async def loadMatches():
	credentials = {"user": DBUSER, "password": DBPASS, "database": DBDATABASE, "host": DBHOST}
	db = await asyncpg.create_pool(**credentials)
	conn = await db.acquire()
	for i in range(1, 20):
		week = await get_week(i)
		#"2021-04-20T07:59:59.000Z"
		selement = datetime.datetime.strptime(week["content"]["tableData"]["startDate"],"%Y-%m-%dT%H:%M:%S.%fZ") 
		#stimestamp = datetime.datetime.timestamp(selement) 

		eelement = datetime.datetime.strptime(week["content"]["tableData"]["endDate"],"%Y-%m-%dT%H:%M:%S.%fZ") 
		await conn.execute("INSERT INTO athena.weeks (week_number, startdate, enddate, type) VALUES ($1, $2, $3, $4)", week["content"]["tableData"]["weekNumber"], selement, eelement, week["content"]["tableData"]["events"][0]["eventBanner"]["title"][5:-16])
		async with conn.transaction():
			for match in week["content"]["tableData"]["events"][0]["matches"]:
				if match['isEncore']:
					continue
				try:
					htscore = match['scores'][0]
					atscore = match['scores'][1]
				except IndexError:
					htscore = None
					atscore = None
				await conn.execute("INSERT INTO athena.matches (htname, htscore, atname, atscore, startdate, week_number, htshort, atshort, status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);", match["competitors"][0]["name"], htscore, match["competitors"][1]["name"], atscore, datetime.datetime.fromtimestamp(match["startDate"]/1000.0), week["content"]["tableData"]["weekNumber"], match["competitors"][0]["abbreviatedName"], match["competitors"][1]["abbreviatedName"], match["status"])
					

	await db.release(conn)

asyncio.get_event_loop().run_until_complete(loadMatches())