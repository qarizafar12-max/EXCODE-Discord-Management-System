import discord
from discord.ext import commands, tasks
import json
import asyncio
import datetime
import os
import sys

class WebIntegration(commands.Cog):
    """Handles tasks from the Web Dashboard via Database Queue"""
    
    def __init__(self, bot):
        self.bot = bot
        self.process_queue.start()
        self.sync_active_mutes.start()

    def cog_unload(self):
        self.process_queue.cancel()
        self.sync_active_mutes.cancel()

    @tasks.loop(minutes=2)
    async def sync_active_mutes(self):
        """Sync actual Discord timeouts to the database for the web dashboard"""
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            
            for guild in self.bot.guilds:
                # 1. Clear expired mutes from DB first
                await self.bot.db.clear_expired_mutes(guild.id, now.isoformat())
                
                # 2. Check all members for active timeouts
                # Note: This relies on members being cached (Chunking/Intents)
                actual_mutes = []
                for member in guild.members:
                    # Use getattr to safely check for timeout attribute (compatibility)
                    timeout_until = getattr(member, 'communication_disabled_until', None)
                    if timeout_until and timeout_until > now:
                        actual_mutes.append(member)
                        await self.bot.db.sync_current_mute(
                            member.id, 
                            guild.id, 
                            member.name, 
                            timeout_until.isoformat()
                        )
                
                # 3. Handle members who were unmuted externally (not in guild.members or timeout removed)
                db_mutes = await self.bot.db.get_current_mutes(guild.id)
                actual_ids = [m.id for m in actual_mutes]
                for db_mute in db_mutes:
                    if db_mute['user_id'] not in actual_ids:
                        await self.bot.db.remove_current_mute(db_mute['user_id'], guild.id)

            # --- PREVIOUS logic: Resolve "Unknown" names in infractions ---
            conn = await self.bot.db.db.execute("SELECT DISTINCT user_id FROM infractions WHERE user_name = 'Unknown' LIMIT 10")
            unknown_ids = await conn.fetchall()
            
            for row in unknown_ids:
                user_id = row[0]
                try:
                    user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                    if user:
                        await self.bot.db.update_infraction_name(user_id, user.name)
                        print(f"[SYNC] Resolved name for {user_id}: {user.name}")
                except Exception as e:
                    if "404" in str(e):
                        await self.bot.db.update_infraction_name(user_id, "Deleted User")
            
        except Exception as e:
            print(f"[MUTE SYNC ERROR] {e}")

    @tasks.loop(seconds=5)
    async def process_queue(self):
        """Check DB for pending tasks"""
        try:
            pending_tasks = await self.bot.db.get_pending_tasks()
            
            for task in pending_tasks:
                task_id = task[0]
                try:
                    guild_id = int(task[1]) # Ensure int
                except ValueError:
                    print(f"Invalid guild_id: {task[1]}")
                    await self.bot.db.complete_task(task_id, 'failed')
                    continue
                    
                action = task[2]
                payload = json.loads(task[3])
                
                print(f"Processing Task {task_id}: {action} for Guild {guild_id}") # Debug
                
                try:
                    await self.execute_task(guild_id, action, payload)
                    await self.bot.db.complete_task(task_id, 'completed')
                except Exception as e:
                    print(f"Failed to execute task {task_id}: {e}")
                    await self.bot.db.complete_task(task_id, 'failed')
                    
        except Exception as e:
            print(f"Queue Error: {e}")

    @process_queue.before_loop
    async def before_queue(self):
        await self.bot.wait_until_ready()

    async def execute_task(self, guild_id, action, payload):
        guild_id = int(guild_id)
        guild = self.bot.get_guild(guild_id)
        if not guild:
            try:
                guild = await self.bot.fetch_guild(guild_id)
            except:
                print(f"Guild {guild_id} not found for task.")
                return

        if action == 'test_broadcast':
             # Find log channel or fallback
             channel_id = int(payload.get('channel_id', 0))
             channel = guild.get_channel(channel_id)
             if channel:
                 await channel.send(f"🔔 **Broadcast Test**: {payload.get('message')}")

        elif action == 'send_broadcast':
            channel_id_val = payload.get('channel_id')
            if not channel_id_val:
                print(f"[ERROR] Missing channel_id in broadcast payload: {payload}")
                return
            channel_id = int(channel_id_val)
            content = payload.get('message', "")
            title = payload.get('title', 'Announcement')
            image_url = payload.get('image_url')
            thumbnail_url = payload.get('thumbnail_url')
            
            # Helper to check for image extensions
            def is_image(url):
                if not url: return False
                url = str(url).strip().lower()
                if not url.startswith('http'): return False
                return any(url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'])

            # If URLs are provided but are NOT direct images (e.g. YT, Instagram), append to content
            extra_links = []
            if image_url and not is_image(image_url):
                extra_links.append(image_url)
                image_url = None
            if thumbnail_url and not is_image(thumbnail_url):
                extra_links.append(thumbnail_url)
                thumbnail_url = None
            
            if extra_links:
                content += "\n\n" + "\n".join(extra_links)
            
            channel = guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title=f"📢 {title}",
                    description=content,
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow()
                )
                if image_url:
                    embed.set_image(url=image_url)
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)
                
                embed.set_footer(text=f"{guild.name} | Broadcast", icon_url=guild.icon.url if guild.icon else None)
                    
                await channel.send(embed=embed)
            else:
                print(f"[ERROR] Broadcast channel {channel_id} not found in guild {guild.name}")

        elif action == 'send_dm':
            user_id_val = payload.get('user_id')
            user_id = int(user_id_val) if user_id_val else None
            content = payload.get('message', "")
            title = payload.get('title', 'Message')
            image_url = payload.get('image_url')
            thumbnail_url = payload.get('thumbnail_url')
            is_mass = payload.get('is_mass', False)

            def is_image(url):
                if not url: return False
                url = str(url).strip().lower()
                if not url.startswith('http'): return False
                return any(url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'])

            extra_links = []
            if image_url and not is_image(image_url):
                extra_links.append(image_url)
                image_url = None
            if thumbnail_url and not is_image(thumbnail_url):
                extra_links.append(thumbnail_url)
                thumbnail_url = None
            
            if extra_links:
                content += "\n\n" + "\n".join(extra_links)

            # --- MASS DM LOGIC ---
            if is_mass:
                print(f"🚀 Starting MASS DM for Guild: {guild.name}")
                members = guild.members
                total = len(members)
                sent = 0
                failed = 0
                
                embed = discord.Embed(
                    title=f"📩 {title}",
                    description=content,
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                if image_url: embed.set_image(url=image_url)
                if thumbnail_url: embed.set_thumbnail(url=thumbnail_url)
                embed.set_footer(text=f"Sent from {guild.name}", icon_url=guild.icon.url if guild.icon else None)

                for i, member in enumerate(members):
                    if member.bot: continue 
                    try:
                        await member.send(embed=embed)
                        sent += 1
                        if sent % 10 == 0:
                            print(f"[MASS DM] Progress: {sent}/{total} sent...")
                        await asyncio.sleep(0.5) # Hardcoded safety delay
                    except discord.Forbidden:
                        failed += 1
                    except Exception as e:
                        failed += 1
                        print(f"[MASS DM] Error sending to {member.id}: {e}")
                
                print(f"✅ MASS DM Complete for {guild.name}. Total: {total}, Sent: {sent}, Failed: {failed}")
                return # Exit early after mass dm

            # --- SINGLE DM LOGIC ---
            if not user_id:
                print(f"❌ Skipping send_dm: No User ID provided and is_mass is false.")
                return

            # Try to get member from guild first, then global bot cache, then fetch
            user = guild.get_member(user_id) or self.bot.get_user(user_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(user_id)
                    print(f"Fetched user {user_id} from API")
                except discord.NotFound:
                    # Potential ID mixup check
                    if user_id == guild.id:
                        print(f"[WARN] User ID {user_id} matches Guild ID. Possible ID mixup.")
                    elif guild.get_channel(user_id):
                        print(f"[WARN] User ID {user_id} matches a Channel ID. Possible ID mixup.")
                    
                    print(f"[ERROR] User {user_id} not found anywhere (API/Cache)")
                    user = None
                except Exception as e:
                    print(f"[ERROR] Error fetching user {user_id}: {e}")
                    user = None

            if user:
                embed = discord.Embed(
                    title=f"📩 {title}",
                    description=content,
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                if image_url:
                    embed.set_image(url=image_url)
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)
                
                embed.set_footer(text=f"Sent from {guild.name}", icon_url=guild.icon.url if guild.icon else None)
                
                try:
                    await user.send(content=user.mention if "mention" in payload else None, embed=embed)
                    print(f"✅ DM successfully sent to {user.name} ({user_id})")
                except discord.Forbidden:
                    print(f"❌ Could not DM user {user_id} (Forbidden/DMs Closed)")
                except Exception as e:
                    print(f"❌ Error sending DM to {user_id}: {e}")
            else:
                print(f"❌ Skipping send_dm: Target user {user_id} could not be resolved.")

        elif action == 'close_ticket':
            ticket_id = payload.get('ticket_id')
            if ticket_id:
                try:
                    channel_id = int(ticket_id)
                    
                    # Update database FIRST before deleting the channel
                    await self.bot.db.close_ticket(channel_id)
                    print(f"[WEB] Marked ticket {channel_id} as closed in database")
                    
                    # Now try to delete the channel
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        try:
                            # Try fetching if not in cache
                            channel = await guild.fetch_channel(channel_id)
                            print(f"[WEB] Fetched channel {channel_id} from API (not in cache)")
                        except discord.NotFound:
                            channel = None
                            
                    if channel:
                        try:
                            await channel.send("🔒 **Ticket Closed by Web Dashboard**")
                            await asyncio.sleep(2)
                            await channel.delete()
                            print(f"[WEB] Deleted ticket channel {channel_id}")
                        except discord.Forbidden:
                            print(f"[ERROR] No permission to delete channel {channel_id}")
                        except Exception as e:
                            print(f"[ERROR] Error deleting channel {channel_id}: {e}")
                    else:
                        print(f"[WEB] Channel {channel_id} not found (even with fetch)")
                except Exception as e:
                    print(f"[ERROR] Failed to close ticket {ticket_id}: {e}")

        elif action == 'lockdown':
            print(f"Attempting Lockdown for {guild.name}")
            count = 0
            for channel in guild.text_channels:
                try:
                    await channel.set_permissions(guild.default_role, send_messages=False)
                    count += 1
                except Exception as e:
                    print(f"Failed to lock {channel.name}: {e}")
            print(f"Web Action: Lockdown executed in {guild.name} ({count} channels)")

        elif action == 'unlock':
            print(f"Attempting Unlock for {guild.name}")
            count = 0
            channels = guild.text_channels
            print(f"Found {len(channels)} text channels to unlock.")
            
            for i, channel in enumerate(channels):
                try:
                    # Check if there is actually an overwrite to clear to save API calls
                    overwrite = channel.overwrites_for(guild.default_role)
                    if overwrite.send_messages is False: # Only update if it's locked
                         await channel.set_permissions(guild.default_role, send_messages=None)
                         count += 1
                         print(f"Unlocked {channel.name} ({i+1}/{len(channels)})")
                         await asyncio.sleep(0.1) # Avoid rate limits
                    else:
                         print(f"Skipping {channel.name} (Already unlocked)")
                except Exception as e:
                    print(f"Failed to unlock {channel.name}: {e}")
            print(f"Web Action: Unlock executed in {guild.name} ({count} channels unlocked)")

        elif action == 'clear_cache':
            # Sync commands
            try:
                await self.bot.tree.sync()
                # Also maybe reload cogs? For now just sync is good "refresh"
                print(f"Web Action: Cache/Tree synced for {guild.name}")
            except Exception as e:
                print(f"Web Action: Sync failed: {e}")

        elif action == 'sync_tree':
            try:
                print("Web Action: Syncing Slash Commands...")
                synced = await self.bot.tree.sync()
                print(f"Web Action: Synced {len(synced)} commands.")
            except Exception as e:
                print(f"Web Action: Sync failed: {e}")

        elif action == 'reload_cogs':
            print("Web Action: Reloading Cogs...")
            # We need to know which cogs to reload. We can try to reload all currently loaded extensions.
            extensions = list(self.bot.extensions.keys())
            success_count = 0
            for ext in extensions:
                try:
                    await self.bot.reload_extension(ext)
                    success_count += 1
                except Exception as e:
                    print(f"Failed to reload {ext}: {e}")
            print(f"Web Action: Reloaded {success_count}/{len(extensions)} cogs.")

        elif action == 'update_priority':
            ticket_id = payload.get('ticket_id')
            new_priority = payload.get('priority')
            if ticket_id and new_priority:
                await self.bot.db.update_ticket_priority(ticket_id, new_priority)
                channel = guild.get_channel(int(ticket_id)) or await self.bot.fetch_channel(int(ticket_id))
                if channel:
                    await channel.send(f"⚡ **Priority Updated via Web**: {new_priority}")
                print(f"[WEB] Updated ticket {ticket_id} priority to {new_priority}")
            else:
                print(f"[ERROR] Missing data for update_priority: {payload}")

        elif action == 'transfer_ticket':
            ticket_id = payload.get('ticket_id')
            admin_id = payload.get('admin_id')
            if ticket_id and admin_id:
                channel = guild.get_channel(int(ticket_id)) or await self.bot.fetch_channel(int(ticket_id))
                admin = guild.get_member(int(admin_id)) or await self.bot.fetch_user(int(admin_id))
                
                admin_name = str(admin.display_name) if admin else "Unknown"
                await self.bot.db.transfer_ticket(ticket_id, admin_id, admin_name)
                
                if channel and admin:
                    await channel.set_permissions(admin, read_messages=True, send_messages=True, attach_files=True)
                    await channel.send(f"👤 **Ticket Transferred via Web** to {admin.mention}")
                print(f"[WEB] Transferred ticket {ticket_id} to {admin_id} ({admin_name})")
            else:
                print(f"[ERROR] Missing data for transfer_ticket: {payload}")

        elif action == 'restart_bot':
            print("Web Action: Restarting Bot...")
            await self.bot.close()
            # If running in a loop (like top-level while), this might just close the connection.
            # Ideally the process supervisor should restart it.
            import sys
            import os
            # Attempt to re-execute the script
            os.execv(sys.executable, ['python'] + sys.argv)

        elif action == 'unmute':
            user_id = int(payload.get('user_id'))
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)
            if member:
                try:
                    await member.timeout(None, reason="Unmuted via Web Dashboard")
                    await self.bot.db.remove_current_mute(user_id, guild_id)
                    print(f"[WEB] Unmuted {member.name} ({user_id})")
                    await self.bot.db.log_event(guild_id, 'unmute', f"Unmuted via Web Dashboard", user_id)
                except Exception as e:
                    print(f"[WEB ERROR] Failed to unmute {user_id}: {e}")
            else:
                print(f"[WEB ERROR] Member {user_id} not found for unmute")

        elif action == 'manage_bot_admin':
            user_id = int(payload.get('user_id'))
            sub_action = payload.get('sub_action') # 'add' or 'remove'
            
            if sub_action == 'add':
                success = await self.bot.db.add_admin(user_id, self.bot.user.id)
                if success:
                    print(f"[WEB] Added bot admin: {user_id}")
                else:
                    print(f"[WEB] Bot admin {user_id} already exists")
            elif sub_action == 'remove':
                await self.bot.db.remove_admin(user_id)
                print(f"[WEB] Removed bot admin: {user_id}")

        elif action == 'manage_blacklist':
            user_id = int(payload.get('user_id'))
            sub_action = payload.get('sub_action')
            
            if sub_action == 'remove_blacklist':
                await self.bot.db.remove_persistent_ban(user_id, guild_id)
                try:
                    # Attempt to unban from Discord server itself
                    await guild.unban(discord.Object(id=user_id), reason="Removed from persistent blacklist via Web")
                    print(f"[WEB] Removed from blacklist and unbanned from Discord: {user_id}")
                except Exception as e:
                    print(f"[WEB] Removed from blacklist DB, but Discord unban failed (user might not be banned): {e}")

        elif action == 'shutdown_bot':
            print("Web Action: Shutting Down Bot...")
            await self.bot.close()
            import sys
            sys.exit(0)

async def setup(bot):
    await bot.add_cog(WebIntegration(bot))
