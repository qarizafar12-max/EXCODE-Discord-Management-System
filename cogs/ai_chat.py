"""
ai_chat.py
──────────────────────────────────────────────────────────────────────────────
AI Chat — responds to EVERY message in any server channel + DMs.
Uses OpenRouter API (no quota limits like Gemini free tier).

Features:
  • Replies to all non-bot messages automatically
  • Maintains per-user conversation history (last 20 messages)
  • Typing indicator while generating
  • /chat_reset to wipe your history
  • /ai_toggle to enable/disable in a specific channel
──────────────────────────────────────────────────────────────────────────────
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import re

# ─────────────────────────────────────────────────────────────────────────────
#  SYSTEM PROMPT — Bot persona
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are EXCODE AI, an advanced and friendly Discord bot assistant. "
    "You answer ANY question a user asks — coding, math, general knowledge, "
    "advice, creative writing, or just casual chat. "
    "Keep responses concise and well-formatted for Discord "
    "(use markdown code blocks for code, keep replies under 1800 characters). "
    "Be friendly, helpful, and natural in conversation."
)

# OpenRouter models to try in order
MODELS = [
    "openrouter/free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]


class AIChat(commands.Cog):
    """AI Chat — responds to every message using OpenRouter API."""

    def __init__(self, bot):
        self.bot = bot
        self.api_key: str | None = None
        # { user_id: [ {"role": "user"|"assistant", "content": "..."}, ... ] }
        self.chat_histories: dict[int, list[dict]] = {}
        # Channels where AI is disabled (admins can toggle)
        self.disabled_channels: set[int] = set()

    async def cog_load(self):
        """Safe async init."""
        self.api_key = getattr(self.bot.config, "openrouter_api_key", None)
        if self.api_key:
            print("[AIChat] OpenRouter client ready — replying to all messages.")
        else:
            print("[AIChat] WARNING: No OpenRouter API key found! AI chat disabled.")

    # ── OpenRouter call ───────────────────────────────────────────────────────

    async def _call_openrouter(self, messages: list[dict]) -> str | None:
        """Call OpenRouter and return the assistant reply text."""
        if not self.api_key:
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/excode-bot",
            "X-Title": "EXCODE AI Chat",
        }

        for model in MODELS:
            payload = {
                "model": model,
                "max_tokens": 800,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            }
            try:
                timeout = aiohttp.ClientTimeout(total=40, sock_read=35)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            text = data["choices"][0]["message"]["content"].strip()
                            return text
                        else:
                            body = await resp.text()
                            print(f"[AIChat] {model} → HTTP {resp.status}: {body[:80]}")
            except Exception as e:
                print(f"[AIChat] {model} → {str(e)[:80]}")

        return None

    # ── on_message — respond to everything ────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots
        if message.author.bot:
            return

        # Ignore empty / very short messages
        content = message.content.strip()
        if len(content) < 2:
            return

        # Ignore disabled channels
        if message.channel.id in self.disabled_channels:
            return

        # Remove bot @mention from content if present
        if self.bot.user:
            content = content.replace(f"<@{self.bot.user.id}>", "").strip()

        if not content:
            content = "Hello!"

        # Build / update conversation history for this user
        uid = message.author.id
        if uid not in self.chat_histories:
            self.chat_histories[uid] = []

        history = self.chat_histories[uid]
        history.append({"role": "user", "content": content})

        # Keep history at max 20 turns (10 exchanges)
        if len(history) > 20:
            history = history[-20:]
            self.chat_histories[uid] = history

        # Show typing indicator while generating
        async with message.channel.typing():
            reply = await self._call_openrouter(history)

        if not reply:
            reply = "⚠️ I'm having trouble thinking right now. Try again in a moment!"

        # Truncate to Discord's 2000 char limit
        if len(reply) > 1990:
            reply = reply[:1987] + "…"

        # Save assistant reply to history
        history.append({"role": "assistant", "content": reply})

        await message.reply(reply, mention_author=False)

    # ── /chat_reset ───────────────────────────────────────────────────────────

    @app_commands.command(
        name="chat_reset",
        description="🧠 Reset your personal AI conversation history",
    )
    async def chat_reset(self, interaction: discord.Interaction):
        self.chat_histories.pop(interaction.user.id, None)
        await interaction.response.send_message(
            "🧠 Memory wiped! Starting fresh — what's on your mind?",
            ephemeral=True,
        )

    # ── /ai_toggle ────────────────────────────────────────────────────────────

    @app_commands.command(
        name="ai_toggle",
        description="🔇 Enable or disable AI chat replies in a specific channel",
    )
    @app_commands.describe(channel="The channel to toggle AI in (defaults to current)")
    async def ai_toggle(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "❌ You need **Manage Channels** permission.", ephemeral=True
            )
            return

        target = channel or interaction.channel
        if target.id in self.disabled_channels:
            self.disabled_channels.discard(target.id)
            status = "✅ **Enabled**"
        else:
            self.disabled_channels.add(target.id)
            status = "🔇 **Disabled**"

        await interaction.response.send_message(
            f"AI chat is now {status} in {target.mention}.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(AIChat(bot))
