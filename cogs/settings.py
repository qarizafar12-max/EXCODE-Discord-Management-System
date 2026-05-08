import discord
from discord import app_commands
from discord.ext import commands
from utils.checks import is_bot_admin
from utils.settings import SettingsManager

class Settings(commands.Cog):
    """Manage server settings"""
    
    def __init__(self, bot):
        self.bot = bot
        self.settings = SettingsManager(bot)
    
    @app_commands.command(name="settings", description="View or Edit Server Settings")
    @app_commands.describe(action="view or set", key="Setting key (e.g., welcome_channel)", value="Value to set")
    @app_commands.choices(action=[
        app_commands.Choice(name="View Settings", value="view"),
        app_commands.Choice(name="Set Value", value="set")
    ])
    @app_commands.choices(key=[
        app_commands.Choice(name="Welcome Channel (ID)", value="welcome_channel"),
        app_commands.Choice(name="Rules Channel (ID)", value="rules_channel"),
        app_commands.Choice(name="Logs Channel (ID)", value="logs_channel"),
        app_commands.Choice(name="Auto Role (Name/ID)", value="auto_role"),
        app_commands.Choice(name="Welcome Message (Channel)", value="welcome_message"),
        app_commands.Choice(name="Welcome DM (Direct Message)", value="welcome_dm")
    ])
    async def slash_settings(self, interaction: discord.Interaction, action: str, key: str = None, value: str = None):
        """Manage settings"""
        # Admin Check
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command is for Admins only.", ephemeral=True)
            return

        if action == "view":
            embed = discord.Embed(title=f"⚙️ Settings for {interaction.guild.name}", color=discord.Color.blue())
            
            keys = ['welcome_channel', 'rules_channel', 'logs_channel', 'auto_role', 'welcome_message', 'welcome_dm']
            for k in keys:
                val = await self.settings.get_setting(interaction.guild.id, k, "Not Set")
                # Try to resolve channel names
                if 'channel' in k and val != "Not Set":
                    try:
                        channel = interaction.guild.get_channel(int(val))
                        if channel:
                            val = channel.mention
                    except:
                        pass
                
                embed.add_field(name=k.replace('_', ' ').title(), value=str(val), inline=True)
                
            await interaction.response.send_message(embed=embed)
            
        elif action == "set":
            if not key or not value:
                await interaction.response.send_message("❌ Please provide both key and value.", ephemeral=True)
                return
                
            # If value is a channel mention, extract ID
            if value.startswith('<#') and value.endswith('>'):
                value = value[2:-1]
            
            await self.settings.set_setting(interaction.guild.id, key, value)
            await interaction.response.send_message(f"✅ Set **{key}** to `{value}`")

async def setup(bot):
    await bot.add_cog(Settings(bot))
