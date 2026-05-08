import discord
from discord.ext import commands
import asyncio
import os
from config import Config
from database import Database

# Bot configuration
intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Load configuration
bot.config = Config()
bot.db = None

@bot.event
async def on_ready():
    """Called when bot is ready"""
    print(f"""
╔══════════════════════════════════════════╗
║     EXCODE Sentinel Infrastructure       ║
║              Online & Ready!             ║
╚══════════════════════════════════════════╝
    
Bot User: {bot.user.name}#{bot.user.discriminator}
Bot ID: {bot.user.id}
Servers: {len(bot.guilds)}
Total Members: {sum(g.member_count for g in bot.guilds)}
    """)
    
    # Sync slash commands
    try:
        print("Syncing slash commands...")
        synced = await bot.tree.sync()
        print(f"[OK] Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"[ERROR] Failed to sync commands: {e}")
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Sentinel | /help"
        )
    )
    
    print("Bot is ready to manage your server!")
    print("Use /help for slash commands or !help for prefix commands")

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: `{error.param.name}`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument provided")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    elif isinstance(error, commands.CheckFailure):
        pass  # Permission errors already handled in checks
    else:
        print(f"Error in command {ctx.command}: {error}")

@bot.command(name='help')
async def help_command(ctx):
    """Show help information"""
    config = bot.config
    db = bot.db
    is_admin_user = config.is_admin(ctx.author.id) or await db.is_bot_admin(ctx.author.id)
    
    embed = discord.Embed(
        title="🛡️ EXCODE Sentinel",
        description="Production-grade community infrastructure system",
        color=discord.Color.blue()
    )
    
    # Moderation commands
    mod_commands = """
    `!warn @user [reason]` - Warn a user
    `!mute @user [duration] [reason]` - Mute a user (e.g., 10m, 1h, 1d)
    `!unmute @user` - Unmute a user
    `!kick @user [reason]` - Kick a user
    `!ban @user [reason]` - Ban a user
    `!userinfo @user` - View user history and infractions
    """
    embed.add_field(name="⚖️ Moderation Commands", value=mod_commands, inline=False)
    
    # Admin commands (only show to admins)
    if is_admin_user:
        admin_commands = """
        `!postvideo <url> [title] [desc]` - Post a video
        `!announce #channel <message>` - Send announcement
        `!lock [#channel]` - Lock a channel
        `!unlock [#channel]` - Unlock a channel
        `!slowmode #channel <seconds>` - Set slowmode
        `!addrole @user @role` - Add role to user
        `!removerole @user @role` - Remove role from user
        `!purge <amount>` - Delete messages
        `!setchannel <type> #channel` - Set bot channels
        `!antiraid <on/off>` - Toggle anti-raid
        `!raidstatus` - Check raid protection status
        `!raidmode <on/off>` - Toggle raid mode
        `!invite` - Get bot invite link with slash commands
        """
        embed.add_field(name="👑 Admin Commands", value=admin_commands, inline=False)
    
    embed.set_footer(text="EXCODE Sentinel | Community Infrastructure System")
    
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: {latency}ms")

@bot.command(name='info')
async def bot_info(ctx):
    """Show bot information"""
    embed = discord.Embed(
        title="Sentinel Infrastructure",
        description="EXCODE Sentinel Platform",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="Users", value=str(len(bot.users)), inline=True)
    embed.add_field(name="Prefix", value="!", inline=True)
    
    embed.set_footer(text="Engineered by Mr. Miz | EXCODE Sentinel")
    
    await ctx.send(embed=embed)

async def load_cogs():
    """Load all cog modules"""
    cogs = [
        'cogs.welcome',
        'cogs.moderation',
        'cogs.admin',
        'cogs.logging',
        'cogs.antiraid',
        'cogs.slash_commands',
        'cogs.ai',
        'cogs.ai_chat',
        'cogs.suggestions',
        'cogs.polls',
        'cogs.invites',
        'cogs.tickets',
        'cogs.panel',
        'cogs.general',
        'cogs.settings',
        'cogs.setup',
        'cogs.leveling',
        'cogs.server_stats',
        'cogs.sticky',
        'cogs.auto_responder',
        'cogs.web_integration', # Queue worker
        'cogs.server_builder',  # Auto server setup wizard
        'cogs.server_modifier', # /modify-server natural language command
    ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"[OK] Loaded {cog}")
        except Exception as e:
            print(f"[FAIL] Failed to load {cog}: {e}")

async def main():
    """Main bot startup function"""
    # Initialize database
    bot.db = Database()
    await bot.db.connect()
    print("[OK] Database connected")
    
    # Load all cogs
    await load_cogs()
    
    # Start the bot
    token = bot.config.token
    if not token:
        print("[ERROR] Bot token not found! Please check your .env file or config.json.")
        return
    
    try:
        await bot.start(token)
    except discord.LoginFailure:
        print("[ERROR] Invalid bot token!")
    except Exception as e:
        print(f"[ERROR] Error starting bot: {e}")
    finally:
        if bot.db:
            await bot.db.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nBot shutting down...")
