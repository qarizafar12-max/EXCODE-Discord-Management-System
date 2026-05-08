"""
Ticket Cleanup Script - Sync Database with Discord Reality

This script checks which tickets are marked as 'open' in the database
but don't actually exist as channels in Discord anymore.
"""
import discord
from discord.ext import commands
import asyncio
import sys
sys.path.insert(0, '.')

from config import Config
from database import Database

class TicketCleaner:
    async def clean(self):
        # Setup bot client
        config = Config()
        intents = discord.Intents.default()
        intents.guilds = True
        bot = commands.Bot(command_prefix="!", intents=intents)
        
        @bot.event
        async def on_ready():
            print(f"[OK] Logged in as {bot.user}")
            
            # Connect to database
            db = Database()
            await db.connect()
            
            # Get all open tickets
            import aiosqlite
            async with db.db.execute("SELECT channel_id, guild_id FROM tickets WHERE status = 'open'") as cursor:
                open_tickets = await cursor.fetchall()
            
            print(f"\n[INFO] Found {len(open_tickets)} tickets marked as 'open' in database")
            
            closed_count = 0
            for ticket_id, guild_id in open_tickets:
                guild = bot.get_guild(guild_id)
                if not guild:
                    print(f"[WARN] Guild {guild_id} not found")
                    continue
                
                channel = guild.get_channel(ticket_id)
                if not channel:
                    # Channel doesn't exist - mark as closed
                    print(f"[FIX] Channel {ticket_id} doesn't exist - marking as closed")
                    await db.db.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (ticket_id,))
                    await db.db.commit()
                    closed_count += 1
                else:
                    print(f"[OK] Channel {ticket_id} exists: #{channel.name}")
            
            print(f"\n[DONE] Closed {closed_count} orphaned tickets")
            print("[INFO] Database is now synced with Discord")
            
            await db.close()
            await bot.close()
        
        await bot.start(config.token)

if __name__ == "__main__":
    cleaner = TicketCleaner()
    asyncio.run(cleaner.clean())
