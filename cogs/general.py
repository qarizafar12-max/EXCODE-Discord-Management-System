import discord
from discord import app_commands
from discord.ext import commands
import datetime
import time
from utils.checks import is_bot_admin

class General(commands.Cog):
    """General Information Commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()

    @app_commands.command(name="help", description="Show all available commands")
    async def help_command(self, interaction: discord.Interaction):
        """Show help menu"""
        embed = discord.Embed(
            title="🧠 EXCODE BOT COMMANDS",
            description="Here is a list of everything I can do.",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="🎫 Support", value="`/setup_tickets` - Create Ticket Panel\n`/panel` - Admin Control Panel", inline=False)
        embed.add_field(name="ℹ️ General", value="`/faq` - Common Questions\n`/uptime` - Bot Status", inline=False)
        
        if await is_bot_admin(self.bot, interaction.user.id):
             embed.add_field(name="👑 Admin", value="`/lockdown` `/unlock` `/purge`", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="faq", description="Frequently Asked Questions")
    async def faq(self, interaction: discord.Interaction):
        """Show FAQ"""
        embed = discord.Embed(title="❓ Frequently Asked Questions", color=discord.Color.green())
        embed.add_field(name="How do I get help?", value="Open a ticket in the support channel!", inline=False)
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="support", description="How to contact support")
    async def support_cmd(self, interaction: discord.Interaction):
        """Show support info"""
        await interaction.response.send_message("🎫 Need help? Go to the ticket channel and click **Open Ticket**!", ephemeral=True)

    @app_commands.command(name="uptime", description="Check bot uptime and latency")
    async def uptime(self, interaction: discord.Interaction):
        """Show uptime"""
        current_time = time.time()
        uptime_seconds = int(current_time - self.start_time)
        uptime_str = str(datetime.timedelta(seconds=uptime_seconds))
        
        latency = round(self.bot.latency * 1000)
        
        embed = discord.Embed(title="⚡ System Status", color=discord.Color.green())
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Ping", value=f"{latency}ms", inline=True)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="verify", description="Verify a customer (Admin Only)")
    async def verify_user(self, interaction: discord.Interaction, user: discord.Member):
        """Verify a user"""
        if not await is_bot_admin(self.bot, interaction.user.id):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
            
        # Add 'Client' role if exists
        role = discord.utils.get(interaction.guild.roles, name="Client")
        if role:
            try:
                await user.add_roles(role)
                await interaction.response.send_message(f"✅ Verified {user.mention} as a Client!", ephemeral=True)
            except:
                 await interaction.response.send_message(f"❌ Failed to assign role. Check permissions.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 'Client' role not found in this server.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(General(bot))
