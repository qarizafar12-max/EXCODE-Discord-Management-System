"""
server_builder.py
─────────────────────────────────────────────────────────────────────────────
Interactive Discord Server Builder powered by Google Gemini AI.

Flow:
  1. Bot joins a guild  →  DMs the owner with a greeting + [Start Setup] button.
  2. Owner clicks Start  →  Bot asks 9 questions (text / button / dropdown).
  3. After all answers   →  Gemini AI generates a FULL server layout in JSON.
  4. Bot parses JSON     →  Creates categories, text channels, voice channels
                            and roles directly on Discord.
─────────────────────────────────────────────────────────────────────────────
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import json
import re

import aiohttp


# ─────────────────────────────────────────────────────────────────────────────
#  SESSION STORE  { guild_id: session_dict }
# ─────────────────────────────────────────────────────────────────────────────
active_sessions: dict[int, dict] = {}

# ─────────────────────────────────────────────────────────────────────────────
#  WIZARD QUESTIONS
# ─────────────────────────────────────────────────────────────────────────────
QUESTIONS = [
    {
        "key": "server_name",
        "prompt": "**What is your server name?**\nType the name you'd like for your community.",
        "type": "text",
    },
    {
        "key": "purpose",
        "prompt": "**What is the main purpose of your server?**",
        "type": "select",
        "options": ["Gaming", "AI / Tech", "Business", "Community", "Study / Education", "Art & Creative", "Other"],
    },
    {
        "key": "topic",
        "prompt": (
            "**What is the main topic or occupation of your community?**\n"
            "_(e.g. Python developers, FPS gamers, crypto traders, anime fans…)_\n"
            "Reply with a short description."
        ),
        "type": "text",
    },
    {
        "key": "ai_channels",
        "prompt": "**Do you want AI / Tech related channels?**",
        "type": "yesno",
    },
    {
        "key": "gaming_channels",
        "prompt": "**Do you want gaming channels?**",
        "type": "yesno",
    },
    {
        "key": "voice_channels",
        "prompt": "**Do you want voice channels?**",
        "type": "yesno",
    },
    {
        "key": "staff_system",
        "prompt": "**Do you want a staff / moderation system?**\n_(private channels hidden from regular members)_",
        "type": "yesno",
    },
    {
        "key": "welcome_system",
        "prompt": "**Do you want a welcome / onboarding system?**\n_(#welcome, #verify, #roles etc.)_",
        "type": "yesno",
    },
    {
        "key": "server_size",
        "prompt": "**How large do you expect your server to grow?**",
        "type": "select",
        "options": ["Small (under 100)", "Medium (100 – 1 000)", "Large (1 000+)"],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
#  GEMINI PROMPT TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────
GEMINI_SYSTEM_PROMPT = """
You are an expert Discord server architect. Your job is to design a beautiful,
organised, and professional Discord server layout based on the details provided.

STRICT RULES:
1. Return ONLY a valid JSON object — no markdown fences, no extra text.
2. Channel names must be lowercase-with-hyphens (e.g. "general-chat").
3. Category names must be UPPERCASE with an emoji prefix (e.g. "💬 COMMUNITY").
4. Every channel name must start with a relevant emoji followed by ・ (e.g. "💬・general-chat").
5. Voice channel names use spaces, no ・ (e.g. "🔊 General Lounge").
6. Roles should be ordered from highest to lowest privilege.
7. Do NOT add bot-managed roles.
8. Make the layout creative, relevant to the server topic, and visually aesthetic.

OUTPUT FORMAT (strict JSON):
{
  "categories": [
    {
      "name": "📌 INFORMATION",
      "staff_only": false,
      "channels": [
        {"name": "📢・announcements", "type": "text", "read_only": true},
        {"name": "📜・rules",         "type": "text", "read_only": true}
      ]
    },
    {
      "name": "🔊 VOICE",
      "staff_only": false,
      "channels": [
        {"name": "🔊 General Lounge", "type": "voice", "read_only": false}
      ]
    }
  ],
  "roles": [
    {"name": "👑 Owner",     "color": "#FFD700", "hoist": true},
    {"name": "🛡️ Moderator", "color": "#5865F2", "hoist": true},
    {"name": "🌟 Member",    "color": "#99AAB5", "hoist": false}
  ]
}
"""


def build_gemini_user_prompt(answers: dict) -> str:
    yn = lambda v: "Yes" if v is True else ("No" if v is False else str(v))
    return f"""
