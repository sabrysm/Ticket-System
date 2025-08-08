"""
Ticket Commands Cog

Implements core ticket management commands including ticket creation,
user management, and ticket closing functionality.
"""

import logging
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from commands.base_cog import BaseCog
from errors import (
    handle_errors, require_staff_role, TicketBotError, TicketCreationError,
    UserManagementError, PermissionError as TicketPermissionError,
    TicketClosingError, TicketNotFoundError, log_error
)
from logging_config import get_logger, get_audit_logger
from core.ticket_manager import TicketManager
from models.ticket import TicketStatus

logger = get_logger(__name__)
audit_logger = get_audit_logger()


class TicketCommands(BaseCog):
    """Cog containing core ticket management commands."""
    
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.ticket_manager: Optional[TicketManager] = None
    
    async def cog_load(self):
        """Initialize ticket manager when cog loads."""
        await super().cog_load()
        
        # Get ticket manager from bot (will be available when core components are initialized)
        if hasattr(self.bot, 'ticket_manager') and self.bot.ticket_manager:
            self.ticket_manager = self.bot.ticket_manager
        else:
            self.logger.warning("Ticket manager not available - some commands may not work")
    
    def _validate_ticket_manager(self) -> bool:
        """Check if ticket manager is available."""
        return self.ticket_manager is not None
    
    @app_commands.command(name="new", description="Create a new support ticket")
    @handle_errors
    async def new_ticket(self, interaction: discord.Interaction):
        """
        Create a new support ticket for the user.
        
        This command creates a private channel for the user to discuss their issue
        with staff members. Only one active ticket per user is allowed.
        """
        if not self._validate_ticket_manager():
            await self.send_error_embed(
                interaction,
                "❌ Service Unavailable",
                "Ticket system is currently unavailable. Please try again later."
            )
            return
        
        # Defer response as ticket creation might take time
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create the ticket
            ticket = await self.ticket_manager.create_ticket(interaction.user, interaction.guild)
            
            # Get the created channel
            channel = self.bot.get_channel(ticket.channel_id)
            if not channel:
                raise TicketCreationError("Failed to retrieve created ticket channel")
            
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
            
            # Log audit event for successful command usage
            audit_logger.log_command_used(
                command_name="new_ticket",
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
                success=True,
                additional_info={'ticket_id': ticket.ticket_id}
            )
            
        except TicketPermissionError as e:
            # User already has an active ticket
            embed = discord.Embed(
                title="❌ Ticket Already Exists",
                description=f"You already have an active ticket. Please use your existing ticket or wait for it to be closed.\n\n"
                           f"If you can't find your ticket, please contact a staff member.",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except TicketCreationError as e:
            await self.send_error_embed(
                interaction,
                "❌ Ticket Creation Failed",
                f"Failed to create your ticket: {str(e)}\n\nPlease try again or contact an administrator."
            )
            
        except Exception as e:
            self.logger.error(f"Unexpected error in new_ticket command: {e}")
            await self.send_error_embed(
                interaction,
                "❌ Unexpected Error",
                "An unexpected error occurred while creating your ticket. Please try again later."
            )
    
    @app_commands.command(name="add", description="Add a user to the current ticket")
    @app_commands.describe(user="The user to add to this ticket")
    @require_staff_role()
    @handle_errors
    async def add_user(self, interaction: discord.Interaction, user: discord.Member):
        """
        Add a user to the current ticket channel.
        
        This command allows staff members to add other users to an existing ticket
        so they can participate in the conversation.
        
        Args:
            user: The Discord member to add to the ticket
        """
        if not self._validate_ticket_manager():
            await self.send_error_embed(
                interaction,
                "❌ Service Unavailable",
                "Ticket system is currently unavailable. Please try again later."
            )
            return
        
        # Check if command is used in a ticket channel
        if not isinstance(interaction.channel, discord.TextChannel):
            await self.send_error_embed(
                interaction,
                "❌ Invalid Channel",
                "This command can only be used in ticket channels."
            )
            return
        
        # Defer response as user addition might take time
        await interaction.response.defer()
        
        try:
            # Validate that this is actually a ticket channel
            ticket = await self.ticket_manager.get_ticket_by_channel(interaction.channel.id)
            if not ticket:
                await self.send_error_embed(
                    interaction,
                    "❌ Not a Ticket Channel",
                    "This command can only be used in active ticket channels."
                )
                return
            
            # Check if ticket is open
            if ticket.status != TicketStatus.OPEN:
                await self.send_error_embed(
                    interaction,
                    "❌ Ticket Closed",
                    f"Cannot add users to a {ticket.status.value} ticket."
                )
                return
            
            # Add the user to the ticket
            success = await self.ticket_manager.add_user_to_ticket(
                interaction.channel, user, interaction.user
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ User Added",
                    description=f"{user.mention} has been successfully added to this ticket.",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            else:
                await self.send_error_embed(
                    interaction,
                    "❌ Addition Failed",
                    "Failed to add the user to this ticket. Please try again."
                )
                
        except UserManagementError as e:
            if "already in ticket" in str(e).lower():
                await self.send_error_embed(
                    interaction,
                    "❌ User Already Added",
                    f"{user.mention} is already a participant in this ticket."
                )
            else:
                await self.send_error_embed(
                    interaction,
                    "❌ Addition Failed",
                    f"Failed to add user: {str(e)}"
                )
                
        except TicketNotFoundError:
            await self.send_error_embed(
                interaction,
                "❌ Ticket Not Found",
                "This doesn't appear to be a valid ticket channel."
            )
            
        except Exception as e:
            self.logger.error(f"Unexpected error in add_user command: {e}")
            await self.send_error_embed(
                interaction,
                "❌ Unexpected Error",
                "An unexpected error occurred while adding the user."
            )
    
    @app_commands.command(name="remove", description="Remove a user from the current ticket")
    @app_commands.describe(user="The user to remove from this ticket")
    @require_staff_role()
    @handle_errors
    async def remove_user(self, interaction: discord.Interaction, user: discord.Member):
        """
        Remove a user from the current ticket channel.
        
        This command allows staff members to remove users from an existing ticket.
        Note: Removing the ticket creator requires additional confirmation.
        
        Args:
            user: The Discord member to remove from the ticket
        """
        if not self._validate_ticket_manager():
            await self.send_error_embed(
                interaction,
                "❌ Service Unavailable",
                "Ticket system is currently unavailable. Please try again later."
            )
            return
        
        # Check if command is used in a ticket channel
        if not isinstance(interaction.channel, discord.TextChannel):
            await self.send_error_embed(
                interaction,
                "❌ Invalid Channel",
                "This command can only be used in ticket channels."
            )
            return
        
        # Defer response as user removal might take time
        await interaction.response.defer()
        
        try:
            # Validate that this is actually a ticket channel
            ticket = await self.ticket_manager.get_ticket_by_channel(interaction.channel.id)
            if not ticket:
                await self.send_error_embed(
                    interaction,
                    "❌ Not a Ticket Channel",
                    "This command can only be used in active ticket channels."
                )
                return
            
            # Check if ticket is open
            if ticket.status != TicketStatus.OPEN:
                await self.send_error_embed(
                    interaction,
                    "❌ Ticket Closed",
                    f"Cannot remove users from a {ticket.status.value} ticket."
                )
                return
            
            # Remove the user from the ticket
            success = await self.ticket_manager.remove_user_from_ticket(
                interaction.channel, user, interaction.user
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ User Removed",
                    description=f"{user.mention} has been successfully removed from this ticket.",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            else:
                await self.send_error_embed(
                    interaction,
                    "❌ Removal Failed",
                    "Failed to remove the user from this ticket. Please try again."
                )
                
        except TicketPermissionError as e:
            if "ticket creator" in str(e).lower():
                await self.send_error_embed(
                    interaction,
                    "❌ Cannot Remove Creator",
                    "Cannot remove the ticket creator without additional confirmation. "
                    "Please use the close ticket command instead."
                )
            else:
                await self.send_error_embed(
                    interaction,
                    "❌ Permission Denied",
                    f"Permission error: {str(e)}"
                )
                
        except UserManagementError as e:
            if "not in ticket" in str(e).lower():
                await self.send_error_embed(
                    interaction,
                    "❌ User Not Found",
                    f"{user.mention} is not a participant in this ticket."
                )
            else:
                await self.send_error_embed(
                    interaction,
                    "❌ Removal Failed",
                    f"Failed to remove user: {str(e)}"
                )
                
        except TicketNotFoundError:
            await self.send_error_embed(
                interaction,
                "❌ Ticket Not Found",
                "This doesn't appear to be a valid ticket channel."
            )
            
        except Exception as e:
            self.logger.error(f"Unexpected error in remove_user command: {e}")
            await self.send_error_embed(
                interaction,
                "❌ Unexpected Error",
                "An unexpected error occurred while removing the user."
            )
    
    @app_commands.command(name="close", description="Close the current ticket")
    @app_commands.describe(reason="Optional reason for closing the ticket")
    @require_staff_role()
    @handle_errors
    async def close_ticket(self, interaction: discord.Interaction, reason: Optional[str] = None):
        """
        Close the current ticket with optional reason.
        
        This command closes the ticket, generates a transcript, and archives
        or deletes the channel based on server configuration.
        
        Args:
            reason: Optional reason for closing the ticket
        """
        if not self._validate_ticket_manager():
            await self.send_error_embed(
                interaction,
                "❌ Service Unavailable",
                "Ticket system is currently unavailable. Please try again later."
            )
            return
        
        # Check if command is used in a ticket channel
        if not isinstance(interaction.channel, discord.TextChannel):
            await self.send_error_embed(
                interaction,
                "❌ Invalid Channel",
                "This command can only be used in ticket channels."
            )
            return
        
        # Defer response as ticket closing might take time
        await interaction.response.defer()
        
        try:
            # Validate that this is actually a ticket channel
            ticket = await self.ticket_manager.get_ticket_by_channel(interaction.channel.id)
            if not ticket:
                await self.send_error_embed(
                    interaction,
                    "❌ Not a Ticket Channel",
                    "This command can only be used in active ticket channels."
                )
                return
            
            # Check if ticket is already closed
            if ticket.status != TicketStatus.OPEN:
                await self.send_error_embed(
                    interaction,
                    "❌ Ticket Already Closed",
                    f"This ticket is already {ticket.status.value}."
                )
                return
            
            # Send confirmation message before closing
            embed = discord.Embed(
                title="🔒 Closing Ticket",
                description=f"Ticket {ticket.ticket_id} is being closed by {interaction.user.mention}.\n\n"
                           f"**Reason:** {reason or 'No reason provided'}\n\n"
                           f"Generating transcript and archiving channel...",
                color=discord.Color.orange()
            )
            
            await interaction.followup.send(embed=embed)
            
            # Close the ticket
            success = await self.ticket_manager.close_ticket(
                interaction.channel, interaction.user, reason
            )
            
            if not success:
                await self.send_error_embed(
                    interaction,
                    "❌ Closing Failed",
                    "Failed to close the ticket. Please try again or contact an administrator."
                )
                
        except TicketClosingError as e:
            await self.send_error_embed(
                interaction,
                "❌ Closing Failed",
                f"Failed to close ticket: {str(e)}"
            )
            
        except TicketNotFoundError:
            await self.send_error_embed(
                interaction,
                "❌ Ticket Not Found",
                "This doesn't appear to be a valid ticket channel."
            )
            
        except Exception as e:
            self.logger.error(f"Unexpected error in close_ticket command: {e}")
            await self.send_error_embed(
                interaction,
                "❌ Unexpected Error",
                "An unexpected error occurred while closing the ticket."
            )
    
    @app_commands.command(name="info", description="Get information about the current ticket")
    @handle_errors
    async def ticket_info(self, interaction: discord.Interaction):
        """
        Display information about the current ticket.
        
        Shows ticket ID, creator, creation time, participants, and status.
        """
        if not self._validate_ticket_manager():
            await self.send_error_embed(
                interaction,
                "❌ Service Unavailable",
                "Ticket system is currently unavailable. Please try again later."
            )
            return
        
        # Check if command is used in a ticket channel
        if not isinstance(interaction.channel, discord.TextChannel):
            await self.send_error_embed(
                interaction,
                "❌ Invalid Channel",
                "This command can only be used in ticket channels."
            )
            return
        
        try:
            # Get ticket information
            ticket = await self.ticket_manager.get_ticket_by_channel(interaction.channel.id)
            if not ticket:
                await self.send_error_embed(
                    interaction,
                    "❌ Not a Ticket Channel",
                    "This doesn't appear to be a valid ticket channel."
                )
                return
            
            # Get creator information
            creator = self.bot.get_user(ticket.creator_id)
            creator_name = creator.display_name if creator else f"Unknown User ({ticket.creator_id})"
            
            # Build participant list
            participant_mentions = []
            for user_id in ticket.participants:
                user = self.bot.get_user(user_id)
                if user:
                    participant_mentions.append(user.mention)
                else:
                    participant_mentions.append(f"Unknown User ({user_id})")
            
            # Create info embed
            embed = discord.Embed(
                title=f"📋 Ticket Information",
                color=discord.Color.blue(),
                timestamp=ticket.created_at
            )
            
            embed.add_field(name="Ticket ID", value=ticket.ticket_id, inline=True)
            embed.add_field(name="Status", value=ticket.status.value.title(), inline=True)
            embed.add_field(name="Creator", value=creator_name, inline=True)
            
            embed.add_field(
                name="Participants",
                value="\n".join(participant_mentions) if participant_mentions else "None",
                inline=False
            )
            
            if ticket.closed_at:
                embed.add_field(name="Closed At", value=ticket.closed_at.strftime('%Y-%m-%d %H:%M:%S UTC'), inline=True)
            
            embed.set_footer(text="Created")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Unexpected error in ticket_info command: {e}")
            await self.send_error_embed(
                interaction,
                "❌ Unexpected Error",
                "An unexpected error occurred while retrieving ticket information."
            )


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(TicketCommands(bot))