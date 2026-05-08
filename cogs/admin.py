import discord
from discord import app_commands
from discord.ext import commands

class Admin(commands.Cog):
    """Advanced Admin Management"""
    
    def __init__(self, bot):
        self.bot = bot

    def is_owner(self, user_id):
        # Only the config owner can add/remove admins
        return self.bot.config.is_admin(user_id)

    @app_commands.command(name="addadmin", description="Add a new Bot Admin")
    @app_commands.describe(user="The user to promote")
    async def add_admin(self, interaction: discord.Interaction, user: discord.Member):
        """Promote a user to Bot Admin"""
        if not self.is_owner(interaction.user.id):
            await interaction.response.send_message("❌ Only the Bot Owner can add admins.", ephemeral=True)
            return
            
        success = await self.bot.db.add_admin(user.id, interaction.user.id)
        if success:
            await interaction.response.send_message(f"✅ {user.mention} is now a Bot Admin!", ephemeral=True)
            # Log it
            await self.bot.db.log_event(interaction.guild.id, "admin_add", f"{user.name} promoted by {interaction.user.name}", user.id)
        else:
            await interaction.response.send_message(f"⚠️ {user.mention} is already an admin.", ephemeral=True)

    @app_commands.command(name="removeadmin", description="Remove a Bot Admin")
    @app_commands.describe(user="The user to demote")
    async def remove_admin(self, interaction: discord.Interaction, user: discord.Member):
        """Demote a Bot Admin"""
        if not self.is_owner(interaction.user.id):
            await interaction.response.send_message("❌ Only the Bot Owner can remove admins.", ephemeral=True)
            return
            
        # Optional: Prevent removing self if owner?
        if user.id == interaction.user.id:
             await interaction.response.send_message("❌ You cannot remove yourself.", ephemeral=True)
             return

        await self.bot.db.remove_admin(user.id)
        await interaction.response.send_message(f"✅ {user.mention} has been removed from admins.", ephemeral=True)
        # Log it
        await self.bot.db.log_event(interaction.guild.id, "admin_remove", f"{user.name} demoted by {interaction.user.name}", user.id)

    @app_commands.command(name="admins", description="List all Bot Admins")
    async def list_admins(self, interaction: discord.Interaction):
        """List admins"""
        # Anyone can view? Or just admins? Let's say Admins only.
        is_admin = await self.bot.db.is_bot_admin(interaction.user.id) or self.is_owner(interaction.user.id)
        if not is_admin:
             await interaction.response.send_message("❌ Admin access required.", ephemeral=True)
             return

        admin_ids = await self.bot.db.get_all_admins()
        owner_id = self.bot.config.admin_ids[0] if self.bot.config.admin_ids else None
        
        description = f"👑 **Owner**: <@{owner_id}>\n\n**Bot Admins**:\n"
        if not admin_ids:
            description += "None"
        else:
            for uid in admin_ids:
                description += f"• <@{uid}>\n"
                
        embed = discord.Embed(title="🛡️ Admin List", description=description, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="dm", description="Send a DM to a user")
    @app_commands.describe(user="User to DM", message="Message content")
    async def slash_dm(self, interaction: discord.Interaction, user: discord.Member, message: str):
        """Send DM to user"""
        if not self.is_owner(interaction.user.id) and not await self.bot.db.is_bot_admin(interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin access required.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Message from {interaction.guild.name}",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Sent by {interaction.user.name}")
        
        try:
            await user.send(embed=embed)
            await interaction.response.send_message(f"✅ DM sent to {user.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ Failed to DM {user.mention} (Privacy Settings)", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error sending DM: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))
