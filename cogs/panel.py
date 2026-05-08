import discord
from discord import app_commands
from discord.ext import commands
from utils.checks import is_bot_admin

class PanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Lockdown Server", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="panel:lockdown")
    async def lockdown(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        # Check Admin
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Admin only.", ephemeral=True)
            return

        # Iterate all text channels and deny send_messages for @everyone
        count = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.set_permissions(interaction.guild.default_role, send_messages=False)
                count += 1
            except:
                pass
        
        await interaction.followup.send(f"✅ Lockdown Active! Locked {count} channels.", ephemeral=True)

    @discord.ui.button(label="Unlock Server", style=discord.ButtonStyle.success, emoji="🔓", custom_id="panel:unlock")
    async def unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
         # Check Admin
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Admin only.", ephemeral=True)
            return

        count = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.set_permissions(interaction.guild.default_role, send_messages=None) # Reset to default
                count += 1
            except:
                pass
        
        await interaction.followup.send(f"✅ Server Unlocked! Unlocked {count} channels.", ephemeral=True)
    
    @discord.ui.button(label="Toggle Anti-Raid", style=discord.ButtonStyle.primary, emoji="🛡️", custom_id="panel:antiraid")
    async def toggle_antiraid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
         # Check Admin
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Admin only.", ephemeral=True)
            return

        # We need to access AntiRaid cog
        antiraid_cog = self.bot.get_cog('AntiRaid')
        if antiraid_cog:
            current = antiraid_cog.enabled
            antiraid_cog.enabled = not current
            status = "Enabled" if not current else "Disabled"
            color = "🟢" if not current else "🔴"
            await interaction.followup.send(f"✅ Anti-Raid {status} {color}", ephemeral=True)
        else:
            await interaction.followup.send("❌ Anti-Raid cog not loaded!", ephemeral=True)

    @discord.ui.button(label="Quick Purge (100)", style=discord.ButtonStyle.secondary, emoji="🧹", custom_id="panel:purge")
    async def purge(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
         # Check Admin
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Admin only.", ephemeral=True)
            return
            
        try:
            deleted = await interaction.channel.purge(limit=100)
            await interaction.followup.send(f"✅ Purged {len(deleted)} messages.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Purge failed: {e}", ephemeral=True)


class Panel(commands.Cog):
    """Admin Control Panel"""
    
    def __init__(self, bot):
        self.bot = bot
        
    async def cog_load(self):
        self.bot.add_view(PanelView(self.bot))

    @app_commands.command(name="panel", description="Open Admin Control Panel")
    async def slash_panel(self, interaction: discord.Interaction):
        """Show the admin panel"""
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="🎛️ Server Control Panel",
            description="Manage server security and settings with one click.",
            color=discord.Color.dark_theme()
        )
        embed.set_footer(text="Admin Access Only")
        
        await interaction.response.send_message(embed=embed, view=PanelView(self.bot))

async def setup(bot):
    await bot.add_cog(Panel(bot))
