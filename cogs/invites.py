import discord
from discord import app_commands
from discord.ext import commands
import datetime
from utils.checks import is_bot_admin

class Invites(commands.Cog):
    """Invite Tracking System"""
    
    def __init__(self, bot):
        self.bot = bot
        self.invite_cache = {} # {guild_id: {code: uses}}
    
    async def cog_load(self):
        """Load invites on startup"""
        for guild in self.bot.guilds:
            try:
                self.invite_cache[guild.id] = {}
                invites = await guild.invites()
                for invite in invites:
                    self.invite_cache[guild.id][invite.code] = invite.uses
            except:
                pass
                
    @commands.Cog.listener()
    async def on_ready(self):
        """Reload invites when bot is ready"""
        await self.cog_load()

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        """Update cache when new invite created"""
        if invite.guild.id not in self.invite_cache:
            self.invite_cache[invite.guild.id] = {}
        self.invite_cache[invite.guild.id][invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        """Update cache when invite deleted"""
        if invite.guild.id in self.invite_cache:
            if invite.code in self.invite_cache[invite.guild.id]:
                del self.invite_cache[invite.guild.id][invite.code]

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Track who invited the member"""
        guild = member.guild
        if guild.id not in self.invite_cache:
            return
            
        old_invites = self.invite_cache[guild.id]
        new_invites = {}
        
        try:
            current_invites = await guild.invites()
            inviter = None
            
            for invite in current_invites:
                new_invites[invite.code] = invite.uses
                # Check for usage increment
                if invite.code in old_invites:
                    if invite.uses > old_invites[invite.code]:
                        inviter = invite.inviter
                elif invite.uses > 0:
                    # New invite with uses
                    inviter = invite.inviter
            
            # Update cache
            self.invite_cache[guild.id] = new_invites
            
            # Update Database
            if inviter:
                # Check for self-invite
                if inviter.id == member.id:
                    pass # Don't count self invites
                elif inviter.bot:
                    pass # Don't count bot invites
                else:
                    await self.bot.db.update_invites(inviter.id, guild.id, change_regular=1)
                    
                    # Log it
                    await self.bot.db.log_event(
                        guild.id,
                        'invite_join',
                        f"{member.name} joined via {inviter.name}'s invite",
                        inviter.id
                    )
                    
                    # Optional: Send welcome message specifying inviter?
                    # For now keep it simple database tracking
                    
        except discord.Forbidden:
            pass # Missing permissions

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Check if an invited member left (optional: mark as fake/left)"""
        # Complex logic to track who invited this specific member would require 
        # a separate table 'referrals' (member_id -> inviter_id).
        # For this lightweight version, we stick to count increment.
        pass

    @app_commands.command(name="invites", description="Check invite statistics")
    @app_commands.describe(user="User to check (optional)")
    async def slash_invites(self, interaction: discord.Interaction, user: discord.Member = None):
        """Check invites"""
        # Admin Check
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This server is managed by Admins only.", ephemeral=True)
            return

        target = user or interaction.user
        data = await self.bot.db.get_invites(target.id, interaction.guild.id)
        
        total = data['regular'] + data['bonus'] - data['fake']
        
        embed = discord.Embed(title=f"✉️ Invites for {target.name}", color=discord.Color.blue())
        embed.add_field(name="✅ Regular", value=str(data['regular']), inline=True)
        # embed.add_field(name="❌ Left/Fake", value=str(data['fake']), inline=True)
        # embed.add_field(name="✨ Bonus", value=str(data['bonus']), inline=True)
        embed.add_field(name="🏆 Total", value=f"**{total}**", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Show top inviters")
    async def slash_leaderboard(self, interaction: discord.Interaction):
        """Show invite leaderboard"""
        # Admin Check
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This server is managed by Admins only.", ephemeral=True)
            return

        top_users = await self.bot.db.get_top_inviters(interaction.guild.id)
        
        if not top_users:
            await interaction.response.send_message("❌ No invite data found yet!", ephemeral=True)
            return
            
        embed = discord.Embed(title="🏆 Invite Leaderboard", color=discord.Color.gold())
        description = ""
        
        for i, (user_id, regular, fake, bonus) in enumerate(top_users):
            total = regular + bonus - fake
            member = interaction.guild.get_member(user_id)
            name = member.name if member else f"User {user_id}"
            
            description += f"**{i+1}. {name}**: {total} invites\n"
            
        embed.description = description
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Invites(bot))
