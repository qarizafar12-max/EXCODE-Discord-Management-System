import discord
from discord import app_commands
from discord.ext import commands
from utils.embeds import create_embed
import datetime
from utils.checks import is_bot_admin

class SuggestionView(discord.ui.View):
    def __init__(self, bot, author_id):
        super().__init__(timeout=None) # Persistent view
        self.bot = bot
        self.author_id = author_id
        
    async def update_votes(self, interaction: discord.Interaction, message: discord.Message):
        # Calculate votes from DB
        votes = await self.bot.db.get_poll_votes(message.id)
        # votes is list of (option_index, count)
        
        upvotes = 0
        downvotes = 0
        
        for option, count in votes:
            if option == 1:
                upvotes = count
            elif option == 2:
                downvotes = count
                
        # Update embed
        embed = message.embeds[0]
        # Allow negative (downvotes) to show ratio? Or just raw counts.
        # Let's show: 👍 5  |  👎 2
        
        embed.set_field_at(0, name="Votes", value=f"👍 **{upvotes}**   |   👎 **{downvotes}**", inline=False)
        
        # Determine color based on ratio
        if upvotes > downvotes + 2:
            embed.color = discord.Color.green()
        elif downvotes > upvotes + 2:
            embed.color = discord.Color.red()
        else:
            embed.color = discord.Color.gold()
            
        await message.edit(embed=embed)
        
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, emoji="👍", custom_id="suggest:up")
    async def upvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Option 1 = Upvote
        result = await self.bot.db.add_poll_vote(interaction.message.id, interaction.user.id, 1)
        if result:
            await interaction.response.defer()
            await self.update_votes(interaction, interaction.message)
        else:
            await interaction.response.send_message("❌ Database error.", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, emoji="👎", custom_id="suggest:down")
    async def downvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Option 2 = Downvote
        result = await self.bot.db.add_poll_vote(interaction.message.id, interaction.user.id, 2)
        if result:
            await interaction.response.defer()
            await self.update_votes(interaction, interaction.message)
        else:
            await interaction.response.send_message("❌ Database error.", ephemeral=True)
            
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.grey, emoji="🗑️", custom_id="suggest:delete")
    async def delete_suggestion(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only admin, bot admin, or author can delete
        is_admin = await is_bot_admin(self.bot, interaction.user.id)
        if interaction.user.id == self.author_id or is_admin or interaction.user.guild_permissions.manage_messages:
            await interaction.message.delete()
            await interaction.response.send_message("✅ Suggestion deleted.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You cannot delete this suggestion.", ephemeral=True)

class Suggestions(commands.Cog):
    """Community suggestion system"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="suggest", description="Submit a suggestion for the server")
    @app_commands.describe(
        idea="Your suggestion",
        channel="Channel to post the suggestion in (optional)"
    )
    async def slash_suggest(
        self, 
        interaction: discord.Interaction, 
        idea: str,
        channel: discord.TextChannel = None
    ):
        """Submit a suggestion"""
        # Admin Check
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This server is managed by Admins only.", ephemeral=True)
            return

        settings = self.bot.config.suggestions_settings
        
        # Determine target channel: Argument > Config > Current
        target_channel = channel
        
        if not target_channel:
            config_channel_id = settings.get('channel_id')
            if config_channel_id:
                found = interaction.guild.get_channel(config_channel_id)
                if found:
                    target_channel = found
        
        if not target_channel:
            target_channel = interaction.channel
                
        # Create Embed
        embed = discord.Embed(
            title="💡 New Suggestion",
            description=idea,
            color=discord.Color.gold(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Votes", value="👍 **0**   |   👎 **0**", inline=False)
        embed.set_footer(text=f"User ID: {interaction.user.id} • Status: Pending")
        
        # Send to target channel
        if target_channel != interaction.channel:
             # Check permissions first
             try:
                message = await target_channel.send(embed=embed, view=SuggestionView(self.bot, interaction.user.id))
                await interaction.response.send_message(f"✅ Suggestion posted in {target_channel.mention}", ephemeral=True)
             except discord.Forbidden:
                await interaction.response.send_message(f"❌ I don't have permission to post in {target_channel.mention}", ephemeral=True)
                return
        else:
             await interaction.response.send_message("✅ Suggestion posted below!", ephemeral=True)
             # Send new message even in same channel to ensure clean embed
             message = await interaction.channel.send(embed=embed, view=SuggestionView(self.bot, interaction.user.id))

        # Auto-thread
        if settings.get('auto_thread', True):
            try:
                await message.create_thread(name=f"Discussion: {idea[:20]}...")
            except:
                pass

async def setup(bot):
    await bot.add_cog(Suggestions(bot))
