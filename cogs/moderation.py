import discord
from discord.ext import commands
from datetime import datetime, timedelta
from utils.checks import is_moderator, is_admin
from utils.embeds import warning_embed, mute_embed, kick_embed, ban_embed, user_info_embed
from utils.detection import check_message

class Moderation(commands.Cog):
    """Moderation system with auto-moderation and commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Monitor messages for auto-moderation"""
        # Skip bots and DMs
        if message.author.bot or not message.guild:
            return
        
        config = self.bot.config
        db = self.bot.db
        
        # Skip admins (config owner or bot admin from db)
        if config.is_admin(message.author.id) or await db.is_bot_admin(message.author.id):
            return
        
        # Increment message count for tracking
        await db.increment_message_count(message.author.id, message.guild.id)
        
        # Run detection checks (now async and passes db for trust scores)
        violation = await check_message(message, config, db)
        
        if violation:
            # Delete the violating message
            try:
                await message.delete()
            except:
                pass
            
            # Issue warning
            reason = f"Auto-moderation: {violation['reason']}"
            await db.add_warning(message.author.id, message.guild.id, self.bot.user.id, reason)
            
            # Get warning count
            warning_count = await db.get_warning_count(message.author.id, message.guild.id)
            
            # Send warning message
            try:
                # Get template based on violation type
                template_key = 'warning'
                if violation['type'] == 'spam':
                    template_key = 'spam_warning'
                elif violation['type'] == 'toxic':
                    template_key = 'toxic_warning'
                
                # Fetch template with fallback
                responses = getattr(config, 'moderation_responses', {})
                template = responses.get(template_key, responses.get('warning', ''))
                
                if not template:
                    # Hard fallback if config is broken
                    template = "⚠️ **Warning**\n{mention}, you have been warned for: {reason}. (Warning {count}/3)"

                # Format message
                description = template.format(
                    mention=message.author.mention,
                    reason=violation['reason'],
                    count=f"{warning_count}"
                )
                
                # Send warning embed
                embed = discord.Embed(
                    description=description,
                    color=discord.Color.orange(),
                    timestamp=datetime.utcnow()
                )
                warn_msg = await message.channel.send(embed=embed)
                
                # DM the user
                try:
                    await message.author.send(embed=embed)
                except:
                    pass
                
                # Auto-delete warning message after 5 seconds
                await warn_msg.delete(delay=5)

            except Exception as e:
                print(f"Error sending warning: {e}")
                # Fallback simple message if everything fails
                try:
                    await message.channel.send(f"⚠️ {message.author.mention} Warning: {violation['reason']}", delete_after=5)
                except:
                    pass
            
            # Log the warning
            await db.log_event(
                message.guild.id,
                'auto_warning',
                f"{message.author.name} warned for: {violation['reason']}",
                message.author.id
            )
            
            # Auto-punish after 3 warnings
            if warning_count >= config.moderation_settings.get('warnings_before_mute', 3):
                try:
                    # Check past infractions for escalation
                    infractions = await db.get_infractions(message.author.id, message.guild.id)
                    
                    has_been_muted = any(i[3] == 'mute' for i in infractions) # type is index 3
                    has_been_kicked = any(i[3] == 'kick' for i in infractions)
                    
                    punishment_reason = "Exceeded warning limit (Escalated)"
                    
                    # ESCALATION LOGIC
                    if has_been_kicked:
                        # Escalation: BAN
                        template = config.moderation_responses.get('ban', '🚫 **{mention}** has been permanently banned for: **{reason}**')
                        desc = template.format(mention=message.author.mention, reason=punishment_reason)

                        await message.author.ban(reason=punishment_reason, delete_message_seconds=604800) # 7 days msg del
                        
                        await db.add_infraction(message.author.id, message.guild.id, 'ban', self.bot.user.id, punishment_reason, None, user_name=message.author.name)
                        # Add to persistent blacklist
                        await db.add_persistent_ban(message.author.id, message.guild.id, message.author.name, punishment_reason)
                        
                        await message.channel.send(embed=discord.Embed(description=desc, color=discord.Color.dark_red()))
                        
                    elif has_been_muted:
                        # Escalation: KICK
                        template = config.moderation_responses.get('kick', '')
                        desc = template.format(mention=message.author.mention, reason=punishment_reason)
                        
                        await message.author.kick(reason=punishment_reason)
                        
                        await db.add_infraction(message.author.id, message.guild.id, 'kick', self.bot.user.id, punishment_reason, None, user_name=message.author.name)
                        await message.channel.send(embed=discord.Embed(description=desc, color=discord.Color.dark_red()))
                        
                    else:
                        # Initial Punishment: MUTE
                        duration_secs = 600 # 10 mins
                        duration_str = "10m"
                        
                        template = config.moderation_responses.get('mute', '🔇 **{mention}** has been muted for {duration} | Reason: **{reason}**')
                        desc = template.format(mention=message.author.mention, duration=duration_str, reason=punishment_reason)
                        
                        await message.author.timeout(timedelta(seconds=duration_secs), reason=punishment_reason)
                        
                        await db.add_infraction(message.author.id, message.guild.id, 'mute', self.bot.user.id, punishment_reason, duration_secs, user_name=message.author.name)
                        await message.channel.send(embed=discord.Embed(description=desc, color=discord.Color.red()))
                    
                    # Reset warnings after punishment
                    await db.clear_warnings(message.author.id, message.guild.id)
                    
                except discord.Forbidden:
                    await message.channel.send("❌ I tried to punish this user but I lack permissions.")
                except Exception as e:
                    print(f"Error in auto-punishment: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Check for persistent bans on join"""
        db = self.bot.db
        is_banned = await db.is_persistently_banned(member.id, member.guild.id)
        
        if is_banned:
            try:
                # Get ban reason if possible (optional)
                reason = "Persistent Ban (Blacklist Enforcement)"
                
                # Kick immediately if they rejoin
                await member.kick(reason=reason)
                
                # Log the enforcement
                await db.log_event(
                    member.guild.id,
                    'blacklist_enforcement',
                    f"Blocked {member.name} ({member.id}) from rejoining due to persistent ban.",
                    member.id
                )
                print(f"[BLACKLIST] Enforced ban on {member.name} in {member.guild.id}")
            except Exception as e:
                print(f"[BLACKLIST ERROR] Could not enforce ban on {member.id}: {e}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        """Sync manual Discord bans to persistent blacklist"""
        try:
            # Default reason
            reason = "Manual Ban (Synced from Discord)"
            moderator_id = self.bot.user.id # Default to bot if audit log fails

            # Try to fetch audit logs to get real reason and mod
            if guild.me.guild_permissions.view_audit_log:
                async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                    if entry.target.id == user.id:
                        reason = entry.reason or reason
                        moderator_id = entry.user.id
                        break
            
            # Add to persistent blacklist
            await self.bot.db.add_persistent_ban(user.id, guild.id, user.name, reason)
            
            # Log it
            await self.bot.db.log_event(
                guild.id,
                'ban_sync',
                f"Synced manual ban for {user.name} ({user.id}). Reason: {reason}",
                user.id
            )
            print(f"[SYNC] Added manual ban for {user.name} to persistent blacklist.")
            
        except Exception as e:
            print(f"[SYNC ERROR] Failed to sync ban for {user.id}: {e}")
    
    @commands.command(name='warn')
    @is_moderator()
    async def warn_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """Warn a user"""
        db = self.bot.db
        
        # Add warning
        await db.add_warning(member.id, ctx.guild.id, ctx.author.id, reason)
        
        # Get warning count
        warning_count = await db.get_warning_count(member.id, ctx.guild.id)
        
        # Get template
        template = db.bot.config.moderation_responses.get('warning', '')
        description = template.format(
            mention=member.mention,
            reason=reason,
            count=f"{warning_count}"
        )
        
        # Create and send embed
        embed = discord.Embed(
            description=description,
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        await ctx.send(embed=embed)
        
        # Log the warning
        await db.log_event(
            ctx.guild.id,
            'warning',
            f"{member.name} warned by {ctx.author.name}: {reason}",
            member.id
        )
        
        # DM the user
        try:
            await member.send(
                f"⚠️ You have been warned in **{ctx.guild.name}**\n"
                f"**Reason:** {reason}\n"
                f"**Total warnings:** {warning_count}/3"
            )
        except:
            pass
    
    @commands.command(name='mute')
    @is_moderator()
    async def mute_user(self, ctx, member: discord.Member, duration: str = "10m", *, reason: str = "No reason provided"):
        """Mute a user for a specified duration (e.g., 10m, 1h, 1d)"""
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
            await ctx.send("❌ Invalid duration format. Use format like: 10m, 1h, 2d")
            return
        
        # Apply timeout
        try:
            timeout_duration = timedelta(seconds=seconds)
            await member.timeout(timeout_duration, reason=reason)
            
            # Add to database
            await self.bot.db.add_infraction(
                member.id,
                ctx.guild.id,
                'mute',
                ctx.author.id,
                reason,
                seconds,
                user_name=member.name
            )
            
            # Send confirmation
            template = self.bot.config.moderation_responses.get('mute', '')
            description = template.format(
                mention=member.mention,
                reason=reason,
                duration=duration
            )
            
            embed = discord.Embed(
                description=description,
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            await ctx.send(embed=embed)
            
            # Sync to current_mutes
            member_timeout = getattr(member, 'communication_disabled_until', None)
            if member_timeout:
                await self.bot.db.sync_current_mute(
                    member.id, 
                    ctx.guild.id, 
                    member.name, 
                    member_timeout.isoformat()
                )

            # Log the mute
            await self.bot.db.log_event(
                ctx.guild.id,
                'mute',
                f"{member.name} muted by {ctx.author.name} for {duration}: {reason}",
                member.id
            )
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to timeout this user.")
    
    @commands.command(name='unmute')
    @is_moderator()
    async def unmute_user(self, ctx, member: discord.Member):
        """Unmute a user"""
        try:
            await member.timeout(None)
            await self.bot.db.remove_current_mute(member.id, ctx.guild.id)
            await ctx.send(f"✅ {member.mention} has been unmuted.")
            
            # Log the unmute
            await self.bot.db.log_event(
                ctx.guild.id,
                'unmute',
                f"{member.name} unmuted by {ctx.author.name}",
                member.id
            )
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to unmute this user.")
    
    @commands.command(name='kick')
    @is_moderator()
    async def kick_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """Kick a user from the server"""
        try:
            # Check hierarchy
            if member.top_role >= ctx.author.top_role:
                await ctx.send("❌ You cannot kick a user with a higher or equal role!")
                return

            # DM the user (Best effort) - BEFORE KICK
            try:
                await member.send(
                    f"👢 You have been kicked from **{ctx.guild.name}**\n"
                    f"**Reason:** {reason}"
                )
            except:
                pass

            # Kick the user
            await member.kick(reason=reason)
            
            # Add to database
            await self.bot.db.add_infraction(
                member.id,
                ctx.guild.id,
                'kick',
                ctx.author.id,
                reason,
                None,
                user_name=member.name
            )
            
            # Send embed
            template = self.bot.config.moderation_responses.get('kick', '')
            description = template.format(
                mention=member.mention,
                reason=reason
            )
            
            embed = discord.Embed(
                description=description,
                color=discord.Color.dark_red(),
                timestamp=datetime.utcnow()
            )
            await ctx.send(embed=embed)
            
            # Log the kick
            await self.bot.db.log_event(
                ctx.guild.id,
                'kick',
                f"{member.name} kicked by {ctx.author.name}: {reason}",
                member.id
            )
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to kick this user (Role Hierarchy).")
        except Exception as e:
            await ctx.send(f"❌ Kick failed: {str(e)}")
    
    @commands.command(name='ban')
    @is_moderator()
    async def ban_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """Ban a user from the server"""
        try:
            # Check hierarchy
            if member.top_role >= ctx.author.top_role:
                await ctx.send("❌ You cannot ban a user with a higher or equal role!")
                return

            # DM the user - BEFORE BAN
            try:
                await member.send(
                    f"🔨 You have been banned from **{ctx.guild.name}**\n"
                    f"**Reason:** {reason}"
                )
            except:
                pass

            # Ban the user (use delete_message_seconds)
            await member.ban(reason=reason, delete_message_seconds=86400) # 1 day default
            
            # Add to database
            await self.bot.db.add_infraction(
                member.id,
                ctx.guild.id,
                'ban',
                ctx.author.id,
                reason,
                None,
                user_name=member.name
            )
            
            # Add to persistent blacklist
            await self.bot.db.add_persistent_ban(member.id, ctx.guild.id, member.name, reason)
            
            # Send embed
            template = self.bot.config.moderation_responses.get('ban', '')
            description = template.format(
                mention=member.mention,
                reason=reason
            )
            
            embed = discord.Embed(
                description=description,
                color=discord.Color.dark_red(),
                timestamp=datetime.utcnow()
            )
            await ctx.send(embed=embed)
            
            # Log the ban
            await self.bot.db.log_event(
                ctx.guild.id,
                'ban',
                f"{member.name} banned by {ctx.author.name}: {reason}",
                member.id
            )
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to ban this user.")
        except Exception as e:
            await ctx.send(f"❌ Ban failed: {str(e)}")

    @commands.command(name='sync_bans')
    @is_admin()
    async def sync_bans(self, ctx):
        """Sync all current Discord bans to the persistent blacklist"""
        if not ctx.guild.me.guild_permissions.ban_members:
            await ctx.send("❌ I need 'Ban Members' permission to view the ban list.")
            return
            
        await ctx.send("🔄 Syncing bans... this might take a moment.")
        
        count = 0
        try:
            async for entry in ctx.guild.bans(limit=None):
                user = entry.user
                reason = entry.reason or "Manual Ban (Synced via !sync_bans)"
                
                # Check if already exists to avoid overwriting original reasons if simpler
                if not await self.bot.db.is_persistently_banned(user.id, ctx.guild.id):
                    await self.bot.db.add_persistent_ban(user.id, ctx.guild.id, user.name, reason)
                    count += 1
            
            await ctx.send(f"✅ Sync complete! Added **{count}** users to the persistent blacklist.")
            
        except Exception as e:
            await ctx.send(f"❌ Sync failed: {e}")
            print(f"Sync error: {e}")
    

async def setup(bot):
    await bot.add_cog(Moderation(bot))
