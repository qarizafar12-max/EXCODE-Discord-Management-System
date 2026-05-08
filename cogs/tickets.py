import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Button, View
from utils.checks import is_bot_admin

class TicketView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
    
    @discord.ui.select(
        placeholder="Select Ticket Category...",
        custom_id="ticket_category_select",
        options=[
            discord.SelectOption(label="Help", emoji="❓", description="General help and questions"),
            discord.SelectOption(label="Buy", emoji="🛒", description="Purchase products or services"),
            discord.SelectOption(label="Support", emoji="🔧", description="Technical support"),
            discord.SelectOption(label="Other", emoji="📝", description="Other inquiries")
        ]
    )
    async def create_ticket(self, interaction: discord.Interaction, select: discord.ui.Select):
        category_name = select.values[0]
        category_slug = category_name.lower()
        
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Tickets")
        
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            category = await guild.create_category("Tickets", overwrites=overwrites)
            
        # Permission Overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Channel Name with Category
        channel_name = f"{category_slug}-{interaction.user.name.lower()}"[:100]
        
        # Check if channel exists (rudimentary check)
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
             await interaction.response.send_message(f"❌ You already have a ticket: {existing.mention}", ephemeral=True)
             return

        channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
        
        # Save to DB - We could extend DB to save category, but mostly for tracking
        await self.bot.db.create_ticket(channel.id, guild.id, interaction.user.id, str(interaction.user.display_name))
        
        await interaction.response.send_message(f"✅ {category_name} Ticket created: {channel.mention}", ephemeral=True)
        
        # Send welcome message
        embed = discord.Embed(
            title=f"{category_name} Ticket",
            description=f"Hello {interaction.user.mention}!\n\nYou opened a **{category_name}** ticket.\nSupport will be with you shortly.\n\nClick the button below to close this ticket.",
            color=discord.Color.green()
        )
        
        # Close button
        close_view = View(timeout=None)
        close_btn = Button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒")
        
        async def close_callback(inter: discord.Interaction):
            # Check permissions
            if inter.user.id != interaction.user.id and not inter.user.guild_permissions.administrator:
                await inter.response.send_message("❌ Only the ticket owner or admins can close this ticket.", ephemeral=True)
                return
            
            await inter.response.send_message("🔒 Closing ticket in 5 seconds...")
            await self.bot.db.close_ticket(channel.id)
            import asyncio
            await asyncio.sleep(5)
            try:
                await channel.delete()
            except:
                pass
        
        close_btn.callback = close_callback
        close_view.add_item(close_btn)
        
        welcome_msg = await channel.send(f"{interaction.user.mention} Welcome!", embed=embed, view=close_view)
        
        # Log the welcome message
        await self.bot.db.log_ticket_message(
            ticket_id=channel.id,
            author_id=self.bot.user.id,
            author_name=self.bot.user.name,
            content=f"Ticket opened: {category_name}",
            is_bot=1
        )

