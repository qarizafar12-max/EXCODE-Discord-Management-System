import discord
from discord import app_commands
from discord.ext import commands
from utils.settings import SettingsManager
from utils.checks import is_bot_admin

class Setup(commands.Cog):
    """Smart Auto-Configuration System"""
    
    def __init__(self, bot):
        self.bot = bot
        self.settings = SettingsManager(bot)
    
    async def smart_scan(self, guild: discord.Guild):
        """Scan guild for setup configuration"""
        results = {
            'channels': [],
            'roles': [],
            'security': []
        }
        
        # 1. Scan Channels
        channels_map = {
            'welcome': ['welcome', 'joins', 'arrivals', 'new-members'],
            'rules': ['rules', 'guidelines', 'info', 'regulations'],
            'logs': ['logs', 'mod-logs', 'server-logs', 'audit-logs', 'bot-logs']
        }
        
        for channel in guild.text_channels:
            name = channel.name.lower()
            for key, keywords in channels_map.items():
                # Check if current setting is already set (optional, maybe overwrite?)
                # For now, we only set if found
                if any(k in name for k in keywords):
                    # Check if not already set or we want to prioritize exact matches?
                    # Let's just take the first match
                     await self.settings.set_setting(guild.id, f"{key}_channel", str(channel.id))
                     results['channels'].append(f"Set **{key}** to {channel.mention}")
                     break # Found a match for this key, move to next channel? No, one channel can't be multiple things usually.
                     # Actually, break inner loop to stop checking keywords for this key

        # 2. Scan Roles
        auto_role_keywords = ['member', 'citizen', 'verified', 'user', 'community']
        for role in guild.roles:
            if role.is_default(): continue # Skip @everyone
            if role.managed: continue # Skip bot roles
            
            name = role.name.lower()
            if any(k in name for k in auto_role_keywords):
                await self.settings.set_setting(guild.id, "auto_role", str(role.id))
                results['roles'].append(f"Set **Auto-Role** to {role.mention}")
                break # Only need one
                
        # 3. Security Audit
        everyone = guild.default_role
        if everyone.permissions.administrator:
            results['security'].append("⚠️ **CRITICAL**: `@everyone` has Administrator permissions!")
        if everyone.permissions.mention_everyone:
            results['security'].append("⚠️ **WARNING**: `@everyone` can mention @everyone!")
        if everyone.permissions.manage_guild:
            results['security'].append("⚠️ **WARNING**: `@everyone` can manage server!")
            
        return results

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Run smart scan on join"""
        results = await self.smart_scan(guild)
        
        # Build Summary
        embed = discord.Embed(
            title=f"🤖 Setup Complete for {guild.name}",
            description="I have automatically configured the following settings based on your server structure.",
            color=discord.Color.green()
        )
        
        if results['channels']:
            embed.add_field(name="📺 Channels Detected", value="\n".join(results['channels']), inline=False)
        
        if results['roles']:
            embed.add_field(name="🧢 Roles Detected", value="\n".join(results['roles']), inline=False)
            
        if results['security']:
            embed.add_field(name="🛡️ Security Audit", value="\n".join(results['security']), inline=False)
            
        # Send to owner or system channel
        target = guild.system_channel or guild.owner
        if target:
            try:
                await target.send(embed=embed)
            except:
                pass

    @app_commands.command(name="setup", description="Run smart auto-configuration")
    @app_commands.describe(mode="Mode to run (auto)")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Auto Scan", value="auto")
    ])
    async def slash_setup(self, interaction: discord.Interaction, mode: str):
        """Run setup"""
        # Admin Check
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command is for Admins only.", ephemeral=True)
            return
            
        if mode == "auto":
            await interaction.response.defer()
            results = await self.smart_scan(interaction.guild)
            
            embed = discord.Embed(
                title="🤖 Smart Setup Results",
                description="Configuration updated based on scan.",
                color=discord.Color.green()
            )
            
            if results['channels']:
                embed.add_field(name="📺 Channels Set", value="\n".join(results['channels']), inline=False)
            else:
                 embed.add_field(name="📺 Channels", value="No matching channels found.", inline=False)
            
            if results['roles']:
                embed.add_field(name="🧢 Roles Set", value="\n".join(results['roles']), inline=False)
                
            if results['security']:
                embed.add_field(name="🛡️ Security Alerts", value="\n".join(results['security']), inline=False)
            else:
                embed.add_field(name="🛡️ Security", value="No immediate issues found.", inline=False)
                
            await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Setup(bot))
