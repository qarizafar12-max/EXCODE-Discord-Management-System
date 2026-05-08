import discord
from discord.ext import commands
from datetime import datetime, timedelta
from collections import defaultdict
from utils.checks import is_admin, is_bot_admin
from utils.embeds import create_embed

class AntiRaid(commands.Cog):
    """Anti-raid protection system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.join_tracker = defaultdict(list)  # Track recent joins
        self.raid_mode = False
    
    def is_raid_detected(self, guild_id):
        """Check if a raid is being detected"""
        config = self.bot.config
        settings = config.antiraid_settings
        
        if not settings.get('enabled', False):
            return False
        
        threshold = settings.get('join_threshold', 5)
        interval = settings.get('join_interval', 60)
        
        # Get recent joins
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=interval)
        
        # Clean old joins
        self.join_tracker[guild_id] = [
            join_time for join_time in self.join_tracker[guild_id]
            if join_time > cutoff
        ]
        
        # Check if threshold exceeded
        return len(self.join_tracker[guild_id]) >= threshold
    
    def is_new_account(self, member):
        """Check if account is newly created"""
        config = self.bot.config
        settings = config.antiraid_settings
        
        new_account_days = settings.get('new_account_days', 7)
        account_age = (datetime.utcnow() - member.created_at).days
        
        return account_age < new_account_days
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Monitor joins for raid detection"""
        config = self.bot.config
        settings = config.antiraid_settings
        
        if not settings.get('enabled', False):
            return
        
        # Track the join
        self.join_tracker[member.guild.id].append(datetime.utcnow())
        
        # Check for raid
        if self.is_raid_detected(member.guild.id):
            if not self.raid_mode:
                self.raid_mode = True
                await self.alert_admins(member.guild, "Possible raid detected! Multiple users joining rapidly.")
        
        # Check for new account
        if self.is_new_account(member):
            # Alert but don't auto-kick (to avoid blocking legitimate new users)
            await self.alert_admins(
                member.guild,
                f"⚠️ New account joined: {member.mention} (Account age: {(datetime.utcnow() - member.created_at).days} days)"
            )
            
            # Log to database
            await self.bot.db.log_event(
                member.guild.id,
                'new_account_join',
                f"New account ({(datetime.utcnow() - member.created_at).days} days old): {member.name} ({member.id})",
                member.id
            )
        
        # If in raid mode and new account, increase scrutiny
        if self.raid_mode and self.is_new_account(member):
            # Monitor their first message closely
            pass
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Monitor messages from new users during potential raids"""
        if message.author.bot or not message.guild:
            return
            
        if await is_bot_admin(self.bot, message.author.id):
            return
        
        config = self.bot.config
        
        # If raid mode is active and user is new
        if self.raid_mode and self.is_new_account(message.author):
            # Check if they immediately spam after joining
            user_data = await self.bot.db.get_user_data(message.author.id, message.guild.id)
            
            if user_data:
                # If this is one of their first messages and it looks suspicious
                message_count = user_data[4]  # total_messages
                
                if message_count < 3:
                    # Check for suspicious patterns
                    content = message.content.lower()
                    
                    # Check for links in first message (common raid tactic)
                    if any(pattern in content for pattern in ['http://', 'https://', 'discord.gg/']):
                        await self.alert_admins(
                            message.guild,
                            f"🚨 Suspicious behavior: {message.author.mention} posted link in first message during raid mode!"
                        )
                        
                        # Delete the message
                        try:
                            await message.delete()
                        except:
                            pass
    
    async def alert_admins(self, guild, alert_message):
        """Send alert to admins about suspicious activity"""
        config = self.bot.config
        
        # Send to logs channel
        if config.logs_channel:
            channel = guild.get_channel(config.logs_channel)
            if channel:
                embed = create_embed(
                    "🚨 Anti-Raid Alert",
                    alert_message,
                    discord.Color.red()
                )
                await channel.send(embed=embed)
        
        # Could also DM admins, but that might be too spammy
        # For now, just log it
        print(f"[ANTI-RAID] {alert_message}")
    
    @commands.command(name='antiraid')
    @is_admin()
    async def toggle_antiraid(self, ctx, mode: str):
        """Toggle anti-raid protection
        Usage: !antiraid <on/off>
        """
        if mode.lower() not in ['on', 'off', 'enable', 'disable']:
            await ctx.send("❌ Usage: `!antiraid <on/off>`")
            return
        
        enabled = mode.lower() in ['on', 'enable']
        
        # Update config
        self.bot.config.data['antiraid']['enabled'] = enabled
        self.bot.config.save_config()
        
        # Reset raid mode when disabling
        if not enabled:
            self.raid_mode = False
            self.join_tracker.clear()
        
        status = "enabled" if enabled else "disabled"
        embed = create_embed(
            "Anti-Raid Protection",
            f"Anti-raid protection has been **{status}**",
            discord.Color.green() if enabled else discord.Color.orange()
        )
        
        await ctx.send(embed=embed)
        
        # Log the action
        await self.bot.db.log_event(
            ctx.guild.id,
            'antiraid_toggle',
            f"{ctx.author.name} {status} anti-raid protection",
            ctx.author.id
        )
    
    @commands.command(name='raidstatus')
    @is_admin()
    async def raid_status(self, ctx):
        """Check anti-raid protection status"""
        config = self.bot.config
        settings = config.antiraid_settings
        
        enabled = settings.get('enabled', False)
        threshold = settings.get('join_threshold', 5)
        interval = settings.get('join_interval', 60)
        
        recent_joins = len(self.join_tracker.get(ctx.guild.id, []))
        
        embed = create_embed(
            "Anti-Raid Status",
            f"Current anti-raid protection status",
            discord.Color.blue(),
            [
                {'name': 'Status', 'value': 'Enabled ✅' if enabled else 'Disabled ❌', 'inline': True},
                {'name': 'Raid Mode', 'value': 'Active 🚨' if self.raid_mode else 'Inactive', 'inline': True},
                {'name': 'Join Threshold', 'value': f'{threshold} users in {interval}s', 'inline': True},
                {'name': 'Recent Joins', 'value': f'{recent_joins} in last {interval}s', 'inline': True}
            ]
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='raidmode')
    @is_admin()
    async def toggle_raid_mode(self, ctx, mode: str):
        """Manually toggle raid mode
        Usage: !raidmode <on/off>
        """
        if mode.lower() not in ['on', 'off']:
            await ctx.send("❌ Usage: `!raidmode <on/off>`")
            return
        
        self.raid_mode = mode.lower() == 'on'
        
        status = "activated" if self.raid_mode else "deactivated"
        await ctx.send(f"🚨 Raid mode has been **{status}**")
        
        # Log the action
        await self.bot.db.log_event(
            ctx.guild.id,
            'raid_mode_toggle',
            f"{ctx.author.name} {status} raid mode",
            ctx.author.id
        )

async def setup(bot):
    await bot.add_cog(AntiRaid(bot))