Design a complete Discord server layout for the following server:

• Server Name       : {answers.get('server_name', 'My Server')}
• Main Purpose      : {answers.get('purpose', 'Community')}
• Community Topic   : {answers.get('topic', 'General')}
• AI / Tech Channels: {yn(answers.get('ai_channels'))}
• Gaming Channels   : {yn(answers.get('gaming_channels'))}
• Voice Channels    : {yn(answers.get('voice_channels'))}
• Staff System      : {yn(answers.get('staff_system'))}
• Welcome System    : {yn(answers.get('welcome_system'))}
• Expected Size     : {answers.get('server_size', 'Small')}

Generate a creative, aesthetic, and professional layout tailored to this community.
Include ALL relevant categories, channels, and roles. Remember: return ONLY the JSON.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  UI — YES / NO BUTTONS
# ─────────────────────────────────────────────────────────────────────────────
class YesNoView(discord.ui.View):
    def __init__(self, guild_id: int, cog: "ServerBuilder"):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.cog = cog

    @discord.ui.button(label="✅  Yes", style=discord.ButtonStyle.success)
    async def yes_btn(self, interaction: discord.Interaction, _btn):
        await self._respond(interaction, True)

    @discord.ui.button(label="❌  No", style=discord.ButtonStyle.danger)
    async def no_btn(self, interaction: discord.Interaction, _btn):
        await self._respond(interaction, False)

    async def _respond(self, interaction: discord.Interaction, value: bool):
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        session = active_sessions.get(self.guild_id)
        if session:
            await self.cog.advance_wizard(session, value)


