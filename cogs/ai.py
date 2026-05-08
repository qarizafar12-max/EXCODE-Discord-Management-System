import discord
from discord import app_commands
from discord.ext import commands
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from utils.embeds import create_embed
from utils.checks import is_bot_admin
import time
from collections import defaultdict

class AI(commands.Cog):
    """Lightweight AI server management (VADER Sentiment)"""
    
    def __init__(self, bot):
        self.bot = bot
        self.analyzer = SentimentIntensityAnalyzer()
        self.ai_enabled = True # VADER is always ready
        
        # Structure: {channel_id: [(timestamp, sentiment_score), ...]}
        self.channel_sentiment_history = defaultdict(list)
        self.active_slowmodes = set()

    def get_sentiment(self, text):
        """Get sentiment score (-1 to 1)"""
        scores = self.analyzer.polarity_scores(text)
        return scores['compound']

    def sentiment_to_text(self, score):
        """Convert score to readable text"""
        if score >= 0.5: return "Positive 🟢"
        if score >= 0.05: return "Slightly Positive 🙂"
        if score <= -0.5: return "Toxic/Negative 🔴"
        if score <= -0.05: return "Slightly Negative 🙁"
        return "Neutral ⚪"

    @commands.Cog.listener()
    async def on_message(self, message):
        """Monitor messages for toxicity"""
        if message.author.bot or not message.content:
            return
            
        if await is_bot_admin(self.bot, message.author.id):
            return

        ai_config = self.bot.config.ai_settings
        if not ai_config.get('enabled', True):
            return

        # Check Toxicity
        score = self.get_sentiment(message.content)
        threshold = ai_config.get('sentiment_threshold', -0.8)
        
        # Update channel sentiment history
        now = time.time()
        self.channel_sentiment_history[message.channel.id].append((now, score))
        
        # Clean up old history (keep only last 60 seconds)
        cutoff = now - 60
        self.channel_sentiment_history[message.channel.id] = [
            (ts, s) for (ts, s) in self.channel_sentiment_history[message.channel.id] 
            if ts > cutoff
        ]
        
        # Dynamic Slowmode Check
        if message.channel.id not in self.active_slowmodes and message.channel.permissions_for(message.guild.me).manage_channels:
            recent_negatives = [s for (ts, s) in self.channel_sentiment_history[message.channel.id] if s < -0.5]
            
            # If 5 negative messages in 60 seconds
            if len(recent_negatives) >= 5:
                self.active_slowmodes.add(message.channel.id)
                try:
                    await message.channel.edit(slowmode_delay=10, reason="AI Supervisor: Argument detected. Cooling down.")
                    
                    embed = discord.Embed(
                        title="⚠️ AI Supervisor Intervention",
                        description="I've detected a high volume of negative sentiment in this channel recently. "
                                    "I have temporarily enabled a 10-second slowmode to help cool things down.\n\n"
                                    "Please remember to keep conversations respectful.",
                        color=discord.Color.orange()
                    )
                    await message.channel.send(embed=embed)
                    
                    # Schedule removal of slowmode after 5 minutes
                    self.bot.loop.create_task(self.remove_slowmode(message.channel, 300))
                except discord.Forbidden:
                    # Ignore if permissions lacking
                    self.active_slowmodes.remove(message.channel.id)

        # Basic Deletion Check (Old Logic)
        
        # If score is lower (more negative) than threshold, it's flagged
        if score < threshold:
            try:
                await message.delete()
                
                await self.bot.db.log_event(
                    message.guild.id,
                    'ai_moderation_toxicity',
                    f"Sentiment flagged ({score}): {message.content}",
                    message.author.id
                )
            except:
                pass

    async def remove_slowmode(self, channel, delay):
        """Removes slowmode after the specified delay."""
        import asyncio
        await asyncio.sleep(delay)
        
        if channel.id in self.active_slowmodes:
            try:
                # We assume we put it to 10. We turn it off (0). 
                # (A more robust system would save the previous slowmode, but this is simple enough)
                if channel.permissions_for(channel.guild.me).manage_channels:
                   await channel.edit(slowmode_delay=0, reason="AI Supervisor: Cooldown period ended.")
            except discord.Forbidden:
                pass
            finally:
                self.active_slowmodes.remove(channel.id)

    @app_commands.command(name="mood", description="Analyze the mood of the current channel")
    async def analyze_mood(self, interaction: discord.Interaction):
        """Analyze channel mood"""
        await interaction.response.defer()

        scores = []
        async for msg in interaction.channel.history(limit=50):
            if not msg.author.bot and msg.content:
                scores.append(self.get_sentiment(msg.content))

        if not scores:
            await interaction.followup.send("Not enough messages to analyze.")
            return

        avg_score = sum(scores) / len(scores)
        status = self.sentiment_to_text(avg_score)
        
        embed = create_embed(
            "🧠 Channel Mood Analysis",
            f"**Status**: {status}\n**Score**: {avg_score:.2f} (-1 to 1)\n**Sample Size**: {len(scores)} messages",
            discord.Color.purple()
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ai_user", description="Generate a behavior report for a user")
    @app_commands.describe(user="The user to analyze")
    async def analyze_user(self, interaction: discord.Interaction, user: discord.Member):
        """Analyze a user's behavior"""
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.kick_members:
             await interaction.response.send_message("❌ Admin/Mod only.", ephemeral=True)
             return

        await interaction.response.defer()
        
        scores = []
        msg_count = 0
        async for msg in interaction.channel.history(limit=100):
            if msg.author.id == user.id and msg.content:
                scores.append(self.get_sentiment(msg.content))
                msg_count += 1
        
        if not scores:
            await interaction.followup.send("No recent messages found for this user.")
            return

        avg_score = sum(scores) / len(scores)
        status = self.sentiment_to_text(avg_score)
        
        verdict = "Trusted Member"
        color = discord.Color.green()
        
        if avg_score < -0.3:
            verdict = "High Risk / Toxic"
            color = discord.Color.red()
        elif avg_score < 0:
            verdict = "Potential Risk"
            color = discord.Color.orange()
            
        embed = create_embed(
            f"🕵️ Automated User Analysis: {user.name}",
            f"**Verdict**: {verdict}\n**Sentiment**: {status} ({avg_score:.2f})\n**Activity**: {msg_count} recent messages",
            color
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="server_insight", description="Get insights on server health")
    async def server_insight(self, interaction: discord.Interaction):
        """Analyze server stats (Heuristic based)"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        guild = interaction.guild
        tips = []
        
        # Simple heuristics logic
        if guild.member_count < 10:
            tips.append("• **Growth**: You're starting small! Try inviting friends or posting on social media.")
        elif guild.member_count > 100 and len(guild.text_channels) < 3:
            tips.append("• **Structure**: You might need more channels to organize this many members.")
            
        if len(guild.roles) < 3:
            tips.append("• **Roles**: Consider adding more roles (e.g., 'Member', 'VIP') to reward activity.")
            
        if not tips:
            tips.append("• **Engagement**: Try hosting a weekly event or game night.")
            tips.append("• **Safety**: Ensure your automod settings are tuned for the active user base.")
            
        embed = create_embed(
            "📊 Server Health Hints",
            "\n".join(tips),
            discord.Color.green()
        )
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AI(bot))
