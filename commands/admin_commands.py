"""
Admin Commands Cog

Implements administrative commands for bot setup, configuration management,
and ticket embed creation with buttons.
"""

import logging
from typing import Optional, List

import discord
from discord.ext import commands
from discord import app_commands

from commands.base_cog import BaseCog, handle_errors, require_admin_role
from config.config_manager import ConfigManager, GuildConfig, ConfigurationError

logger = logging.getLogger(__name__)


class TicketCreateView(discord.ui.View):
    """Persistent view for ticket creation button."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="create_ticket_button"
    )
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle ticket creation button clicks."""
        # Get the bot instance and ticket manager
        bot = interaction.client
        
        if not hasattr(bot, 'ticket_manager') or not bot.ticket_manager:
            embed = discord.Embed(
                title="❌ Service Unavailable",
                description="Ticket system is currently unavailable. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Defer response as ticket creation might take time
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create the ticket using the ticket manager
            ticket = await bot.ticket_manager.create_ticket(interaction.user, interaction.guild)
            
            # Get the created channel
            channel = bot.get_channel(ticket.channel_id)
            if not channel:
                raise Exception("Failed to retrieve created ticket channel")
            
            # Send success response
            embed = discord.Embed(
                title="✅ Ticket Created",
                description=f"Your ticket has been created successfully!\n\n"
                           f"**Ticket ID:** {ticket.ticket_id}\n"
                           f"**Channel:** {channel.mention}\n\n"
                           f"Please head to your ticket channel to describe your issue.",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error creating ticket from button: {e}")
            
            # Check for specific error types
            if "already has an active ticket" in str(e).lower():
                embed = discord.Embed(
                    title="❌ Ticket Already Exists",
                    description="You already have an active ticket. Please use your existing ticket or wait for it to be closed.",
                    color=discord.Color.orange()
                )
            else:
                embed = discord.Embed(
                    title="❌ Ticket Creation Failed",
                    description="Failed to create your ticket. Please try again or contact an administrator.",
                    color=discord.Color.red()
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)


class AdminCommands(BaseCog):
    """Cog containing administrative commands for bot setup and configuration."""
    
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.config_manager: Optional[ConfigManager] = None
    
    async def cog_load(self):
        """Initialize config manager when cog loads."""
        await super().cog_load()
        
        # Get config manager from bot (will be available when core components are initialized)
        if hasattr(self.bot, 'config_manager') and self.bot.config_manager:
            self.config_manager = self.bot.config_manager
        else:
            # Create a temporary config manager for testing
            try:
                self.config_manager = ConfigManager()
                self.logger.info("Created temporary config manager")
            except Exception as e:
                self.logger.warning(f"Config manager not available: {e}")
        
        # Add the persistent view for ticket creation buttons
        self.bot.add_view(TicketCreateView())
    
    def _validate_config_manager(self) -> bool:
        """Check if config manager is available."""
        return self.config_manager is not None
    
    @app_commands.command(name="setup", description="Initial setup for the ticket system")
    @app_commands.describe(
        staff_role="The role that can manage tickets",
        ticket_category="Category where ticket channels will be created",
        log_channel="Channel for ticket logs (optional)"
    )
    @require_admin_role()
    @handle_errors
    async def setup(
        self,
        interaction: discord.Interaction,
        staff_role: discord.Role,
        ticket_category: discord.CategoryChannel,
        log_channel: Optional[discord.TextChannel] = None
    ):
        """
        Initial setup command for the ticket system.
        
        This command configures the basic settings needed for the ticket system
        to function properly in the server.
        
        Args:
            staff_role: Discord role that can manage tickets
            ticket_category: Category where ticket channels will be created
            log_channel: Optional channel for ticket logs
        """
        if not self._validate_config_manager():
            await self.send_error_embed(
                interaction,
                "❌ Configuration Unavailable",
                "Configuration system is currently unavailable. Please try again later."
            )
            return
        
        # Defer response as setup might take time
        await interaction.response.defer()
        
        try:
            # Get or create guild configuration
            guild_config = self.config_manager.get_guild_config(interaction.guild.id)
            
            # Update configuration
            guild_config.staff_roles = [staff_role.id]
            guild_config.ticket_category = ticket_category.id
            if log_channel:
                guild_config.log_channel = log_channel.id
            
            # Set default embed settings
            guild_config.embed_settings = {
                'title': '🎫 Support Tickets',
                'description': 'Click the button below to create a new support ticket.\n\n'
                              'Our staff team will assist you as soon as possible.',
                'color': 0x00ff00,  # Green color
                'footer': 'Ticket System'
            }
            
            # Save configuration
            self.config_manager.set_guild_config(guild_config)
            self.config_manager.save_configuration()
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Setup Complete",
                description="Ticket system has been configured successfully!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Staff Role",
                value=staff_role.mention,
                inline=True
            )
            embed.add_field(
                name="Ticket Category",
                value=ticket_category.mention,
                inline=True
            )
            
            if log_channel:
                embed.add_field(
                    name="Log Channel",
                    value=log_channel.mention,
                    inline=True
                )
            
            embed.add_field(
                name="Next Steps",
                value="Use `/ticket-embed` to send the ticket creation embed to a channel.",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except ConfigurationError as e:
            await self.send_error_embed(
                interaction,
                "❌ Configuration Error",
                f"Failed to save configuration: {str(e)}"
            )
            
        except Exception as e:
            self.logger.error(f"Unexpected error in setup command: {e}")
            await self.send_error_embed(
                interaction,
                "❌ Setup Failed",
                "An unexpected error occurred during setup. Please try again."
            )
    
    @app_commands.command(name="ticket-embed", description="Send the ticket creation embed with button")
    @app_commands.describe(
        channel="Channel to send the embed to (optional, defaults to current channel)",
        title="Custom title for the embed (optional)",
        description="Custom description for the embed (optional)"
    )
    @require_admin_role()
    @handle_errors
    async def send_ticket_embed(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        title: Optional[str] = None,
        description: Optional[str] = None
    ):
        """
        Send a ticket creation embed with button to a channel.
        
        This command sends an embed message with a button that users can click
        to create new support tickets.
        
        Args:
            channel: Channel to send the embed to (defaults to current channel)
            title: Custom title for the embed
            description: Custom description for the embed
        """
        if not self._validate_config_manager():
            await self.send_error_embed(
                interaction,
                "❌ Configuration Unavailable",
                "Configuration system is currently unavailable. Please try again later."
            )
            return
        
        # Use current channel if none specified
        target_channel = channel or interaction.channel
        
        if not isinstance(target_channel, discord.TextChannel):
            await self.send_error_embed(
                interaction,
                "❌ Invalid Channel",
                "The embed can only be sent to text channels."
            )
            return
        
        # Defer response
        await interaction.response.defer()
        
        try:
            # Get guild configuration for embed settings
            guild_config = self.config_manager.get_guild_config(interaction.guild.id)
            embed_settings = guild_config.embed_settings
            
            # Use custom values or fall back to configuration/defaults
            embed_title = title or embed_settings.get('title', '🎫 Support Tickets')
            embed_description = description or embed_settings.get(
                'description',
                'Click the button below to create a new support ticket.\n\n'
                'Our staff team will assist you as soon as possible.'
            )
            embed_color = embed_settings.get('color', 0x00ff00)
            embed_footer = embed_settings.get('footer', 'Ticket System')
            
            # Create the embed
            embed = discord.Embed(
                title=embed_title,
                description=embed_description,
                color=embed_color
            )
            embed.set_footer(text=embed_footer)
            
            # Add server icon if available
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
            
            # Create the view with the button
            view = TicketCreateView()
            
            # Send the embed to the target channel
            message = await target_channel.send(embed=embed, view=view)
            
            # Send confirmation
            confirmation_embed = discord.Embed(
                title="✅ Embed Sent",
                description=f"Ticket creation embed has been sent to {target_channel.mention}",
                color=discord.Color.green()
            )
            confirmation_embed.add_field(
                name="Message Link",
                value=f"[Click here to view]({message.jump_url})",
                inline=False
            )
            
            await interaction.followup.send(embed=confirmation_embed)
            
        except discord.Forbidden:
            await self.send_error_embed(
                interaction,
                "❌ Permission Denied",
                f"I don't have permission to send messages in {target_channel.mention}."
            )
            
        except Exception as e:
            self.logger.error(f"Unexpected error in send_ticket_embed command: {e}")
            await self.send_error_embed(
                interaction,
                "❌ Failed to Send Embed",
                "An unexpected error occurred while sending the embed."
            )
    
    @app_commands.command(name="config", description="View or modify bot configuration")
    @app_commands.describe(
        action="Action to perform (view, set-staff-role, set-category, set-log-channel)",
        value="Value for the configuration (role, channel, etc.)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="View Configuration", value="view"),
        app_commands.Choice(name="Add Staff Role", value="add-staff-role"),
        app_commands.Choice(name="Remove Staff Role", value="remove-staff-role"),
        app_commands.Choice(name="Set Ticket Category", value="set-category"),
        app_commands.Choice(name="Set Log Channel", value="set-log-channel"),
        app_commands.Choice(name="Clear Log Channel", value="clear-log-channel")
    ])
    @require_admin_role()
    @handle_errors
    async def config(
        self,
        interaction: discord.Interaction,
        action: str,
        value: Optional[str] = None
    ):
        """
        View or modify bot configuration for this server.
        
        This command allows administrators to view and modify various
        configuration settings for the ticket system.
        
        Args:
            action: The configuration action to perform
            value: The value for the configuration (when applicable)
        """
        if not self._validate_config_manager():
            await self.send_error_embed(
                interaction,
                "❌ Configuration Unavailable",
                "Configuration system is currently unavailable. Please try again later."
            )
            return
        
        # Defer response
        await interaction.response.defer()
        
        try:
            guild_config = self.config_manager.get_guild_config(interaction.guild.id)
            
            if action == "view":
                await self._handle_view_config(interaction, guild_config)
            elif action == "add-staff-role":
                await self._handle_add_staff_role(interaction, guild_config, value)
            elif action == "remove-staff-role":
                await self._handle_remove_staff_role(interaction, guild_config, value)
            elif action == "set-category":
                await self._handle_set_category(interaction, guild_config, value)
            elif action == "set-log-channel":
                await self._handle_set_log_channel(interaction, guild_config, value)
            elif action == "clear-log-channel":
                await self._handle_clear_log_channel(interaction, guild_config)
            else:
                await self.send_error_embed(
                    interaction,
                    "❌ Invalid Action",
                    f"Unknown configuration action: {action}"
                )
                
        except Exception as e:
            self.logger.error(f"Unexpected error in config command: {e}")
            await self.send_error_embed(
                interaction,
                "❌ Configuration Error",
                "An unexpected error occurred while managing configuration."
            )
    
    async def _handle_view_config(self, interaction: discord.Interaction, guild_config: GuildConfig):
        """Handle viewing the current configuration."""
        embed = discord.Embed(
            title="⚙️ Server Configuration",
            description=f"Current configuration for **{interaction.guild.name}**",
            color=discord.Color.blue()
        )
        
        # Staff roles
        if guild_config.staff_roles:
            staff_role_mentions = []
            for role_id in guild_config.staff_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    staff_role_mentions.append(role.mention)
                else:
                    staff_role_mentions.append(f"Unknown Role ({role_id})")
            
            embed.add_field(
                name="Staff Roles",
                value="\n".join(staff_role_mentions),
                inline=False
            )
        else:
            embed.add_field(
                name="Staff Roles",
                value="*Not configured*",
                inline=False
            )
        
        # Ticket category
        if guild_config.ticket_category:
            category = interaction.guild.get_channel(guild_config.ticket_category)
            category_value = category.mention if category else f"Unknown Category ({guild_config.ticket_category})"
        else:
            category_value = "*Not configured*"
        
        embed.add_field(
            name="Ticket Category",
            value=category_value,
            inline=True
        )
        
        # Log channel
        if guild_config.log_channel:
            log_channel = interaction.guild.get_channel(guild_config.log_channel)
            log_value = log_channel.mention if log_channel else f"Unknown Channel ({guild_config.log_channel})"
        else:
            log_value = "*Not configured*"
        
        embed.add_field(
            name="Log Channel",
            value=log_value,
            inline=True
        )
        
        await interaction.followup.send(embed=embed)
    
    async def _handle_add_staff_role(self, interaction: discord.Interaction, guild_config: GuildConfig, value: Optional[str]):
        """Handle adding a staff role."""
        if not value:
            await self.send_error_embed(
                interaction,
                "❌ Missing Value",
                "Please provide a role ID or mention to add as a staff role."
            )
            return
        
        # Try to parse role ID or mention
        try:
            # Remove mention formatting if present
            role_id_str = value.strip('<@&>')
            role_id = int(role_id_str)
            
            # Verify role exists
            role = interaction.guild.get_role(role_id)
            if not role:
                await self.send_error_embed(
                    interaction,
                    "❌ Role Not Found",
                    f"Could not find a role with ID {role_id} in this server."
                )
                return
            
            # Check if role is already a staff role
            if role_id in guild_config.staff_roles:
                await self.send_error_embed(
                    interaction,
                    "❌ Role Already Added",
                    f"{role.mention} is already configured as a staff role."
                )
                return
            
            # Add the role
            guild_config.staff_roles.append(role_id)
            self.config_manager.set_guild_config(guild_config)
            self.config_manager.save_configuration()
            
            await self.send_success_embed(
                interaction,
                "✅ Staff Role Added",
                f"{role.mention} has been added as a staff role."
            )
            
        except ValueError:
            await self.send_error_embed(
                interaction,
                "❌ Invalid Role",
                "Please provide a valid role ID or mention."
            )
    
    async def _handle_remove_staff_role(self, interaction: discord.Interaction, guild_config: GuildConfig, value: Optional[str]):
        """Handle removing a staff role."""
        if not value:
            await self.send_error_embed(
                interaction,
                "❌ Missing Value",
                "Please provide a role ID or mention to remove from staff roles."
            )
            return
        
        try:
            # Remove mention formatting if present
            role_id_str = value.strip('<@&>')
            role_id = int(role_id_str)
            
            # Check if role is in staff roles
            if role_id not in guild_config.staff_roles:
                await self.send_error_embed(
                    interaction,
                    "❌ Role Not Found",
                    "This role is not configured as a staff role."
                )
                return
            
            # Remove the role
            guild_config.staff_roles.remove(role_id)
            self.config_manager.set_guild_config(guild_config)
            self.config_manager.save_configuration()
            
            # Get role name for confirmation
            role = interaction.guild.get_role(role_id)
            role_name = role.mention if role else f"Role ({role_id})"
            
            await self.send_success_embed(
                interaction,
                "✅ Staff Role Removed",
                f"{role_name} has been removed from staff roles."
            )
            
        except ValueError:
            await self.send_error_embed(
                interaction,
                "❌ Invalid Role",
                "Please provide a valid role ID or mention."
            )
    
    async def _handle_set_category(self, interaction: discord.Interaction, guild_config: GuildConfig, value: Optional[str]):
        """Handle setting the ticket category."""
        if not value:
            await self.send_error_embed(
                interaction,
                "❌ Missing Value",
                "Please provide a category ID or mention to set as the ticket category."
            )
            return
        
        try:
            # Remove mention formatting if present
            category_id_str = value.strip('<#>')
            category_id = int(category_id_str)
            
            # Verify category exists and is actually a category
            category = interaction.guild.get_channel(category_id)
            if not category or not isinstance(category, discord.CategoryChannel):
                await self.send_error_embed(
                    interaction,
                    "❌ Category Not Found",
                    f"Could not find a category channel with ID {category_id} in this server."
                )
                return
            
            # Set the category
            guild_config.ticket_category = category_id
            self.config_manager.set_guild_config(guild_config)
            self.config_manager.save_configuration()
            
            await self.send_success_embed(
                interaction,
                "✅ Ticket Category Set",
                f"Ticket category has been set to {category.mention}."
            )
            
        except ValueError:
            await self.send_error_embed(
                interaction,
                "❌ Invalid Category",
                "Please provide a valid category ID or mention."
            )
    
    async def _handle_set_log_channel(self, interaction: discord.Interaction, guild_config: GuildConfig, value: Optional[str]):
        """Handle setting the log channel."""
        if not value:
            await self.send_error_embed(
                interaction,
                "❌ Missing Value",
                "Please provide a channel ID or mention to set as the log channel."
            )
            return
        
        try:
            # Remove mention formatting if present
            channel_id_str = value.strip('<#>')
            channel_id = int(channel_id_str)
            
            # Verify channel exists and is a text channel
            channel = interaction.guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                await self.send_error_embed(
                    interaction,
                    "❌ Channel Not Found",
                    f"Could not find a text channel with ID {channel_id} in this server."
                )
                return
            
            # Set the log channel
            guild_config.log_channel = channel_id
            self.config_manager.set_guild_config(guild_config)
            self.config_manager.save_configuration()
            
            await self.send_success_embed(
                interaction,
                "✅ Log Channel Set",
                f"Log channel has been set to {channel.mention}."
            )
            
        except ValueError:
            await self.send_error_embed(
                interaction,
                "❌ Invalid Channel",
                "Please provide a valid channel ID or mention."
            )
    
    async def _handle_clear_log_channel(self, interaction: discord.Interaction, guild_config: GuildConfig):
        """Handle clearing the log channel."""
        guild_config.log_channel = None
        self.config_manager.set_guild_config(guild_config)
        self.config_manager.save_configuration()
        
        await self.send_success_embed(
            interaction,
            "✅ Log Channel Cleared",
            "Log channel has been cleared. Ticket logs will not be sent to any channel."
        )


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(AdminCommands(bot))