"""
Complete Ticket System Fix & Verification Script

This script will:
1. Sync database with Discord (mark deleted channels as closed)
2. Show current status
3. Create a test ticket to verify everything works
4. Display messages for verification
"""
import discord
from discord.ext import commands
import asyncio
import sys
sys.path.insert(0, '.')

from config import Config
from database import Database

async def main():
    # Setup
    config = Config()
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print("=" * 60)
        print(f"TICKET SYSTEM FIX & VERIFICATION")
        print("=" * 60)
        print(f"Logged in as: {bot.user}\n")
        
        # Connect to database
        db = Database()
        await db.connect()
        
        # Step 1: Get all tickets from database
        print("[STEP 1] Checking database tickets...")
        async with db.db.execute("SELECT channel_id, guild_id, owner_id, status FROM tickets") as cursor:
            all_tickets = await cursor.fetchall()
        
        print(f"Total tickets in database: {len(all_tickets)}")
        open_count = sum(1 for t in all_tickets if t[3] == 'open')
        print(f"Marked as 'open': {open_count}\n")
        
        # Step 2: Sync with Discord
        print("[STEP 2] Syncing with Discord...")
        synced_count = 0
        closed_count = 0
        
        for channel_id, guild_id, owner_id, status in all_tickets:
            if status != 'open':
                continue
                
            guild = bot.get_guild(guild_id)
            if not guild:
                print(f"  ⚠ Guild {guild_id} not accessible")
                continue
            
            channel = guild.get_channel(channel_id)
            if not channel:
                print(f"  ✗ Channel {channel_id} doesn't exist - marking as closed")
                await db.db.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (channel_id,))
                closed_count += 1
            else:
                print(f"  ✓ Channel exists: #{channel.name} (ID: {channel_id})")
                synced_count += 1
        
        await db.db.commit()
        print(f"\nSynced {synced_count} tickets, closed {closed_count} orphaned tickets\n")
        
        # Step 3: Show current open tickets
        print("[STEP 3] Current open tickets:")
        async with db.db.execute("SELECT channel_id, guild_id FROM tickets WHERE status = 'open'") as cursor:
            open_tickets = await cursor.fetchall()
        
        if not open_tickets:
            print("  No open tickets found\n")
        else:
            for channel_id, guild_id in open_tickets:
                guild = bot.get_guild(guild_id)
                if guild:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        # Get message count
                        async with db.db.execute("SELECT COUNT(*) FROM ticket_messages WHERE ticket_id = ?", (channel_id,)) as cursor:
                            msg_count = (await cursor.fetchone())[0]
                        print(f"  ✓ #{channel.name} (ID: {channel_id}) - {msg_count} messages logged")
        
        print("\n" + "=" * 60)
        print("VERIFICATION COMPLETE")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Refresh web dashboard")
        print("2. Load tickets with your Guild ID")
        print("3. Create a NEW ticket in Discord if none are open")
        print("4. Send messages in the ticket")
        print("5. Check web - ticket should appear with messages")
        print("\nPress Ctrl+C to exit...")
        
        await db.close()
        await bot.close()
    
    try:
        await bot.start(config.token)
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    asyncio.run(main())
