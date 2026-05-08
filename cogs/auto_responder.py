import discord
from discord.ext import commands
from discord import app_commands
from utils.checks import is_bot_admin
from thefuzz import fuzz
from thefuzz import process

class AutoResponder(commands.Cog):
    """Auto Responder System"""

    def __init__(self, bot):
        self.bot = bot
        self.triggers = {}
        
        # Hardcoded built-in conversational NLP intents
        self.conversational_intents = {
            "hello": "Hello there! I'm the Excode AI Supervisor. How can I assist you today?",
            "hi": "Hi! How's it going?",
            "hey": "Hey! Need any help?",
            "how are you": "I'm just a bot, but I'm doing great! Monitoring the server and keeping things safe.",
            "what can you do": "I'm an AI Supervisor. I can answer FAQs, monitor chat sentiment, automatically cool down arguments with slowmode, and manage user trust scores!",
            "who are you": "I am the Excode Bot, currently acting as your local AI Supervisor.",
            "good morning": "Good morning! Hope you have a productive day.",
            "good night": "Good night! I'll be here watching the server while you sleep."
        }
        
    async def cog_load(self):
        # Load triggers into memory
        rows = await self.bot.db.get_auto_responses()
        self.triggers = {row[0].lower(): row[1] for row in rows}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
            
        # Ignore messages that mention the bot, let ai_chat handle them
        if self.bot.user in message.mentions:
            return
            
        content_lower = message.content.lower()
        
        # Exact match preferred
        if content_lower in self.triggers:
            response = self.triggers[content_lower]
            await message.channel.send(response)
            return

        # Check for conversational chit-chat first
        best_intent, intent_score = process.extractOne(content_lower, list(self.conversational_intents.keys()), scorer=fuzz.token_set_ratio)
        if intent_score > 85:
            await message.channel.send(self.conversational_intents[best_intent])
            return

        # Smart FAQ / Fuzzy Matching (AI Feature)
        if len(content_lower) > 5 and len(self.triggers) > 0:
            # We only fuzzy match if message is long enough to have meaning
            # Check all triggers for a fuzzy match
            best_match, score = process.extractOne(content_lower, list(self.triggers.keys()), scorer=fuzz.token_set_ratio)
            
            # If the score is high enough (e.g. > 85%), we consider it a match
            if score > 85:
                response = self.triggers[best_match]
                # We can optionally add a small prefix so users know it's a "smart" reply
                await message.channel.send(f"*(Smart FAQ Match)*: {response}")

    @app_commands.command(name="addtrigger", description="Add an auto-response trigger")
    async def add_trigger(self, interaction: discord.Interaction, trigger: str, response: str):
        """Add a trigger"""
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Missing permissions.", ephemeral=True)
            return
            
        success = await self.bot.db.add_auto_response(trigger, response)
        if success:
            self.triggers[trigger.lower()] = response
            await interaction.response.send_message(f"✅ Added trigger `{trigger}` -> `{response}`")
        else:
            await interaction.response.send_message("❌ Trigger already exists or error occurred.", ephemeral=True)

    @app_commands.command(name="deltrigger", description="Delete an auto-response trigger")
    async def del_trigger(self, interaction: discord.Interaction, trigger: str):
        """Delete a trigger"""
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Missing permissions.", ephemeral=True)
            return
            
        if trigger.lower() in self.triggers:
            await self.bot.db.remove_auto_response(trigger)
            del self.triggers[trigger.lower()]
            await interaction.response.send_message(f"✅ Removed trigger `{trigger}`")
        else:
            await interaction.response.send_message("❌ Trigger not found.", ephemeral=True)

    @app_commands.command(name="triggers", description="List all triggers")
    async def list_triggers(self, interaction: discord.Interaction):
        """List triggers"""
        if not self.triggers:
            await interaction.response.send_message("No triggers set.", ephemeral=True)
            return
            
        desc = "\n".join([f"• `{k}` -> `{v}`" for k, v in self.triggers.items()])
        embed = discord.Embed(title="📝 Auto Responses", description=desc, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AutoResponder(bot))
