import discord
from discord.ext import commands
from discord import app_commands
from utils.checks import is_bot_admin

class Sticky(commands.Cog):
    """Sticky Message System"""

    def __init__(self, bot):
        self.bot = bot
        self.sticky_active = {} # Cache: {channel_id: (message, last_msg_id)}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        # Check if channel has sticky message
        # We rely on DB primarily, but maybe cache for speed? 
        # For now, hit DB to be safe and simple 
        # Optimization: Cache it
        
        sticky_data = await self.bot.db.get_sticky_message(message.channel.id)
        if sticky_data:
            sticky_text, last_msg_id = sticky_data
            
            # Delete old sticky if it exists
            if last_msg_id:
                try:
                    old_msg = await message.channel.fetch_message(last_msg_id)
                    await old_msg.delete()
                except:
                    pass
            
            # Send new stick
            try:
                embed = discord.Embed(description=sticky_text, color=discord.Color.gold())
                embed.set_footer(text="📌 Sticky Message")
                new_msg = await message.channel.send(embed=embed)
                
                # Update DB
                await self.bot.db.update_sticky_last_id(message.channel.id, new_msg.id)
                
            except Exception as e:
                print(f"Failed to stick message: {e}")

    @app_commands.command(name="stick", description="Stick a message to the bottom of the channel")
    async def stick(self, interaction: discord.Interaction, message: str):
        """Set a sticky message"""
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Missing permissions.", ephemeral=True)
            return

        # Send initial
        embed = discord.Embed(description=message, color=discord.Color.gold())
        embed.set_footer(text="📌 Sticky Message")
        sent = await interaction.channel.send(embed=embed)
        
        await self.bot.db.set_sticky_message(interaction.channel_id, message, sent.id)
        await interaction.response.send_message("✅ Message stuck!", ephemeral=True)

    @app_commands.command(name="unstick", description="Remove sticky message from channel")
    async def unstick(self, interaction: discord.Interaction):
        """Remove sticky message"""
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Missing permissions.", ephemeral=True)
            return

        try:
            # Delete last sticky if exists
            data = await self.bot.db.get_sticky_message(interaction.channel_id)
            if data and data[1]:
                try:
                    msg = await interaction.channel.fetch_message(data[1])
                    await msg.delete()
                except:
                    pass
                    
            await self.bot.db.remove_sticky_message(interaction.channel_id)
            await interaction.response.send_message("✅ Sticky message removed.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Sticky(bot))
