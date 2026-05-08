import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from typing import Optional, Literal
from utils.embeds import (
    warning_embed, mute_embed, kick_embed, ban_embed, 
    user_info_embed, create_embed, announcement_embed
)

class SlashCommands(commands.Cog):
    """Advanced slash commands for server management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # ==================== MODERATION COMMANDS ====================
    
    @app_commands.command(name="warn", description="Warn a user for breaking rules")
    @app_commands.describe(
        user="The user to warn",
        reason="Why are you warning this user?"
    )
    @app_commands.checks.has_permissions(kick_members=True)
    async def slash_warn(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member, 
        reason: str = "No reason provided"
    ):
        """Warn a user"""
        db = self.bot.db
        
        # Add warning
        await db.add_warning(user.id, interaction.guild.id, interaction.user.id, reason)
        
        # Get warning count
        warning_count = await db.get_warning_count(user.id, interaction.guild.id)
        
        # Create and send embed
        embed = warning_embed(user, interaction.user, reason, warning_count)
        await interaction.response.send_message(embed=embed)
        
        # Log the warning
        await db.log_event(
            interaction.guild.id,
            'warning',
            f"{user.name} warned by {interaction.user.name}: {reason}",
            user.id
        )
        
        # DM the user
        try:
            await user.send(
                f"⚠️ You have been warned in **{interaction.guild.name}**\n"
                f"**Reason:** {reason}\n"
                f"**Total warnings:** {warning_count}/3"
            )
        except:
            pass
    
    @app_commands.command(name="mute", description="Temporarily mute a user")
    @app_commands.describe(
        user="The user to mute",
        duration="How long to mute (e.g., 10m, 1h, 2d)",
        reason="Why are you muting this user?"
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    async def slash_mute(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        duration: str = "10m",
        reason: str = "No reason provided"
    ):
        """Mute a user for a specified duration"""
        # Parse duration
        try:
            time_units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
            unit = duration[-1]
            value = int(duration[:-1])
            seconds = value * time_units.get(unit, 60)
            
            # Discord timeout max is 28 days
            if seconds > 28 * 86400:
                seconds = 28 * 86400
                duration = "28d"
        except:
            await interaction.response.send_message("❌ Invalid duration format. Use: 10m, 1h, 2d", ephemeral=True)
            return
        
        # Apply timeout
        try:
            timeout_duration = timedelta(seconds=seconds)
            await user.timeout(timeout_duration, reason=reason)
            
            # Add to database
            await self.bot.db.add_infraction(
                user.id,
                interaction.guild.id,
                'mute',
                interaction.user.id,
                reason,
                seconds
            )
            
            # Send confirmation
            embed = mute_embed(user, interaction.user, duration, reason)
            await interaction.response.send_message(embed=embed)
            
            # Log the mute
            await self.bot.db.log_event(
                interaction.guild.id,
                'mute',
                f"{user.name} muted by {interaction.user.name} for {duration}: {reason}",
                user.id
            )
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to timeout this user.", ephemeral=True)
    
    @app_commands.command(name="unmute", description="Remove timeout from a user")
    @app_commands.describe(user="The user to unmute")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def slash_unmute(self, interaction: discord.Interaction, user: discord.Member):
        """Unmute a user"""
        try:
            await user.timeout(None)
            await interaction.response.send_message(f"✅ {user.mention} has been unmuted.")
            
            # Log the unmute
            await self.bot.db.log_event(
                interaction.guild.id,
                'unmute',
                f"{user.name} unmuted by {interaction.user.name}",
                user.id
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to unmute this user.", ephemeral=True)
    
    @app_commands.command(name="kick", description="Kick a user from the server")
    @app_commands.describe(
        user="The user to kick",
        reason="Why are you kicking this user?"
    )
    @app_commands.checks.has_permissions(kick_members=True)
    async def slash_kick(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "No reason provided"
    ):
        """Kick a user from the server"""
        await interaction.response.defer()
        
        try:
            # Check hierarchy
            if user.top_role >= interaction.user.top_role:
                await interaction.followup.send("❌ You cannot kick a user with a higher or equal role!", ephemeral=True)
                return

            # DM the user (Best effort) - BEFORE KICK
            try:
                await user.send(
                    f"👢 You have been kicked from **{interaction.guild.name}**\n"
                    f"**Reason:** {reason}"
                )
            except:
                pass

            # Perform the kick FIRST
            await user.kick(reason=reason)
            
            # If successful, Log and Respond
            await self.bot.db.add_infraction(
                user.id,
                interaction.guild.id,
                'kick',
                interaction.user.id,
                reason,
                None
            )
            
            # Send embed
            embed = kick_embed(user, interaction.user, reason)
            await interaction.followup.send(embed=embed)
            
            # Log the kick
            await self.bot.db.log_event(
                interaction.guild.id,
                'kick',
                f"{user.name} kicked by {interaction.user.name}: {reason}",
                user.id
            )
            
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to kick this user (Role Hierarchy Error).", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Kick failed: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="ban", description="Ban a user from the server")
    @app_commands.describe(
        user="The user to ban",
        reason="Why are you banning this user?",
        delete_messages="How many days of messages to delete (0-7)"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def slash_ban(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "No reason provided",
        delete_messages: int = 1
    ):
        """Ban a user from the server"""
        await interaction.response.defer()

        try:
            # Check hierarchy
            if user.top_role >= interaction.user.top_role:
                await interaction.followup.send("❌ You cannot ban a user with a higher or equal role!", ephemeral=True)
                return

            # DM the user - BEFORE BAN
            try:
                await user.send(
                    f"🔨 You have been banned from **{interaction.guild.name}**\n"
                    f"**Reason:** {reason}"
                )
            except:
                pass

            # Perform ban FIRST (Use delete_message_seconds for discord.py 2.0+)
            # delete_messages is in days, so * 86400
            seconds = min(delete_messages, 7) * 86400
            await user.ban(reason=reason, delete_message_seconds=seconds)

            # Add to database
            await self.bot.db.add_infraction(
                user.id,
                interaction.guild.id,
                'ban',
                interaction.user.id,
                reason,
                None
            )
            
            # Send embed
            embed = ban_embed(user, interaction.user, reason)
            await interaction.followup.send(embed=embed)
            
            # Log the ban
            await self.bot.db.log_event(
                interaction.guild.id,
                'ban',
                f"{user.name} banned by {interaction.user.name}: {reason}",
                user.id
            )
            
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to ban this user (Role Hierarchy Error).", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ban failed: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="userinfo", description="View detailed information about a user")
    @app_commands.describe(user="The user to get information about")
    async def slash_userinfo(self, interaction: discord.Interaction, user: discord.Member):
        """Get detailed information about a user"""
        db = self.bot.db
        
        # Get warnings and infractions
        warnings = await db.get_warnings(user.id, interaction.guild.id)
        infractions = await db.get_infractions(user.id, interaction.guild.id)
        tracking_data = await db.get_user_data(user.id, interaction.guild.id)
        
        # Create embed
        embed = user_info_embed(user, warnings, infractions, tracking_data)
        
        # Add recent warnings
        if warnings:
            recent_warnings = warnings[:5]
            warnings_text = "\n".join([
                f"• {w[4][:50]}... ({w[5][:10]})"
                for w in recent_warnings
            ])
            embed.add_field(name="Recent Warnings", value=warnings_text or "None", inline=False)
        
        # Add recent infractions
        if infractions:
            recent_infractions = infractions[:5]
            infractions_text = "\n".join([
                f"• **{i[3].upper()}**: {i[5][:50]}... ({i[7][:10]})"
                for i in recent_infractions
            ])
            embed.add_field(name="Recent Infractions", value=infractions_text or "None", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="role", description="Manage user roles (Add/Remove)")
    @app_commands.describe(user="The user to manage", role="The role to add or remove", action="Whether to add or remove the role")
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove")
    ])
    async def slash_role(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role, action: str):
        """Manage roles for a user"""
        # Admin or Bot Admin check
        is_admin = interaction.client.config.is_admin(interaction.user.id)
        is_bot_admin = await interaction.client.db.is_bot_admin(interaction.user.id)
        
        if not is_admin and not is_bot_admin and not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You don't have permission to manage roles.", ephemeral=True)
            return

        # Verification of role existence in guild
        actual_role = interaction.guild.get_role(role.id)
        if not actual_role:
             await interaction.response.send_message(f"❌ Role `{role.name}` (ID: {role.id}) not found in this server.", ephemeral=True)
             return

        # Bot Hierarchy check
        if interaction.guild.me.top_role <= actual_role:
             await interaction.response.send_message(f"❌ I cannot manage the role **{actual_role.name}** because it is higher than or equal to my own highest role!", ephemeral=True)
             return

        # User Hierarchy check (if not owner)
        if interaction.user.top_role <= actual_role and not is_admin:
             await interaction.response.send_message("❌ You cannot manage a role higher than or equal to your highest role!", ephemeral=True)
             return

        try:
            if action == "add":
                await user.add_roles(actual_role)
                await interaction.response.send_message(f"✅ Added {actual_role.mention} to {user.mention}!", ephemeral=True)
            else:
                await user.remove_roles(actual_role)
                await interaction.response.send_message(f"✅ Removed {actual_role.mention} from {user.mention}!", ephemeral=True)
            
            # Log the action
            await self.bot.db.log_event(interaction.guild.id, f"role_{action}", f"Role {actual_role.name} {action}ed to {user.name} by {interaction.user.name}", user.id)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage this role.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Role management failed: {str(e)}", ephemeral=True)

    # ==================== ADMIN COMMANDS ====================
    
    async def is_bot_admin(interaction: discord.Interaction) -> bool:
        """Check if user is a bot admin (Owner or DB Admin)"""
        bot = interaction.client
        if bot.config.is_admin(interaction.user.id):
            return True
        return await bot.db.is_bot_admin(interaction.user.id)
    
    @app_commands.command(name="lock", description="Lock a channel or category to prevent messages")
    @app_commands.describe(
        channel="The specific channel to lock",
        category="The entire category to lock (locks all channels inside)"
    )
    @app_commands.check(is_bot_admin)
    async def slash_lock(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        category: Optional[discord.CategoryChannel] = None
    ):
        """Lock a channel or category"""
        if not channel and not category:
            channel = interaction.channel

        everyone_role = interaction.guild.default_role
        
        await interaction.response.defer()
        
        locked_channels = []
        
        try:
            # Lock single channel
            if channel:
                await channel.set_permissions(everyone_role, send_messages=False)
                locked_channels.append(channel.mention)
            
            # Lock category
            if category:
                for cat_channel in category.text_channels:
                    try:
                        await cat_channel.set_permissions(everyone_role, send_messages=False)
                        locked_channels.append(cat_channel.mention)
                    except:
                        continue # Skip channels we can't manage
            
            if locked_channels:
                if len(locked_channels) > 5:
                    msg = f"🔒 Locked **{len(locked_channels)}** channels."
                else:
                    msg = f"🔒 Locked: {', '.join(locked_channels)}"
                
                await interaction.followup.send(msg)
                
                # Log the action
                await self.bot.db.log_event(
                    interaction.guild.id,
                    'admin_lock',
                    f"{interaction.user.name} locked {len(locked_channels)} channels",
                    interaction.user.id
                )
            else:
                await interaction.followup.send("❌ No channels were locked (check permissions).")
                
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to lock channels.", ephemeral=True)
    
    @app_commands.command(name="unlock", description="Unlock a channel or category to allow messages")
    @app_commands.describe(
        channel="The specific channel to unlock",
        category="The entire category to unlock (unlocks all channels inside)"
    )
    @app_commands.check(is_bot_admin)
    async def slash_unlock(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        category: Optional[discord.CategoryChannel] = None
    ):
        """Unlock a channel or category"""
        if not channel and not category:
            channel = interaction.channel

        everyone_role = interaction.guild.default_role
        
        await interaction.response.defer()
        
        unlocked_channels = []
        
        try:
            # Unlock single channel
            if channel:
                await channel.set_permissions(everyone_role, send_messages=None)
                unlocked_channels.append(channel.mention)
            
            # Unlock category
            if category:
                for cat_channel in category.text_channels:
                    try:
                        await cat_channel.set_permissions(everyone_role, send_messages=None)
                        unlocked_channels.append(cat_channel.mention)
                    except:
                        continue
            
            if unlocked_channels:
                if len(unlocked_channels) > 5:
                    msg = f"🔓 Unlocked **{len(unlocked_channels)}** channels."
                else:
                    msg = f"🔓 Unlocked: {', '.join(unlocked_channels)}"
                
                await interaction.followup.send(msg)
                
                # Log the action
                await self.bot.db.log_event(
                    interaction.guild.id,
                    'admin_unlock',
                    f"{interaction.user.name} unlocked {len(unlocked_channels)} channels",
                    interaction.user.id
                )
            else:
                await interaction.followup.send("❌ No channels were unlocked.")
                
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to unlock channels.", ephemeral=True)
    
    @app_commands.command(name="slowmode", description="Set slowmode delay for a channel")
    @app_commands.describe(
        channel="The channel to modify",
        seconds="Slowmode delay in seconds (0 to disable, max 21600)"
    )
    @app_commands.check(is_bot_admin)
    async def slash_slowmode(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        seconds: int
    ):
        """Set slowmode for a channel"""
        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message("❌ Slowmode must be between 0 and 21600 seconds (6 hours)", ephemeral=True)
            return
        
        try:
            await channel.edit(slowmode_delay=seconds)
            
            if seconds == 0:
                await interaction.response.send_message(f"✅ Slowmode disabled in {channel.mention}")
            else:
                await interaction.response.send_message(f"✅ Slowmode set to {seconds} seconds in {channel.mention}")
            
            # Log the action
            await self.bot.db.log_event(
                interaction.guild.id,
                'admin_slowmode',
                f"{interaction.user.name} set slowmode to {seconds}s in {channel.name}",
                interaction.user.id
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to edit this channel.", ephemeral=True)
    
    @app_commands.command(name="purge", description="Bulk delete messages from a channel")
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    @app_commands.check(is_bot_admin)
    async def slash_purge(self, interaction: discord.Interaction, amount: int):
        """Bulk delete messages"""
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100", ephemeral=True)
            return
        
        try:
            await interaction.response.defer(ephemeral=True)
            deleted = await interaction.channel.purge(limit=amount)
            
            await interaction.followup.send(f"✅ Deleted {len(deleted)} messages.", ephemeral=True)
            
            # Log the action
            await self.bot.db.log_event(
                interaction.guild.id,
                'admin_purge',
                f"{interaction.user.name} purged {len(deleted)} messages in {interaction.channel.name}",
                interaction.user.id
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to delete messages.", ephemeral=True)
    
    @app_commands.command(name="announce", description="Send a professional announcement")
    @app_commands.describe(
        channel="The channel to send the announcement to",
        title="Announcement title",
        message="Announcement message",
        dm_members="Whether to DM this announcement to ALL members (Use with caution!)"
    )
    @app_commands.check(is_bot_admin)
    async def slash_announce(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        message: str,
        dm_members: bool = False
    ):
        """Send an announcement"""
        await interaction.response.defer()
        
        embed = announcement_embed(title, message, interaction.user, interaction.guild)
        
        # Send to channel
        try:
            await channel.send(embed=embed)
            response_msg = f"✅ Announcement sent to {channel.mention}"
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to post in that channel.")
            return

        # Mass DM Logic
        if dm_members:
            response_msg += "\n\n**Sending DMs to members...**\n(This may take a while to avoid rate limits)"
            msg_obj = await interaction.followup.send(response_msg)
            
            # Ensure members are cached
            if not interaction.guild.chunked:
                await interaction.guild.chunk()
            
            sent_count = 0
            fail_count = 0
            
            # Create a DM-specific embed (maybe slightly different title?)
            dm_embed = announcement_embed(title, message, interaction.user, interaction.guild)
            dm_embed.title = f"📢 Announcement from {interaction.guild.name}: {title}"
            
            for member in interaction.guild.members:
                if member.bot:
                    continue
                
                try:
                    await member.send(embed=dm_embed)
                    sent_count += 1
                    # Basic rate limit protection
                    if sent_count % 10 == 0:
                        await asyncio.sleep(1) 
                except discord.Forbidden:
                    fail_count += 1 # DM closed
                except Exception:
                    fail_count += 1
            
            await msg_obj.edit(content=f"✅ Announcement sent to {channel.mention}\n\n📨 **DM Report:**\n• Sent: {sent_count}\n• Failed/Closed: {fail_count}")
        else:
            await interaction.followup.send(response_msg)
        
        # Log the action
        await self.bot.db.log_event(
            interaction.guild.id,
            'admin_announcement',
            f"{interaction.user.name} posted announcement in {channel.name} (DMs: {dm_members})",
            interaction.user.id
        )
    # ==================== UTILITY COMMANDS ====================
    
    @app_commands.command(name="serverinfo", description="View detailed server information")
    async def slash_serverinfo(self, interaction: discord.Interaction):
        """Get server information"""
        guild = interaction.guild
        
        # Count channels
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        # Count members
        total_members = guild.member_count
        bots = len([m for m in guild.members if m.bot])
        humans = total_members - bots
        
        # Get boost info
        boost_level = guild.premium_tier
        boost_count = guild.premium_subscription_count
        
        embed = create_embed(
            f"📊 {guild.name} Server Information",
            f"Detailed statistics about this server",
            discord.Color.blue(),
            [
                {'name': '👥 Members', 'value': f'**Total:** {total_members}\n**Humans:** {humans}\n**Bots:** {bots}', 'inline': True},
                {'name': '📝 Channels', 'value': f'**Text:** {text_channels}\n**Voice:** {voice_channels}\n**Categories:** {categories}', 'inline': True},
                {'name': '🚀 Boost Status', 'value': f'**Level:** {boost_level}\n**Boosts:** {boost_count}', 'inline': True},
                {'name': '👑 Owner', 'value': guild.owner.mention, 'inline': True},
                {'name': '🎭 Roles', 'value': str(len(guild.roles)), 'inline': True},
                {'name': '😊 Emojis', 'value': str(len(guild.emojis)), 'inline': True},
                {'name': '📅 Created', 'value': guild.created_at.strftime("%b %d, %Y"), 'inline': True},
                {'name': '🆔 Server ID', 'value': str(guild.id), 'inline': True},
            ]
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="stats", description="View bot statistics")
    async def slash_stats(self, interaction: discord.Interaction):
        """Get bot statistics"""
        db = self.bot.db
        
        # Get stats from database
        warnings = await db.db.execute('SELECT COUNT(*) FROM warnings WHERE guild_id = ?', (interaction.guild.id,))
        warning_count = (await warnings.fetchone())[0]
        
        infractions = await db.db.execute('SELECT COUNT(*) FROM infractions WHERE guild_id = ?', (interaction.guild.id,))
        infraction_count = (await infractions.fetchone())[0]
        
        events = await db.db.execute('SELECT COUNT(*) FROM event_logs WHERE guild_id = ?', (interaction.guild.id,))
        event_count = (await events.fetchone())[0]
        
        embed = create_embed(
            "📈 Bot Statistics",
            f"Activity statistics for {interaction.guild.name}",
            discord.Color.green(),
            [
                {'name': '⚠️ Total Warnings', 'value': str(warning_count), 'inline': True},
                {'name': '🔨 Total Infractions', 'value': str(infraction_count), 'inline': True},
                {'name': '📝 Logged Events', 'value': str(event_count), 'inline': True},
                {'name': '🤖 Bot Servers', 'value': str(len(self.bot.guilds)), 'inline': True},
                {'name': '👥 Total Users', 'value': str(len(self.bot.users)), 'inline': True},
                {'name': '⏱️ Bot Latency', 'value': f'{round(self.bot.latency * 1000)}ms', 'inline': True},
            ]
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(SlashCommands(bot))
