import discord
from discord import app_commands
from discord.ext import commands
import datetime
from utils.checks import is_bot_admin

class PollButton(discord.ui.Button):
    def __init__(self, index, label):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=label[:80], # Limit label length
            custom_id=f"poll:opt:{index}",
            row=index // 5 
        )
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view: PollView = self.view
        # Add vote to DB (poll_id = message.id)
        # We need option_index. 
        # But wait, persistent views rely on custom_id parsing usually.
        # Since I'm attaching this view to the message immediately, self.index works for this instance.
        # But if the bot restarts, we need to reconstruct the view.
        # For now, let's assume standard runtime.
        
        # Save vote
        await view.bot.db.add_poll_vote(interaction.message.id, interaction.user.id, self.index)
        
        # Update Embed
        await interaction.response.defer()
        await view.update_chart(interaction.message)


class PollView(discord.ui.View):
    def __init__(self, bot, options):
        super().__init__(timeout=None) # Persistent
        self.bot = bot
        self.options = options # List of option strings
        
        # Add buttons
        for i, option in enumerate(options):
            self.add_item(PollButton(i, option))
            
    async def update_chart(self, message: discord.Message):
        # Get votes
        votes = await self.bot.db.get_poll_votes(message.id)
        # votes is list of (option_index, count)
        
        vote_counts = {i: 0 for i in range(len(self.options))}
        total_votes = 0
        
        for option_idx, count in votes:
            if option_idx in vote_counts:
                vote_counts[option_idx] = count
                total_votes += count
                
        # Rebuild Embed Description with Chart
        embed = message.embeds[0]
        
        chart_text = ""
        
        # Calculate percentages and draw bars
        for i, option in enumerate(self.options):
            count = vote_counts[i]
            percent = (count / total_votes * 100) if total_votes > 0 else 0
            
            # Draw bar (10 segments)
            filled = int(percent / 10)
            empty = 10 - filled
            bar = "▇" * filled + "░" * empty
            
            chart_text += f"**{option}**\n`{bar}` {int(percent)}% ({count})\n\n"
            
        embed.description = chart_text
        embed.set_footer(text=f"Total Votes: {total_votes} | Click options below to vote")
        
        await message.edit(embed=embed)

class Polls(commands.Cog):
    """Professional Polling System"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="poll", description="Create an interactive poll")
    @app_commands.describe(
        question="The question to ask",
        channel="Channel to post the poll in (optional)",
        option1="Option 1",
        option2="Option 2",
        option3="Option 3 (Optional)",
        option4="Option 4 (Optional)",
        option5="Option 5 (Optional)"
    )
    async def slash_poll(
        self, 
        interaction: discord.Interaction, 
        question: str, 
        option1: str, 
        option2: str,
        channel: discord.TextChannel = None,
        option3: str = None, 
        option4: str = None, 
        option5: str = None
    ):
        """Create a poll"""
        # Admin Check
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This server is managed by Admins only.", ephemeral=True)
            return

        # Collect options
        raw_options = [option1, option2, option3, option4, option5]
        options = [opt for opt in raw_options if opt]
        
        if len(options) < 2:
            await interaction.response.send_message("❌ You need at least 2 options!", ephemeral=True)
            return
            
        target_channel = channel or interaction.channel
            
        # Create Embed
        embed = discord.Embed(
            title=f"📊 {question}",
            description="Generating poll...", # Will be replaced immediately
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text="Total Votes: 0")
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        
        if target_channel != interaction.channel:
            # Posting to another channel
            try:
                # Create View
                view = PollView(self.bot, options)
                
                message = await target_channel.send(embed=embed, view=view)
                await interaction.response.send_message(f"✅ Poll posted in {target_channel.mention}", ephemeral=True)
                
                # Update chart immediately to show empty bars (on the posted message)
                await view.update_chart(message)
                
            except discord.Forbidden:
                await interaction.response.send_message(f"❌ I don't have permission to post in {target_channel.mention}", ephemeral=True)
        else:
            # Posting in current channel
            await interaction.response.send_message(embed=embed)
            message = await interaction.original_response()
            
            # Create View
            view = PollView(self.bot, options)
            
            # Update chart immediately to show empty bars
            await view.update_chart(message)
            
            # Attach view
            await message.edit(view=view)

async def setup(bot):
    await bot.add_cog(Polls(bot))
