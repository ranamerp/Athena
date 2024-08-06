import discord
import asyncio
import asyncpg
from discord.ext import commands
from resources import queries, helpers
import pickle

eventTypeMap = {"offers": "offers", "trades": "offers", "offer": "offers", "trade": "offer"}

class NotifsCog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
	



	async def notify(self, eventType, notifText, who=None):
		async with self.bot.db.acquire() as conn:
			if who:
				toNotify = await conn.fetchrow("SELECT user_id FROM notifications WHERE event_type = $1 AND user_id = $2 AND opt_in;", eventType, who)
				if not toNotify:
					return

				user = self.bot.get_user(toNotify['user_id'])
				if not user:
					print(f'Attempted and failed to send message to user id {who}, removing from notification list')
					await conn.execute("DELETE FROM notifications WHERE user_id = $1;", who)
				else:
					try:
						await user.send(notifText)
					except discord.Forbidden:
						print(f"Failed sending message to {who}: Invalid Permissions")
					else:
						print(f"Notified 1 user for {eventType}")

			else:
				toNotify = await conn.fetch("SELECT user_id FROM notifications WHERE event_type = $1 AND opt_in;", eventType)
				if not toNotify:
					return

				i = 0
				for user in toNotify:
					user = await self.bot.get_user(user['user_id'])
					if not user:
						print(f'Attempted and failed to send message to user id {who}, removing from notification list')
						await conn.execute("DELETE FROM notifications WHERE user_id = $1;", who)
					else:
						try:
							await user.send(notifText)
							i += 1
						except discord.Forbidden:
							print(f"Failed sending message to {who}: Invalid Permissions")
				
			print(f"Notified {i} user(s) for {eventType}")

	async def optIn(self, eventType, userID, special=None):
		async with self.bot.db.acquire() as conn:
			if not await conn.fetchrow("SELECT * FROM notifications WHERE user_id = $1 AND event_type = $2 AND special = $3;", userID, eventType, special):
				await conn.execute('INSERT INTO notifications (user_id, event_type, opt_in, special) VALUES ($1, $2, TRUE, $3);', userID, eventType, special)



	@commands.command(name='opt')
	async def optInOrOut(self, ctx, inOrOut, eventType, *, special=None):
		if inOrOut.lower() == 'in':
			opt = True
		elif inOrOut.lower() == 'out':
			opt = False
		else:
			await ctx.send("You must chose to either opt in or opt out")
			return
 
		try:
			eventType = eventTypeMap[eventType.lower()]
		except KeyError:
			await ctx.send("Notification type not found")
			return

		async with self.bot.db.acquire() as conn:
			async with conn.transaction():
				await conn.execute("DELETE FROM notifications WHERE user_id = $1 AND event_type = $2 AND special = $3", ctx.author.id, eventType, special)
				await conn.execute('INSERT INTO notifications (user_id, event_type, opt_in, special) VALUES ($1, $2, $3, $4);', ctx.author.id, eventType, opt, special)

		await self.ctx.send(f'Successfully opted {ctx.author.name} {inOrOut.lower()} of notification')

async def setup(bot):
	await bot.add_cog(NotifsCog(bot))
