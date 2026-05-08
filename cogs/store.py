import discord
from discord import app_commands
from discord.ext import commands
import datetime
from utils.checks import is_bot_admin

class Store(commands.Cog):
    """Marketplace and Order System"""
    
    def __init__(self, bot):
        self.bot = bot

    # --- Admin Commands ---
    
    @app_commands.command(name="addproduct", description="Add a new product to the store")
    @app_commands.describe(name="Product Name", price="Price (e.g. 15)", description="Product Description")
    async def add_product(self, interaction: discord.Interaction, name: str, price: float, description: str):
        """Add a product"""
        if not await is_bot_admin(self.bot, interaction.user.id):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
            
        success = await self.bot.db.add_product(name, price, description, interaction.user.id)
        if success:
            await interaction.response.send_message(f"✅ Product **{name}** added for ${price}!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Product **{name}** already exists!", ephemeral=True)

    @app_commands.command(name="removeproduct", description="Remove a product from the store")
    async def remove_product(self, interaction: discord.Interaction, name: str):
        """Remove a product"""
        if not await is_bot_admin(self.bot, interaction.user.id):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
            
        await self.bot.db.delete_product(name)
        await interaction.response.send_message(f"✅ Product **{name}** removed.", ephemeral=True)

    @app_commands.command(name="sales", description="View sales statistics")
    async def check_sales(self, interaction: discord.Interaction):
        """Check sales stats"""
        if not await is_bot_admin(self.bot, interaction.user.id):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
            
        # This scans all orders. For high volume, a cache or COUNT query is better.
        # But for this scale, fetching all is fine.
        async with self.bot.db.db.execute('SELECT COUNT(*), SUM(p.price) FROM orders o JOIN products p ON o.product_name = p.name WHERE o.status != "Cancelled"') as cursor:
             data = await cursor.fetchone()
             count = data[0] if data else 0
             revenue = data[1] if data and data[1] else 0.0
             
        await interaction.response.send_message(f"💰 **Total Sales**: {count}\n💵 **Total Revenue**: ${revenue:.2f}", ephemeral=True)

    # --- User Commands ---

    @app_commands.command(name="store", description="View available products")
    async def view_store(self, interaction: discord.Interaction):
        """View the store"""
        products = await self.bot.db.get_all_products()
        
        if not products:
            await interaction.response.send_message("🛒 The store is currently empty.", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="🛒 EXCODE MARKETPLACE",
            description="Browse our premium software and services.",
            color=discord.Color.purple()
        )
        
        for p in products:
            # p = (id, name, price, desc, creator)
            embed.add_field(
                name=f"{p[1]} – ${p[2]}",
                value=p[3] or "No description.",
                inline=False
            )
            
        embed.set_footer(text="Use /buy <product> to purchase.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Purchase a product")
    @app_commands.describe(product="Name of the product")
    async def buy_product(self, interaction: discord.Interaction, product: str):
        """Buy a product"""
        item = await self.bot.db.get_product(product)
        
        if not item:
            await interaction.response.send_message(f"❌ Product **{product}** not found. Check /store.", ephemeral=True)
            return
            
        # Create Order
        order_id = await self.bot.db.create_order(interaction.user.id, product)
        
        embed = discord.Embed(
            title="✅ Order Created",
            description=f"Your order for **{product}** has been placed!\n**Order ID:** `#{order_id}`\n\nPlease wait for a staff member to reach out, or open a ticket with your Order ID.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        
        # Notify Admins (Log Channel)
        log_channel_id = 1461270229714731090 # User's log channel
        log_channel = interaction.guild.get_channel(log_channel_id)
        if log_channel:
             await log_channel.send(f"📦 **New Order!**\nUser: {interaction.user.mention}\nProduct: {product}\nID: #{order_id}")

    @app_commands.command(name="status", description="Check order status")
    async def check_status(self, interaction: discord.Interaction, order_id: int):
        """Check status"""
        order = await self.bot.db.get_order(order_id)
        
        if not order:
            await interaction.response.send_message("❌ Order not found.", ephemeral=True)
            return
            
        # Validate User
        if order[1] != interaction.user.id and not await is_bot_admin(self.bot, interaction.user.id):
             await interaction.response.send_message("❌ You can only view your own orders.", ephemeral=True)
             return
             
        await interaction.response.send_message(f"📦 **Order #{order_id}**\nProduct: {order[2]}\nStatus: **{order[3]}**\nDate: {order[4]}", ephemeral=True)

    @app_commands.command(name="quote", description="Request a quote for custom software")
    async def request_quote(self, interaction: discord.Interaction, details: str):
        """Request a custom quote"""
        # This essentially acts like a ticket but specific to orders
        await interaction.response.send_message("✅ Quote request sent! A developer will DM you or ping you shortly.", ephemeral=True)
        
        log_channel_id = 1461270229714731090
        log_channel = interaction.guild.get_channel(log_channel_id)
        if log_channel:
             await log_channel.send(f"💡 **New Quote Request**\nUser: {interaction.user.mention}\nDetails: {details}")

async def setup(bot):
    await bot.add_cog(Store(bot))
