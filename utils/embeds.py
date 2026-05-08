import discord
from datetime import datetime

def create_embed(title, description, color=discord.Color.blue(), fields=None):
    """Create a standard embed"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow()
    )
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get('name', ''),
                value=field.get('value', ''),
                inline=field.get('inline', False)
            )
    
    return embed

def welcome_embed(member):
    """Create a welcome embed for new members"""
    embed = discord.Embed(
        title=f"Welcome to {member.guild.name}! 👋",
        description=f"{member.mention} just joined the server!",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Member Count", value=f"{member.guild.member_count} members", inline=False)
    embed.set_footer(text=f"ID: {member.id}")
    return embed

def warning_embed(user, moderator, reason, warning_count):
    """Create a warning embed"""
    embed = discord.Embed(
        title="⚠️ User Warned",
        description=f"{user.mention} has been warned by {moderator.mention}",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Total Warnings", value=str(warning_count), inline=False)
    embed.set_footer(text=f"User ID: {user.id}")
    return embed

def mute_embed(user, moderator, duration, reason):
    """Create a mute embed"""
    embed = discord.Embed(
        title="🔇 User Muted",
        description=f"{user.mention} has been muted by {moderator.mention}",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Duration", value=duration, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"User ID: {user.id}")
    return embed

def kick_embed(user, moderator, reason):
    """Create a kick embed"""
    embed = discord.Embed(
        title="👢 User Kicked",
        description=f"{user.mention} has been kicked by {moderator.mention}",
        color=discord.Color.dark_red(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"User ID: {user.id}")
    return embed

def ban_embed(user, moderator, reason):
    """Create a ban embed"""
    embed = discord.Embed(
        title="🔨 User Banned",
        description=f"{user.mention} has been banned by {moderator.mention}",
        color=discord.Color.dark_red(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"User ID: {user.id}")
    return embed

def log_embed(title, description, color=discord.Color.blue(), fields=None):
    """Create a log embed"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow()
    )
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get('name', ''),
                value=field.get('value', ''),
                inline=field.get('inline', False)
            )
    
    return embed

def announcement_embed(title, message, author, guild=None):
    """Create an announcement embed"""
    embed = discord.Embed(
        title=f"📢 {title}",
        description=message,
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"Posted by {author.name} | {guild.name if guild else ''}", icon_url=author.display_avatar.url)
    if guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    return embed

def video_embed(url, title=None, description=None, author=None):
    """Create a video post embed"""
    embed = discord.Embed(
        title=f"🎥 {title}" if title else "🎥 Video Post",
        description=description or "Check out this video!",
        color=discord.Color.purple(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Video URL", value=url, inline=False)
    
    if author:
        embed.set_footer(text=f"Posted by {author.name}", icon_url=author.display_avatar.url)
    
    return embed

def user_info_embed(user, warnings, infractions, tracking_data):
    """Create a user info embed"""
    embed = discord.Embed(
        title=f"User Information - {user.name}",
        description=f"Detailed information about {user.mention}",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="User ID", value=str(user.id), inline=True)
    embed.add_field(name="Account Created", value=user.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    
    if isinstance(user, discord.Member):
        embed.add_field(name="Joined Server", value=user.joined_at.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    
    embed.add_field(name="Total Warnings", value=str(len(warnings)), inline=True)
    embed.add_field(name="Total Infractions", value=str(len(infractions)), inline=True)
    
    if tracking_data:
        embed.add_field(name="Total Messages", value=str(tracking_data[4]), inline=True)
    
    embed.set_footer(text=f"Requested at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    
    return embed
