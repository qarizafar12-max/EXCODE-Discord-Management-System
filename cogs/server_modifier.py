"""
server_modifier.py
──────────────────────────────────────────────────────────────────────────────
/modify-server  —  Natural language server channel/category modification.

Usage:
  /modify-server request:"add a reports channel and remove general-chat"

Flow:
  1. Admin types a plain-English request.
  2. Bot sends it to OpenRouter AI.
  3. AI returns a JSON list of actions (create / delete channel / category).
  4. Bot executes each action with bold Unicode channel names like:
       ⚠┃𝗥𝗘𝗣𝗢𝗥𝗧𝗦
──────────────────────────────────────────────────────────────────────────────
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import aiohttp
import json
import re

# ─────────────────────────────────────────────────────────────────────────────
#  BOLD UNICODE CONVERTER
#  Converts plain ASCII text → 𝗕𝗼𝗹𝗱 𝗨𝗻𝗶𝗰𝗼𝗱𝗲 (Mathematical Bold)
# ─────────────────────────────────────────────────────────────────────────────
_BOLD_UPPER = 0x1D400  # A
_BOLD_LOWER = 0x1D41A  # a
_BOLD_DIGIT = 0x1D7CE  # 0


def to_bold(text: str) -> str:
    """Convert ASCII letters/digits to Mathematical Bold Unicode."""
    result = []
    for ch in text:
        if "A" <= ch <= "Z":
            result.append(chr(_BOLD_UPPER + ord(ch) - ord("A")))
        elif "a" <= ch <= "z":
            result.append(chr(_BOLD_LOWER + ord(ch) - ord("a")))
        elif "0" <= ch <= "9":
            result.append(chr(_BOLD_DIGIT + ord(ch) - ord("0")))
        else:
            result.append(ch)
    return "".join(result)


def format_channel(emoji: str, name: str) -> str:
    """Format a channel name:  ⚠┃𝗥𝗘𝗣𝗢𝗥𝗧𝗦"""
    bold_name = to_bold(name.upper().replace("-", " ").replace("_", " "))
    return f"{emoji}┃{bold_name}"


def format_category(emoji: str, name: str) -> str:
    """Format a category name:  ⚙ 𝗦𝗧𝗔𝗙𝗙"""
    bold_name = to_bold(name.upper().replace("-", " ").replace("_", " "))
    return f"{emoji} {bold_name}"


# ─────────────────────────────────────────────────────────────────────────────
#  AI SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a Discord server modification assistant.
Given a plain-English request, return a JSON array of actions to perform on the server.

STRICT RULES:
1. Return ONLY a valid JSON array — no markdown, no explanation.
2. Each action must have:
   - "action"   : "create_channel" | "delete_channel" | "create_category" | "delete_category"
   - "name"     : short lowercase-with-hyphens name (e.g. "reports", "staff-chat")
   - "emoji"    : ONE relevant emoji for the channel/category
   - "type"     : "text" | "voice"  (only for create_channel, omit for categories)
   - "category" : (optional) name of the parent category for create_channel
   - "read_only": true | false  (optional, for text channels that should be read-only)
3. For delete actions, only include "action" and "name" (the current Discord name to match, no emoji).
4. Keep names short (1-3 words max).
5. Choose emojis that match the channel purpose.

EXAMPLE OUTPUT:
[
  {"action": "create_category", "name": "reports", "emoji": "⚠️"},
  {"action": "create_channel",  "name": "reports", "emoji": "⚠️", "type": "text", "category": "reports", "read_only": false},
  {"action": "delete_channel",  "name": "general-chat"}
]
"""


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN COG
# ─────────────────────────────────────────────────────────────────────────────
class ServerModifier(commands.Cog):
    """Natural-language server channel/category modifier."""

    MODELS = [
        "openrouter/free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
    ]

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key: str | None = None

    async def cog_load(self):
        self.api_key = getattr(self.bot.config, "openrouter_api_key", None)
        if self.api_key:
            print("[ServerModifier] OpenRouter API key loaded OK.")
        else:
            print("[ServerModifier] Warning: No OpenRouter API key found!")

    # ── AI call ───────────────────────────────────────────────────────────────

    async def _ask_ai(self, request: str) -> list | None:
        """Send the user's request to OpenRouter and return parsed JSON actions."""
        if not self.api_key:
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/excode-bot",
            "X-Title": "EXCODE Server Modifier",
        }

        for model in self.MODELS:
            payload = {
                "model": model,
                "max_tokens": 1000,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": request},
                ],
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
                            raw = data["choices"][0]["message"]["content"].strip()
                            # Strip markdown fences
                            raw = re.sub(r"^```(?:json)?\s*", "", raw)
                            raw = re.sub(r"\s*```$", "", raw)
                            return json.loads(raw)
                        else:
                            text = await resp.text()
                            print(f"[ServerModifier] {model} HTTP {resp.status}: {text[:100]}")
            except Exception as e:
                print(f"[ServerModifier] Error ({model}): {str(e)[:100]}")

        return None

    # ── Execute actions ───────────────────────────────────────────────────────

    async def _execute_actions(
        self, guild: discord.Guild, actions: list
    ) -> tuple[list[str], list[str]]:
        """Execute the AI-returned actions. Returns (successes, failures)."""
        successes: list[str] = []
        failures:  list[str] = []

        for action in actions:
            act  = action.get("action", "")
            name = action.get("name", "").lower().strip()
            emoji = action.get("emoji", "📁")
            ch_type = action.get("type", "text")
            cat_name = action.get("category", "")
            read_only = action.get("read_only", False)

            try:
                # ── CREATE CATEGORY ────────────────────────────────────────
                if act == "create_category":
                    display = format_category(emoji, name)
                    existing = discord.utils.find(
                        lambda c: name in c.name.lower(),
                        guild.categories,
                    )
                    if existing:
                        failures.append(f"Category **{display}** already exists")
                        continue
                    await guild.create_category(display)
                    successes.append(f"📂 Created category **{display}**")
                    await asyncio.sleep(0.5)

                # ── DELETE CATEGORY ────────────────────────────────────────
                elif act == "delete_category":
                    target = discord.utils.find(
                        lambda c: name in c.name.lower(),
                        guild.categories,
                    )
                    if not target:
                        failures.append(f"Category matching `{name}` not found")
                        continue
                    deleted_name = target.name
                    await target.delete()
                    successes.append(f"🗑️ Deleted category **{deleted_name}**")
                    await asyncio.sleep(0.5)

                # ── CREATE CHANNEL ─────────────────────────────────────────
                elif act == "create_channel":
                    display = format_channel(emoji, name)

                    # Find parent category
                    category_obj: discord.CategoryChannel | None = None
                    if cat_name:
                        category_obj = discord.utils.find(
                            lambda c: cat_name.lower() in c.name.lower(),
                            guild.categories,
                        )

                    # Build permission overwrites (read-only channels)
                    overwrites = {}
                    if read_only:
                        overwrites[guild.default_role] = discord.PermissionOverwrite(
                            read_messages=True, send_messages=False
                        )

                    if ch_type == "voice":
                        await guild.create_voice_channel(
                            display, category=category_obj, overwrites=overwrites
                        )
                    else:
                        await guild.create_text_channel(
                            display, category=category_obj, overwrites=overwrites
                        )
                    successes.append(f"{'🔊' if ch_type == 'voice' else '💬'} Created channel **{display}**")
                    await asyncio.sleep(0.4)

                # ── DELETE CHANNEL ─────────────────────────────────────────
                elif act == "delete_channel":
                    target = discord.utils.find(
                        lambda c: name in c.name.lower(),
                        guild.channels,
                    )
                    if not target:
                        failures.append(f"Channel matching `{name}` not found")
                        continue
                    deleted_name = target.name
                    await target.delete()
                    successes.append(f"🗑️ Deleted channel **{deleted_name}**")
                    await asyncio.sleep(0.4)

                else:
                    failures.append(f"Unknown action: `{act}`")

            except discord.Forbidden:
                failures.append(f"❌ No permission to `{act}` `{name}`")
            except Exception as e:
                failures.append(f"❌ Error on `{act}` `{name}`: {str(e)[:60]}")

        return successes, failures

    # ── Slash command ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="modify-server",
        description="✏️ Modify channels & categories using plain English — powered by AI",
    )
    @app_commands.describe(
        request="Describe what you want to add or remove (e.g. 'add a reports channel, remove gaming')"
    )
    async def modify_server(self, interaction: discord.Interaction, request: str):
        # Permission check
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need **Administrator** permission to use this command.",
                ephemeral=True,
            )
            return

        guild = interaction.guild

        # Acknowledge immediately — AI call can take a few seconds
        await interaction.response.defer(ephemeral=False)

        thinking_embed = discord.Embed(
            title="🤖 Analysing your request…",
            description=f"**Request:** {request}\n\nAsking AI to plan the changes…",
            color=0x5865F2,
        )
        thinking_embed.set_footer(text="EXCODE Server Modifier  •  Powered by OpenRouter AI")
        msg = await interaction.followup.send(embed=thinking_embed)

        # ── Ask AI ──
        actions = await self._ask_ai(request)

        if not actions:
            err_embed = discord.Embed(
                title="❌ AI Failed to Respond",
                description=(
                    "The AI couldn't parse your request. Try rephrasing it.\n"
                    "**Example:** `add a reports channel in a new alerts category`"
                ),
                color=0xFF0000,
            )
            await msg.edit(embed=err_embed)
            return

        # Show plan before executing
        plan_lines = []
        for a in actions:
            act  = a.get("action", "?")
            name = a.get("name", "?")
            emoji = a.get("emoji", "")
            if "create" in act:
                plan_lines.append(f"✅ **Create** {emoji} `{name}`")
            else:
                plan_lines.append(f"🗑️ **Delete** `{name}`")

        plan_embed = discord.Embed(
            title="⚙️ Executing Changes…",
            description="\n".join(plan_lines) if plan_lines else "No actions planned.",
            color=0xFFA500,
        )
        plan_embed.set_footer(text="EXCODE Server Modifier  •  Powered by OpenRouter AI")
        await msg.edit(embed=plan_embed)

        # ── Execute ──
        successes, failures = await self._execute_actions(guild, actions)

        # ── Result embed ──
        result_embed = discord.Embed(
            title="✅ Server Modifications Complete!",
            color=0x57F287 if not failures else (0xFFA500 if successes else 0xFF0000),
        )

        if successes:
            result_embed.add_field(
                name=f"✅ Done ({len(successes)})",
                value="\n".join(successes[:10]),
                inline=False,
            )
        if failures:
            result_embed.add_field(
                name=f"⚠️ Issues ({len(failures)})",
                value="\n".join(failures[:5]),
                inline=False,
            )

        result_embed.set_footer(
            text=f"Requested by {interaction.user.display_name}  •  EXCODE Server Modifier"
        )
        await msg.edit(embed=result_embed)


# ─────────────────────────────────────────────────────────────────────────────
#  COG LOADER
# ─────────────────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(ServerModifier(bot))
