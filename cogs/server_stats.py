import discord
from discord.ext import commands, tasks
from discord import app_commands
from utils.checks import is_bot_admin

class ServerStats(commands.Cog):
    """Dynamic Server Statistics"""

    def __init__(self, bot):
        self.bot = bot
        self.update_stats.start()

    def cog_unload(self):
        self.update_stats.cancel()

    async def get_stats_channels(self, guild_id):
        """Get stats channel IDs from DB"""
        # We need to add this to settings or just store in guild_settings
        # Implementation: use guild_settings
        # Format: key="stats_channel_type", value="channel_id"
        # Types: stats_members, stats_bots, stats_boosts
        
        channels = {}
        for safe_key in ['stats_members', 'stats_bots', 'stats_boosts']:
             val = await self.bot.db.get_setting(guild_id, safe_key)
             if val:
                 channels[safe_key] = int(val)
        return channels

    @tasks.loop(minutes=10)
    async def update_stats(self):
        """Update stats channels periodically"""
        for guild in self.bot.guilds:
            await self.update_guild_stats(guild)

    @update_stats.before_loop
    async def before_update_stats(self):
        await self.bot.wait_until_ready()

    async def update_guild_stats(self, guild):
        channels = await self.get_stats_channels(guild.id)
        if not channels:
            return

        # Data
        member_count = guild.member_count
        bot_count = sum(1 for m in guild.members if m.bot)
        human_count = member_count - bot_count
        boost_count = guild.premium_subscription_count

        # Update Channels
        try:
            if 'stats_members' in channels:
                chan = guild.get_channel(channels['stats_members'])
                if chan:
                    await chan.edit(name=f"👥 Members: {human_count}")
            
            if 'stats_bots' in channels:
                chan = guild.get_channel(channels['stats_bots'])
                if chan:
                    await chan.edit(name=f"🤖 Bots: {bot_count}")
                    
            if 'stats_boosts' in channels:
                chan = guild.get_channel(channels['stats_boosts'])
                if chan:
                    await chan.edit(name=f"💎 Boosts: {boost_count}")
        except Exception as e:
            print(f"Failed to update stats for {guild.name}: {e}")

    @app_commands.command(name="setupstats", description="Setup server statistics channels")
    async def setup_stats(self, interaction: discord.Interaction):
        """Create stats channels"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        # Create Category
        try:
            category = await guild.create_category("📊 Server Stats")
            await category.set_permissions(guild.default_role, connect=False, view_channel=True)
            
            # Create Channels
            # Members
            chan_members = await guild.create_voice_channel(f"👥 Members: {len([m for m in guild.members if not m.bot])}", category=category)
            await self.bot.db.set_setting(guild.id, 'stats_members', chan_members.id)
            
            # Bots
            chan_bots = await guild.create_voice_channel(f"🤖 Bots: {sum(1 for m in guild.members if m.bot)}", category=category)
            await self.bot.db.set_setting(guild.id, 'stats_bots', chan_bots.id)
            
            # Boosts
            chan_boosts = await guild.create_voice_channel(f"💎 Boosts: {guild.premium_subscription_count}", category=category)
            await self.bot.db.set_setting(guild.id, 'stats_boosts', chan_boosts.id)

            await interaction.followup.send("✅ Server statistics channels created!")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to setup stats: {e}")

    @app_commands.command(name="updatestats", description="Force update server statistics")
    async def force_update_stats(self, interaction: discord.Interaction):
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
             await interaction.response.send_message("❌ Admin only.", ephemeral=True)
             return
        
        await interaction.response.defer(ephemeral=True)
        await self.update_guild_stats(interaction.guild)
        await interaction.followup.send("✅ Stats updated!")

async def setup(bot):
    await bot.add_cog(ServerStats(bot))
