import discord
from discord.ext import commands
from utils.embeds import log_embed

class Logging(commands.Cog):
    """Event logging system"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def get_log_channel(self, guild):
        """Get the log channel for a guild"""
        config = self.bot.config
        if config.logs_channel:
            return guild.get_channel(config.logs_channel)
        return None
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Log member joins"""
        channel = self.get_log_channel(member.guild)
        if not channel:
            return
        
        # Calculate account age
        account_age = (discord.utils.utcnow() - member.created_at).days
        
        embed = log_embed(
            "Member Joined",
            f"{member.mention} joined the server",
            discord.Color.green(),
            [
                {'name': 'User', 'value': f"{member.name} ({member.id})", 'inline': True},
                {'name': 'Account Created', 'value': member.created_at.strftime("%Y-%m-%d %H:%M UTC"), 'inline': True},
                {'name': 'Account Age', 'value': f"{account_age} days", 'inline': True},
                {'name': 'Member Count', 'value': str(member.guild.member_count), 'inline': True}
            ]
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Log member leaves"""
        channel = self.get_log_channel(member.guild)
        if not channel:
            return
        
        embed = log_embed(
            "Member Left",
            f"{member.mention} left the server",
            discord.Color.orange(),
            [
                {'name': 'User', 'value': f"{member.name} ({member.id})", 'inline': True},
                {'name': 'Joined At', 'value': member.joined_at.strftime("%Y-%m-%d %H:%M UTC") if member.joined_at else "Unknown", 'inline': True},
                {'name': 'Member Count', 'value': str(member.guild.member_count), 'inline': True}
            ]
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await channel.send(embed=embed)
        
        # Log to database
        await self.bot.db.log_event(
            member.guild.id,
            'member_leave',
            f"{member.name} ({member.id}) left the server",
            member.id
        )
    
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Log message deletions"""
        # Skip bots and DMs
        if message.author.bot or not message.guild:
            return
        
        channel = self.get_log_channel(message.guild)
        if not channel:
            return
        
        # Don't log if content is empty (e.g., image only)
        content = message.content[:1000] if message.content else "*[No text content]*"
        
        embed = log_embed(
            "Message Deleted",
            f"Message by {message.author.mention} deleted in {message.channel.mention}",
            discord.Color.red(),
            [
                {'name': 'Author', 'value': f"{message.author.name} ({message.author.id})", 'inline': True},
                {'name': 'Channel', 'value': message.channel.mention, 'inline': True},
                {'name': 'Content', 'value': content, 'inline': False}
            ]
        )
        
        await channel.send(embed=embed)
        
        # Log to database
        await self.bot.db.log_event(
            message.guild.id,
            'message_delete',
            f"Message by {message.author.name} deleted in {message.channel.name}: {content[:100]}",
            message.author.id
        )
    
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Log message edits"""
        # Skip bots, DMs, and if content didn't change
        if before.author.bot or not before.guild or before.content == after.content:
            return
        
        channel = self.get_log_channel(before.guild)
        if not channel:
            return
        
        before_content = before.content[:500] if before.content else "*[No text content]*"
        after_content = after.content[:500] if after.content else "*[No text content]*"
        
        embed = log_embed(
            "Message Edited",
            f"Message by {before.author.mention} edited in {before.channel.mention}",
            discord.Color.blue(),
            [
                {'name': 'Author', 'value': f"{before.author.name} ({before.author.id})", 'inline': True},
                {'name': 'Channel', 'value': before.channel.mention, 'inline': True},
                {'name': 'Before', 'value': before_content, 'inline': False},
                {'name': 'After', 'value': after_content, 'inline': False},
                {'name': 'Jump to Message', 'value': f"[Click here]({after.jump_url})", 'inline': False}
            ]
        )
        
        await channel.send(embed=embed)
        
        # Log to database
        await self.bot.db.log_event(
            before.guild.id,
            'message_edit',
            f"Message by {before.author.name} edited in {before.channel.name}",
            before.author.id
        )
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        """Log member bans"""
        channel = self.get_log_channel(guild)
        if not channel:
            return
        
        embed = log_embed(
            "Member Banned",
            f"{user.mention} was banned",
            discord.Color.dark_red(),
            [
                {'name': 'User', 'value': f"{user.name} ({user.id})", 'inline': True}
            ]
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        await channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        """Log member unbans"""
        channel = self.get_log_channel(guild)
        if not channel:
            return
        
        embed = log_embed(
            "Member Unbanned",
            f"{user.mention} was unbanned",
            discord.Color.green(),
            [
                {'name': 'User', 'value': f"{user.name} ({user.id})", 'inline': True}
            ]
        )
        
        await channel.send(embed=embed)


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Log voice channel updates"""
        if member.bot: return
        
        channel = self.get_log_channel(member.guild)
        if not channel: return
        
        description = ""
        color = discord.Color.blue()
        
        if before.channel is None and after.channel is not None:
             description = f"🎤 {member.mention} **joined** voice channel {after.channel.mention}"
             color = discord.Color.green()
        elif before.channel is not None and after.channel is None:
             description = f"🚪 {member.mention} **left** voice channel {before.channel.mention}"
             color = discord.Color.orange()
        elif before.channel != after.channel:
             description = f"➡️ {member.mention} **moved** from {before.channel.mention} to {after.channel.mention}"
             
        if description:
             embed = discord.Embed(description=description, color=color, timestamp=discord.utils.utcnow())
             embed.set_author(name=member.name, icon_url=member.display_avatar.url)
             await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        channel = self.get_log_channel(role.guild)
        if not channel: return
        
        embed = discord.Embed(description=f"🆕 Role **{role.name}** was created.", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        channel = self.get_log_channel(role.guild)
        if not channel: return
        
        embed = discord.Embed(description=f"🗑️ Role **{role.name}** was deleted.", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        await channel.send(embed=embed)
        
    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        channel = self.get_log_channel(before.guild)
        if not channel: return
        
        if before.name != after.name:
             embed = discord.Embed(description=f"✏️ Role **{before.name}** renamed to **{after.name}**", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
             await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Logging(bot))
