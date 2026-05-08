import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
from utils.checks import is_bot_admin

class Leveling(commands.Cog):
    """Premium Leveling System"""
    
    def __init__(self, bot):
        self.bot = bot
        self._cd = commands.CooldownMapping.from_cooldown(1, 60.0, commands.BucketType.user) # 1 XP per minute

    def get_ratelimit(self, message: discord.Message):
        """Check cooldown"""
        bucket = self._cd.get_bucket(message)
        return bucket.update_rate_limit()

    async def check_level_up(self, user_id, guild_id, current_xp, current_level):
        """Calculate next level"""
        next_level_xp = (current_level + 1) ** 4 # Simple formula: level^4
        
        if current_xp >= next_level_xp:
            return True, current_level + 1
        return False, current_level

    @commands.Cog.listener()
    async def on_message(self, message):
        """Award XP on message"""
        if message.author.bot or not message.guild:
            return
            
        # Ratelimit check
        if self.get_ratelimit(message):
            return

        user_id = message.author.id
        guild_id = message.guild.id
        
        # Get current XP
        data = await self.bot.db.get_xp(user_id, guild_id)
        if data:
            xp, level, _ = data
        else:
            xp, level = 0, 0
            
        # Add random XP (15-25)
        xp_gain = random.randint(15, 25)
        new_xp = xp + xp_gain
        
        # Check Level Up
        leveled_up, new_level = await self.check_level_up(user_id, guild_id, new_xp, level)
        
        # Update DB
        await self.bot.db.update_xp(user_id, guild_id, new_xp, new_level)
        
        if leveled_up:
            # Send Notification
            # Check if there is a specific channel set, otherwise current
            # For now, current channel
            try:
                embed = discord.Embed(
                    title="🎉 Level Up!",
                    description=f"{message.author.mention} has reached **Level {new_level}**!",
                    color=discord.Color.gold()
                )
                await message.channel.send(embed=embed)
                
                # Check for Role Rewards
                reward_role_id = await self.bot.db.get_level_reward(guild_id, new_level)
                if reward_role_id:
                    role = message.guild.get_role(reward_role_id)
                    if role:
                        try:
                            await message.author.add_roles(role)
                            await message.channel.send(f"🏆 You unlocked the **{role.name}** role!")
                        except:
                            pass # Bot missing perms
            except:
                pass # Missing perms to send message

    @app_commands.command(name="rank", description="Check your rank and level")
    async def slash_rank(self, interaction: discord.Interaction, user: discord.Member = None):
        """Check rank"""
        target = user or interaction.user
        
        data = await self.bot.db.get_xp(target.id, interaction.guild.id)
        if not data:
            xp, level = 0, 0
        else:
            xp, level, _ = data
            
        next_xp = (level + 1) ** 4
        
        embed = discord.Embed(
            title=f"📊 Rank for {target.name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="XP", value=f"{xp} / {next_xp}", inline=True)
        
        # Calculate progress bar
        # Simple progress bar
        details = f"Progress to Level {level+1}"
        embed.set_footer(text=details)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard_xp", description="Show XP leaderboard")
    async def slash_leaderboard_xp(self, interaction: discord.Interaction):
        """Show XP leaderboard"""
        top_users = await self.bot.db.get_leaderboard(interaction.guild.id)
        
        if not top_users:
            await interaction.response.send_message("❌ No data found yet!", ephemeral=True)
            return
            
        embed = discord.Embed(title="🏆 Server Levels Leaderboard", color=discord.Color.gold())
        description = ""
        
        for i, (user_id, xp, level) in enumerate(top_users):
            member = interaction.guild.get_member(user_id)
            name = member.name if member else f"User {user_id}"
            description += f"**{i+1}. {name}** - Level {level} ({xp} XP)\n"
            
        embed.description = description
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setxp", description="Admin: Set user XP/Level")
    async def slash_setxp(self, interaction: discord.Interaction, user: discord.Member, level: int):
        """Set user level"""
        # Admin Check
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command is for Admins only.", ephemeral=True)
            return
            
        # Calculate min XP for that level
        xp = level ** 4
        await self.bot.db.update_xp(user.id, interaction.guild.id, xp, level)
        await interaction.response.send_message(f"✅ Set {user.mention} to Level {level} ({xp} XP).")

async def setup(bot):
    await bot.add_cog(Leveling(bot))
