import discord
from discord.ext import commands
from discord import app_commands
from utils.embeds import welcome_embed

class Welcome(commands.Cog):
    """Welcome system for new members"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle new member joins"""
        # Initialize settings manager (if not already done, better to pass user bot)
        # Hack: initializing here if self.settings doesn't exist? 
        # Better: Init in __init__
        if not hasattr(self, 'settings'):
             from utils.settings import SettingsManager
             self.settings = SettingsManager(self.bot)
             
        config = self.bot.config
        db = self.bot.db
        
        # Track user join in database
        await db.track_user_join(member.id, member.guild.id, member.created_at)
        
        # Log the join event
        await db.log_event(
            member.guild.id,
            'member_join',
            f"{member.name} ({member.id}) joined the server. Account created: {member.created_at.strftime('%Y-%m-%d')}",
            member.id
        )
        
        # Send welcome message to welcome channel
        # Use SettingsManager
        welcome_channel_id = await self.settings.get_setting(member.guild.id, 'welcome_channel')
        # Convert to int if string
        if welcome_channel_id:
             try:
                 welcome_channel_id = int(welcome_channel_id)
             except:
                 welcome_channel_id = None

        if welcome_channel_id:
            channel = member.guild.get_channel(welcome_channel_id)
            if channel:
                # Get custom welcome message from config
                welcome_tpl = await self.settings.get_setting(member.guild.id, 'welcome_message')
                
                welcome_msg = welcome_tpl.format(
                    mention=member.mention,
                    name=member.name,
                    server=member.guild.name,
                    count=member.guild.member_count
                )
                
                # Create embed
                embed = welcome_embed(member)
                embed.description = welcome_msg
                
                await channel.send(embed=embed)
        
        # Auto-assign role
        if config.auto_role:
            role = discord.utils.get(member.guild.roles, name=config.auto_role)
            if role:
                try:
                    await member.add_roles(role)
                    print(f"Assigned role '{config.auto_role}' to {member.name}")
                except discord.Forbidden:
                    print(f"Failed to assign role to {member.name}: Missing permissions")
        
        # Send rules DM
        try:
            # Fetch custom DM from settings, fallback to generic default
            rules_message = await self.settings.get_setting(member.guild.id, 'welcome_dm')
            
            if not rules_message:
                # Default generic message if not set
                rules_message = (
                    "👋 Welcome to {server}!\n\n"
                    "To ensure a positive experience for everyone, please adhere to the following community guidelines:\n\n"
                    "1️⃣ Be Respectful\n"
                    "Treat all members with courtesy and respect. Harassment or discrimination of any kind is not tolerated.\n\n"
                    "2️⃣ No Spam or Self-Promotion\n"
                    "Avoid excessive messaging and unauthorized advertising. Share content in the appropriate channels.\n\n"
                    "3️⃣ Professional Language\n"
                    "Keep conversations clean. Toxic behavior, hate speech, and excessive profanity are strictly prohibited.\n\n"
                    "4️⃣ Stay On Topic\n"
                    "Ensure your potential discussions are relevant to the channel's purpose.\n\n"
                    "5️⃣ Follow Discord TOS\n"
                    "Respect Discord's Terms of Service and Community Guidelines.\n\n"
                    "Violations may result in warnings, mutes, or bans depending on severity.\n\n"
                    "Thank you for helping us maintain a great community! 🌟"
                )

            formatted_msg = rules_message.format(
                name=member.name,
                server=member.guild.name,
                mention=member.mention,
                count=member.guild.member_count
            )
            
            dm_embed = discord.Embed(
                title=f"Welcome to {member.guild.name}!",
                description=formatted_msg,
                color=discord.Color.blue()
            )
            
            await member.send(embed=dm_embed)
            print(f"Sent welcome DM to {member.name}")
        except discord.Forbidden:
            print(f"Could not send DM to {member.name} (DMs disabled)")
        except Exception as e:
            print(f"Error sending DM to {member.name}: {e}")

    @app_commands.command(name="test_welcome", description="Debug: Test welcome flow")
    async def slash_test_welcome(self, interaction: discord.Interaction, target: discord.Member):
        """Test welcome message and DM"""
        # Admin Check
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        await interaction.response.defer()
        
        # Manually trigger logic
        # 1. Channel
        config = self.bot.config
        welcome_channel_id = config.get_welcome_channel(target.guild.id)
        
        status = []
        
        if welcome_channel_id:
            channel = target.guild.get_channel(welcome_channel_id)
            if channel:
                try:
                    welcome_msg = config.welcome_message.format(
                        mention=target.mention,
                        name=target.name,
                        server=target.guild.name,
                        count=target.guild.member_count
                    )
                    embed = welcome_embed(target)
                    embed.description = welcome_msg
                    await channel.send(embed=embed)
                    status.append(f"✅ Sent welcome to {channel.mention}")
                except Exception as e:
                    status.append(f"❌ Failed to send to channel: {e}")
            else:
                status.append("❌ Welcome channel not found")
        else:
            status.append("⚠️ No welcome channel set")

        # 2. DM
        try:
            rules_message = config.rules_dm.format(
                name=target.name,
                server=target.guild.name
            )
            dm_embed = discord.Embed(
                title=f"Welcome to {target.guild.name}!",
                description=rules_message,
                color=discord.Color.blue()
            )
            await target.send(embed=dm_embed)
            status.append(f"✅ Sent DM to {target.name}")
        except discord.Forbidden:
            status.append(f"❌ Failed to DM {target.name} (Privacy Settings Closed)")
        except Exception as e:
            status.append(f"❌ Failed to DM: {e}")
            
        await interaction.followup.send("\n".join(status))

async def setup(bot):
    await bot.add_cog(Welcome(bot))