class PriorityView(discord.ui.View):
    def __init__(self, bot, channel_id):
        super().__init__(timeout=60)
        self.bot = bot
        self.channel_id = channel_id

    @discord.ui.button(label="Low", style=discord.ButtonStyle.secondary)
    async def low_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.bot.db.update_ticket_priority(self.channel_id, "Low")
        await interaction.response.send_message("✅ Priority set to **Low**", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Normal", style=discord.ButtonStyle.success)
    async def normal_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.bot.db.update_ticket_priority(self.channel_id, "Normal")
        await interaction.response.send_message("✅ Priority set to **Normal**", ephemeral=True)
        self.stop()

    @discord.ui.button(label="High", style=discord.ButtonStyle.primary)
    async def high_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.bot.db.update_ticket_priority(self.channel_id, "High")
        await interaction.response.send_message("✅ Priority set to **High**", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Urgent", style=discord.ButtonStyle.danger)
    async def urgent_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.bot.db.update_ticket_priority(self.channel_id, "Urgent")
        await interaction.response.send_message("✅ Priority set to **Urgent** 🚨", ephemeral=True)
        self.stop()

class TransferView(discord.ui.View):
    def __init__(self, bot, channel_id, guild):
        super().__init__(timeout=60)
        self.bot = bot
        self.channel_id = channel_id
        self.guild = guild

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Select Admin to Transfer to...")
    async def transfer_select(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        target_user = select.values[0]
        
        # Admin check for target user
        if not target_user.guild_permissions.administrator and not await is_bot_admin(self.bot, target_user.id):
             await interaction.response.send_message("❌ You can only transfer tickets to Administrators or Bot Admins.", ephemeral=True)
             return

        await self.bot.db.transfer_ticket(self.channel_id, target_user.id, str(target_user.display_name))
        
        # Update channel permissions
        channel = self.guild.get_channel(self.channel_id)
        if channel:
            await channel.set_permissions(target_user, read_messages=True, send_messages=True, attach_files=True)
            await channel.send(f"👤 **Ticket Transferred!** New assigned admin: {target_user.mention}")
            
        await interaction.response.send_message(f"✅ Ticket transferred to {target_user.name}", ephemeral=True)
        self.stop()

class TicketOptionsView(View):
    def __init__(self, bot, channel_id, guild):
        super().__init__(timeout=60)
        self.bot = bot
        self.channel_id = channel_id
        self.guild = guild

    @discord.ui.button(label="Set Priority", style=discord.ButtonStyle.secondary, emoji="⚡")
    async def set_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PriorityView(self.bot, self.channel_id)
        await interaction.response.send_message("Select the new priority level:", view=view, ephemeral=True)

    @discord.ui.button(label="Transfer", style=discord.ButtonStyle.secondary, emoji="👥")
    async def transfer(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TransferView(self.bot, self.channel_id, self.guild)
        await interaction.response.send_message("Select an admin to transfer this ticket to:", view=view, ephemeral=True)

    @discord.ui.button(label="Ticket Info", style=discord.ButtonStyle.secondary, emoji="ℹ️")
    async def ticket_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = await self.bot.db.get_ticket(self.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ Ticket info not found.", ephemeral=True)
            return
            
        priority = ticket[4] if len(ticket) > 4 else "Normal"
        assigned_id = ticket[5] if len(ticket) > 5 else None
        assigned_name = "None"
        if assigned_id:
            assigned_user = self.guild.get_member(assigned_id) or await self.bot.fetch_user(assigned_id)
            assigned_name = assigned_user.mention if assigned_user else str(assigned_id)

        embed = discord.Embed(title="Ticket Information", color=discord.Color.blue())
        embed.add_field(name="Owner", value=f"<@{ticket[2]}>", inline=True)
        embed.add_field(name="Status", value=ticket[3], inline=True)
        embed.add_field(name="Priority", value=priority, inline=True)
        embed.add_field(name="Assigned To", value=assigned_name, inline=True)
        embed.add_field(name="Created At", value=ticket[6] if len(ticket) > 6 else "Unknown", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Tickets(commands.Cog):
    """Premium Ticket System"""
    
    def __init__(self, bot):
        self.bot = bot
        # Context Menu
        self.ctx_menu = app_commands.ContextMenu(
            name='Ticket Options',
            callback=self.ticket_options_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)
        self.sync_names.start()
        
    async def cog_load(self):
        """Register persistent view"""
        self.bot.add_view(TicketView(self.bot))

    @tasks.loop(minutes=5)
    async def sync_names(self):
        """Periodically sync missing names for tickets"""
        try:
            # Get all tickets that have Unknown owner_name or missing assigned_name
            async with self.bot.db.db.execute("SELECT channel_id, owner_id, assigned_to FROM tickets WHERE owner_name = 'Unknown' OR (assigned_to IS NOT NULL AND assigned_name IS NULL)") as cursor:
                tickets = await cursor.fetchall()
            
            if not tickets:
                return

            print(f"[TICKETS] Syncing names for {len(tickets)} tickets...")
            updated_count = 0
            for t_id, o_id, a_id in tickets:
                channel = self.bot.get_channel(t_id)
                if not channel: continue
                guild = channel.guild
                
                # Fetch owner name if needed
                try:
                    owner = guild.get_member(o_id) or await guild.fetch_member(o_id)
                    if owner:
                        await self.bot.db.db.execute("UPDATE tickets SET owner_name = ? WHERE channel_id = ?", (str(owner.display_name), t_id))
                        updated_count += 1
                except:
                    pass
                
                # Fetch admin name if assigned
                if a_id:
                    try:
                        admin = guild.get_member(a_id) or await guild.fetch_member(a_id)
                        if admin:
                            await self.bot.db.db.execute("UPDATE tickets SET assigned_name = ? WHERE channel_id = ?", (str(admin.display_name), t_id))
                            updated_count += 1
                    except:
                        pass
            
            await self.bot.db.db.commit()
            if updated_count > 0:
                print(f"[TICKETS] Successfully synced {updated_count} names.")
        except Exception as e:
            print(f"[ERROR] Name sync failed: {e}")

    @sync_names.before_loop
    async def before_sync(self):
        await self.bot.wait_until_ready()

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def ticket_options_menu(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu for ticket management"""
        # Check if this is a ticket channel
        ticket = await self.bot.db.get_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ This is not a valid ticket channel.", ephemeral=True)
            return

        # Permissions check
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only Admins can use Ticket Options.", ephemeral=True)
            return

        view = TicketOptionsView(self.bot, interaction.channel.id, interaction.guild)
        await interaction.response.send_message("Select an action for this ticket:", view=view, ephemeral=True)

    ticket_group = app_commands.Group(name="ticket", description="Ticket management commands")

    @ticket_group.command(name="priority", description="Set ticket priority")
    async def ticket_priority(self, interaction: discord.Interaction, priority: str):
        """Set ticket priority via command"""
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
            
        ticket = await self.bot.db.get_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
            return

        valid_priorities = ["Low", "Normal", "High", "Urgent"]
        if priority.capitalize() not in valid_priorities:
            await interaction.response.send_message(f"❌ Invalid priority. Choose from: {', '.join(valid_priorities)}", ephemeral=True)
            return

        await self.bot.db.update_ticket_priority(interaction.channel.id, priority.capitalize())
        await interaction.response.send_message(f"✅ Priority updated to **{priority.capitalize()}**")

    @ticket_group.command(name="transfer", description="Transfer ticket to another admin")
    async def ticket_transfer(self, interaction: discord.Interaction, admin: discord.Member):
        """Transfer ticket via command"""
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
            
        ticket = await self.bot.db.get_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
            return

        # Target admin check
        if not admin.guild_permissions.administrator and not await is_bot_admin(self.bot, admin.id):
             await interaction.response.send_message("❌ Target user must be an Admin.", ephemeral=True)
             return

        await self.bot.db.transfer_ticket(interaction.channel.id, admin.id, str(admin.display_name))
        await interaction.channel.set_permissions(admin, read_messages=True, send_messages=True, attach_files=True)
        await interaction.response.send_message(f"👤 Ticket transferred to {admin.mention}")

    @ticket_group.command(name="sync_names", description="Admin: Manually sync all ticket names")
    async def ticket_sync_names(self, interaction: discord.Interaction):
        """Manually trigger name sync"""
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
            
        await interaction.response.send_message("🔄 Syncing names... Please check console for progress.", ephemeral=True)
        await self.sync_names()
        await interaction.followup.send("✅ Name synchronization complete.", ephemeral=True)

    @app_commands.command(name="ticket_panel", description="Admin: Setup ticket panel")
    async def slash_ticket_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Setup ticket panel"""
        # Admin Check
        if not await is_bot_admin(self.bot, interaction.user.id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command is for Admins only.", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="🎫 Support Tickets",
            description="Click the button below to open a private support ticket.",
            color=discord.Color.blue()
        )
        
        await channel.send(embed=embed, view=TicketView(self.bot))
        await interaction.response.send_message(f"✅ Ticket panel sent to {channel.mention}", ephemeral=True)

    @app_commands.command(name="close_ticket", description="Close the current ticket")
    async def slash_close_ticket(self, interaction: discord.Interaction):
        """Close ticket"""
        # Check if this is a ticket channel
        ticket = await self.bot.db.get_ticket(interaction.channel.id)
        
        if not ticket:
            await interaction.response.send_message("❌ This is not a valid ticket channel.", ephemeral=True)
            return

        # Close logic
        await self.bot.db.close_ticket(interaction.channel.id)
        
        await interaction.response.send_message("🔒 Ticket closing in 5 seconds...")
        import asyncio
        await asyncio.sleep(5)
        
        try:
            await interaction.channel.delete()
        except:
            await interaction.response.send_message("❌ Failed to delete channel.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Don't log messages from other bots (but DO log our own bot's messages)
        if message.author.bot and message.author.id != self.bot.user.id:
            return
        
        # Only process text channels
        if not isinstance(message.channel, discord.TextChannel):
            return
        
        try:
            # Check if this channel is an open ticket
            ticket = await self.bot.db.get_ticket(message.channel.id)
            
            if ticket and ticket[3] == 'open':  # Status is at index 3
                # Log the message to the database
                await self.bot.db.log_ticket_message(
                    ticket_id=message.channel.id,
                    author_id=message.author.id,
                    author_name=str(message.author.name),
                    content=message.content or "(No content)",
                    is_bot=1 if message.author.bot else 0
                )
                print(f"[TICKET] Logged message in ticket {message.channel.id} from {message.author.name}")
        except Exception as e:
            print(f"[ERROR] Failed to log ticket message in {message.channel.id}: {e}")

async def setup(bot):
    await bot.add_cog(Tickets(bot))
