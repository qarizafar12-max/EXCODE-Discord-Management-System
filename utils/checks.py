from discord.ext import commands
import discord

def is_admin():
    """Check if the user is an authorized admin (Owner or Bot Admin)"""
    async def predicate(ctx):
        # Get bot's config and db
        config = ctx.bot.config
        db = ctx.bot.db
        
        # Check if user ID is the Owner (from config)
        if ctx.author.id in config.admin_ids:
            return True
            
        # Check if user ID is a Bot Admin (from DB)
        if await db.is_bot_admin(ctx.author.id):
            return True
            
        await ctx.send("❌ You don't have permission to use this command. Admin access required.")
        return False
    
    return commands.check(predicate)

async def is_bot_admin(bot, user_id):
    """Async check if a user is an owner or bot admin"""
    if bot.config.is_admin(user_id):
        return True
    return await bot.db.is_bot_admin(user_id)

def is_moderator():
    """Check if the user has moderation permissions"""
    async def predicate(ctx):
        # Check if user is owner or bot admin
        config = ctx.bot.config
        db = ctx.bot.db
        
        if ctx.author.id in config.admin_ids or await db.is_bot_admin(ctx.author.id):
            return True
        
        # Check if user has moderation permissions
        if not isinstance(ctx.author, discord.Member):
            return False
        
        if ctx.author.guild_permissions.kick_members or ctx.author.guild_permissions.ban_members or ctx.author.guild_permissions.administrator:
            return True
        
        await ctx.send("❌ You don't have permission to use this command. Moderator access required.")
        return False
    
    return commands.check(predicate)
