import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
from utils.checks import is_bot_admin

class Economy(commands.Cog):
    """Premium Economy System"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="balance", description="Check your wallet and bank balance")
    async def slash_balance(self, interaction: discord.Interaction, user: discord.Member = None):
        """Check balance"""
        target = user or interaction.user
        
        data = await self.bot.db.get_balance(target.id, interaction.guild.id)
        
        embed = discord.Embed(
            title=f"💰 Balance for {target.name}",
            color=discord.Color.green()
        )
        embed.add_field(name="💳 Wallet", value=f"${data['balance']}", inline=True)
        embed.add_field(name="🏦 Bank", value=f"${data['bank']}", inline=True)
        embed.add_field(name="💎 Total", value=f"${data['balance'] + data['bank']}", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="work", description="Work to earn money")
    async def slash_work(self, interaction: discord.Interaction):
        """Work command"""
        # Check cooldown (naive implementation using DB timestamp)
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        data = await self.bot.db.get_balance(user_id, guild_id)
        last_work = data['last_work']
        
        now = datetime.datetime.utcnow()
        if last_work:
            last_date = datetime.datetime.fromisoformat(last_work)
            diff = now - last_date
            if diff.total_seconds() < 3600: # 1 hour cooldown
                minutes = int((3600 - diff.total_seconds()) / 60)
                await interaction.response.send_message(f"⏳ You can work again in {minutes} minutes.", ephemeral=True)
                return

        # Earnings
        earnings = random.randint(50, 200)
        new_balance = data['balance'] + earnings
        
        await self.bot.db.update_balance(user_id, guild_id, balance=new_balance, last_work=now.isoformat())
        
        await interaction.response.send_message(f"💼 You worked hard and earned **${earnings}**!")

    @app_commands.command(name="daily", description="Claim daily reward")
    async def slash_daily(self, interaction: discord.Interaction):
        """Daily reward"""
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        data = await self.bot.db.get_balance(user_id, guild_id)
        last_daily = data['last_daily']
        
        now = datetime.datetime.utcnow()
        if last_daily:
            last_date = datetime.datetime.fromisoformat(last_daily)
            diff = now - last_date
            if diff.total_seconds() < 86400: # 24 hours
                hours = int((86400 - diff.total_seconds()) / 3600)
                await interaction.response.send_message(f"⏳ You can claim your daily in {hours} hours.", ephemeral=True)
                return

        reward = 500
        new_balance = data['balance'] + reward
        
        await self.bot.db.update_balance(user_id, guild_id, balance=new_balance, last_daily=now.isoformat())
        
        await interaction.response.send_message(f"🌞 You claimed your daily reward of **${reward}**!")

    @app_commands.command(name="pay", description="Pay another user")
    async def slash_pay(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        """Transfer money"""
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
            return
            
        if user.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't pay yourself.", ephemeral=True)
            return

        sender_data = await self.bot.db.get_balance(interaction.user.id, interaction.guild.id)
        if sender_data['balance'] < amount:
            await interaction.response.send_message("❌ Insufficient funds in wallet.", ephemeral=True)
            return
            
        # Receiver
        receiver_data = await self.bot.db.get_balance(user.id, interaction.guild.id)
        
        # Transfer
        new_sender_bal = sender_data['balance'] - amount
        new_receiver_bal = receiver_data['balance'] + amount
        
        await self.bot.db.update_balance(interaction.user.id, interaction.guild.id, balance=new_sender_bal)
        await self.bot.db.update_balance(user.id, interaction.guild.id, balance=new_receiver_bal)
        
        await interaction.response.send_message(f"💸 {interaction.user.mention} paid **${amount}** to {user.mention}!")

    @app_commands.command(name="add_money", description="Admin: Add money to user")
    async def slash_add_money(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        """Give money"""
        # Admin Check
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command is for Admins only.", ephemeral=True)
            return
            
        data = await self.bot.db.get_balance(user.id, interaction.guild.id)
        new_balance = data['balance'] + amount
        
        await self.bot.db.update_balance(user.id, interaction.guild.id, balance=new_balance)
        await interaction.response.send_message(f"✅ Added **${amount}** to {user.mention}'s wallet.")

async def setup(bot):
    await bot.add_cog(Economy(bot))