# ─────────────────────────────────────────────────────────────────────────────
#  UI — DROPDOWN SELECT
# ─────────────────────────────────────────────────────────────────────────────
class SelectView(discord.ui.View):
    def __init__(self, guild_id: int, options: list[str], cog: "ServerBuilder"):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.cog = cog
        select = discord.ui.Select(
            placeholder="Choose an option…",
            options=[discord.SelectOption(label=o, value=o) for o in options],
        )
        select.callback = self._callback
        self.add_item(select)

    async def _callback(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        session = active_sessions.get(self.guild_id)
        if session:
            await self.cog.advance_wizard(session, value)


# ─────────────────────────────────────────────────────────────────────────────
#  UI — START / SKIP (sent on guild join)
# ─────────────────────────────────────────────────────────────────────────────
class StartSetupView(discord.ui.View):
    def __init__(self, guild_id: int, cog: "ServerBuilder"):
        super().__init__(timeout=600)
        self.guild_id = guild_id
        self.cog = cog

    @discord.ui.button(label="🚀  Start Setup", style=discord.ButtonStyle.success)
    async def start_btn(self, interaction: discord.Interaction, _btn):
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        dm = interaction.channel  # already in DM
        session = {
            "guild_id": self.guild_id,
            "owner_id": interaction.user.id,
            "dm": dm,
            "q_index": 0,
            "answers": {},
        }
        active_sessions[self.guild_id] = session
        await self.cog._send_question(session)

    @discord.ui.button(label="⏭️  Skip for Now", style=discord.ButtonStyle.secondary)
    async def skip_btn(self, interaction: discord.Interaction, _btn):
        self.stop()
        for child in self.children:
            child.disabled = True
        skip_embed = discord.Embed(
            title="⏭️ Setup Skipped",
            description=(
                "No problem! You can launch the wizard any time inside your server:\n"
                "👉 `/server-builder`"
            ),
            color=0x99AAB5,
        )
        await interaction.response.edit_message(embed=skip_embed, view=self)


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN COG
# ─────────────────────────────────────────────────────────────────────────────
class ServerBuilder(commands.Cog):
    """AI-powered interactive server builder — triggers automatically on guild join."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key: str | None = None

    async def cog_load(self):
        """Safe async init — called automatically when cog loads."""
        self.api_key = getattr(self.bot.config, "openrouter_api_key", None)
        if not self.api_key:
            print("[ServerBuilder] Warning: No OpenRouter API key found.")
        else:
            print("[ServerBuilder] OpenRouter API key loaded.")

    # ── internal helpers ──────────────────────────────────────────────────────

    def _progress_bar(self, index: int) -> str:
        filled = round((index / len(QUESTIONS)) * 10)
        return f"`{'█' * filled}{'░' * (10 - filled)}` {index}/{len(QUESTIONS)}"

    def _question_embed(self, q_index: int) -> discord.Embed:
        q = QUESTIONS[q_index]
        embed = discord.Embed(
            title=f"🏗️ Server Setup Wizard  •  Step {q_index + 1} of {len(QUESTIONS)}",
            description=q["prompt"],
            color=0x5865F2,
        )
        embed.add_field(name="Progress", value=self._progress_bar(q_index), inline=False)
        embed.set_footer(text="EXCODE Server Builder  •  Powered by Gemini AI")
        return embed

    async def _send_question(self, session: dict):
        q = QUESTIONS[session["q_index"]]
        embed = self._question_embed(session["q_index"])
        dm: discord.DMChannel = session["dm"]

        if q["type"] == "yesno":
            await dm.send(embed=embed, view=YesNoView(session["guild_id"], self))
        elif q["type"] == "select":
            await dm.send(embed=embed, view=SelectView(session["guild_id"], q["options"], self))
        else:
            await dm.send(embed=embed)

    async def advance_wizard(self, session: dict, value):
        """Record answer, advance to next question or trigger AI + build."""
        q = QUESTIONS[session["q_index"]]
        session["answers"][q["key"]] = value
        session["q_index"] += 1

        if session["q_index"] < len(QUESTIONS):
            await self._send_question(session)
        else:
            await self._generate_and_build(session)

    # ── Gemini AI generation ──────────────────────────────────────────────────

    # Models tried in order — openrouter/free auto-picks fastest available model
    MODELS = [
        "openrouter/free",                   # fastest: auto-selects best free model
        "nvidia/nemotron-3-nano-30b-a3b:free",  # small/fast fallback
        "nvidia/nemotron-3-super-120b-a12b:free",  # slow but powerful last resort
    ]

    async def _call_gemini(self, answers: dict, status_msg: discord.Message | None = None) -> dict | None:
        """Ask AI to generate the server layout via OpenRouter with auto-retry on 429."""
        if not self.api_key:
            print("[ServerBuilder] OpenRouter API key not initialized.")
            return None

        user_prompt = build_gemini_user_prompt(answers)

        for model in self.MODELS:
            for attempt in range(3):  # up to 3 retries per model
                try:
                    print(f"[ServerBuilder] Trying model: {model} (attempt {attempt + 1})")
                    
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/excode",
                        "X-Title": "Excode Server Builder"
                    }
                    
                    payload = {
                        "model": model,
                        "max_tokens": 2000,
                        "messages": [
                            {"role": "system", "content": GEMINI_SYSTEM_PROMPT},
                            {"role": "user",   "content": user_prompt},
                        ],
                    }
                    
                    timeout = aiohttp.ClientTimeout(total=45, sock_read=40)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload) as response:
                            if response.status == 200:
                                data = await response.json()
                                if "choices" in data and len(data["choices"]) > 0:
                                    raw = data["choices"][0]["message"]["content"].strip()
                                    # Strip markdown fences if added
                                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                                    raw = re.sub(r"\s*```$", "", raw)
                                    return json.loads(raw)
                                else:
                                    raise Exception("No choices in response.")
                            elif response.status == 429:
                                raise Exception("429 Too Many Requests")
                            else:
                                error_text = await response.text()
                                raise Exception(f"HTTP {response.status}: {error_text}")

                except Exception as e:
                    err_str = str(e)
                    print(f"[ServerBuilder] AI error ({model}): {err_str[:120]}")

                    if "429" in err_str or "Too Many Requests" in err_str:
                        wait = 5 * (attempt + 1)  # Progressive backoff: 5s, 10s
                        if attempt < 2:  # still have retries left on this model
                            print(f"[ServerBuilder] Rate limited. Waiting {wait}s before retry…")
                            if status_msg:
                                try:
                                    rate_embed = discord.Embed(
                                        title="⏳ Rate Limited — Retrying…",
                                        description=(
                                            f"AI is busy right now. Retrying in **{wait} seconds** "
                                            f"(attempt {attempt + 2}/3)…"
                                        ),
                                        color=0xFFA500,
                                    )
                                    await status_msg.edit(embed=rate_embed)
                                except Exception:
                                    pass
                            await asyncio.sleep(wait)
                        else:
                            break  # try next model
                    else:
                        # Non-quota error — no point retrying same model
                        break

        print("[ServerBuilder] All models/retries exhausted.")
        return None

    # ── main build flow ───────────────────────────────────────────────────────

    async def _generate_and_build(self, session: dict):
        guild_id = session["guild_id"]
        answers = session["answers"]
        dm: discord.DMChannel = session["dm"]
        guild = self.bot.get_guild(guild_id)

        if not guild:
            await dm.send("❌ Could not find your server. Please run `/server-builder` manually.")
            active_sessions.pop(guild_id, None)
            return

        # ── Step 1: "Generating…" message ──
        gen_embed = discord.Embed(
            title="🤖 Asking AI…",
            description=(
                "I'm sending your answers to **OpenRouter AI** to design the perfect\n"
                "server layout for your community. This takes a few seconds…"
            ),
            color=0xFFA500,
        )
        gen_embed.set_footer(text="EXCODE  •  Powered by OpenRouter AI")
        status_msg = await dm.send(embed=gen_embed)

        layout = await self._call_gemini(answers, status_msg=status_msg)

        if not layout:
            err_embed = discord.Embed(
                title="❌ AI Generation Failed",
                description=(
                    "The AI couldn't produce a layout. Please try again with `/server-builder`.\n"
                    "Make sure the bot has a valid OpenRouter API key in `config.json`."
                ),
                color=0xFF0000,
            )
            await status_msg.edit(embed=err_embed)
            active_sessions.pop(guild_id, None)
            return

        # ── Step 2: "Building…" message ──
        build_embed = discord.Embed(
            title="⚙️ Building Your Server…",
            description=(
                "Gemini has designed your layout!\n"
                "Now creating **categories**, **channels**, and **roles** on your server…"
            ),
            color=0xFFA500,
        )
        await status_msg.edit(embed=build_embed)

        try:
            summary = await self._apply_layout(guild, layout)
        except Exception as e:
            err_embed = discord.Embed(
                title="❌ Build Failed",
                description=(
                    f"Something went wrong while creating channels:\n`{e}`\n\n"
                    "Make sure the bot has **Manage Channels** and **Manage Roles** permissions."
                ),
                color=0xFF0000,
            )
            await status_msg.edit(embed=err_embed)
            active_sessions.pop(guild_id, None)
            return

        # ── Step 3: Success ──
        done_embed = discord.Embed(
            title="✅ Server Setup Complete!",
            description=(
                f"**{guild.name}** now has a beautiful, AI-designed server layout!\n\n"
                "Here's what was created:"
            ),
            color=0x57F287,
        )
        done_embed.add_field(name="📂 Created", value=summary, inline=False)
        done_embed.add_field(
            name="💡 Next Steps",
            value=(
                "• Assign permissions to each role in Server Settings\n"
                "• Configure welcome messages with `/settings`\n"
                "• Use `/setup auto` to link bot channels"
            ),
            inline=False,
        )
        done_embed.set_footer(text="EXCODE  •  Powered by Gemini AI")
        await status_msg.edit(embed=done_embed)

        # Notify in server system channel
        sc = guild.system_channel
        if sc:
            try:
                notif = discord.Embed(
                    title="🎉 Server Layout Created by AI!",
                    description=(
                        "EXCODE has finished building your server structure using **Gemini AI**.\n"
                        "Check your DMs for the full summary!"
                    ),
                    color=0x5865F2,
                )
                await sc.send(
                    content=guild.owner.mention if guild.owner else None,
                    embed=notif,
                )
            except Exception:
                pass

        active_sessions.pop(guild_id, None)

    # ── apply the AI layout to Discord ───────────────────────────────────────

    async def _apply_layout(self, guild: discord.Guild, layout: dict) -> str:
        """Create roles, categories, and channels from the Gemini JSON."""
        created_roles: list[str] = []
        created_categories: list[str] = []
        created_channels: list[str] = []

        # ── 1. Create Roles ──────────────────────────────────────────────────
        staff_role: discord.Role | None = None

        for role_data in reversed(layout.get("roles", [])):  # bottom → top
            rname = role_data.get("name", "Member")
            color_hex = role_data.get("color", "#99AAB5").lstrip("#")
            hoist = role_data.get("hoist", False)

            # Skip if role already exists
            if discord.utils.get(guild.roles, name=rname):
                continue

            try:
                color_int = int(color_hex, 16)
            except ValueError:
                color_int = 0x99AAB5

            role = await guild.create_role(
                name=rname,
                color=discord.Color(color_int),
                hoist=hoist,
                reason="EXCODE AI Server Builder",
            )
            created_roles.append(rname)
            await asyncio.sleep(0.4)

            # Track a "staff / mod" role for permission overrides
            if any(k in rname.lower() for k in ("mod", "staff", "admin", "team")):
                staff_role = role

        # ── 2. Create Categories & Channels ──────────────────────────────────
        for cat_data in layout.get("categories", []):
            cat_name: str = cat_data.get("name", "CATEGORY")
            staff_only: bool = cat_data.get("staff_only", False)

            # Permission overwrites for the category
            overwrites: dict = {
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=False if staff_only else True
                )
            }
            if staff_only and staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True)

            category = await guild.create_category(cat_name, overwrites=overwrites)
            created_categories.append(cat_name)
            await asyncio.sleep(0.4)

            for ch_data in cat_data.get("channels", []):
                ch_name: str = ch_data.get("name", "channel")
                ch_type: str = ch_data.get("type", "text")
                read_only: bool = ch_data.get("read_only", False)

                ch_overwrites = overwrites.copy()
                if read_only and not staff_only:
                    ch_overwrites[guild.default_role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False,
                    )

                if ch_type == "voice":
                    await category.create_voice_channel(ch_name, overwrites=ch_overwrites)
                else:
                    await category.create_text_channel(ch_name, overwrites=ch_overwrites)

                created_channels.append(ch_name)
                await asyncio.sleep(0.3)

        # ── Build summary string ─────────────────────────────────────────────
        parts = []
        if created_roles:
            parts.append(f"🎭 **{len(created_roles)} roles** — {', '.join(created_roles[:5])}{'…' if len(created_roles) > 5 else ''}")
        if created_categories:
            parts.append(f"📂 **{len(created_categories)} categories**")
        if created_channels:
            parts.append(f"💬 **{len(created_channels)} channels**")

        return "\n".join(parts) if parts else "Layout applied."

    # ── on_guild_join: greet owner ────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        owner = guild.owner
        if not owner:
            return

        embed = discord.Embed(
            title="👋 Thanks for adding EXCODE to your server!",
            description=(
                f"Hey **{owner.display_name}**! I'm **EXCODE** — your professional server management bot.\n\n"
                "I can build a **fully organised, AI-designed server layout** for you in 2 minutes.\n"
                "Just answer 9 quick questions and **Gemini AI** will design:\n\n"
                "• 📂 Categories & text channels\n"
                "• 🔊 Voice channels\n"
                "• 🎭 Roles with colours\n"
                "• 🛠️ Staff / Moderation spaces\n"
                "• 👋 Welcome & onboarding channels\n\n"
                "Ready to build your dream server?"
            ),
            color=0x5865F2,
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="EXCODE  •  Powered by Gemini AI")

        view = StartSetupView(guild.id, self)
        try:
            dm = await owner.create_dm()
            await dm.send(embed=embed, view=view)
        except discord.Forbidden:
            sc = guild.system_channel
            if sc:
                try:
                    await sc.send(content=owner.mention, embed=embed, view=view)
                except Exception:
                    pass

    # ── on_message: accept free-text answers in DM ───────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.DMChannel):
            return

        for guild_id, session in list(active_sessions.items()):
            if session.get("owner_id") == message.author.id:
                q = QUESTIONS[session["q_index"]]
                if q["type"] == "text":
                    await self.advance_wizard(session, message.content.strip())
                break

    # ── slash command: manual trigger ────────────────────────────────────────

    @app_commands.command(
        name="server-builder",
        description="🏗️ Launch the AI-powered server builder wizard",
    )
    async def server_builder_slash(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need **Administrator** permission to use this command.",
                ephemeral=True,
            )
            return

        guild = interaction.guild

        embed = discord.Embed(
            title="🏗️ AI Server Builder",
            description=(
                "I'll walk you through 9 quick questions, then **Gemini AI** will design\n"
                "a beautiful, unique server layout just for you.\n\n"
                "**Check your DMs** — the wizard starts there!"
            ),
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        try:
            dm = await interaction.user.create_dm()
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I couldn't DM you. Please enable DMs from server members.",
                ephemeral=True,
            )
            return

        session = {
            "guild_id": guild.id,
            "owner_id": interaction.user.id,
            "dm": dm,
            "q_index": 0,
            "answers": {},
        }
        active_sessions[guild.id] = session
        await self._send_question(session)


# ─────────────────────────────────────────────────────────────────────────────
#  COG LOADER
# ─────────────────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(ServerBuilder(bot))
