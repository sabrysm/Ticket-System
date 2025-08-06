"""
Ticket Manager for Discord Ticket Bot.

This module provides the core ticket management functionality including
ticket creation, user management, and lifecycle operations.
"""

import asyncio
import logging
import secrets
import string
import io
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import discord
from discord.ext import commands

from models.ticket import Ticket, TicketStatus
from database.adapter import DatabaseAdapter, DatabaseError, TicketNotFoundError
from config.config_manager import ConfigManager, GuildConfig

logger = logging.getLogger(__name__)


class TicketManagerError(Exception):
    """Base exception for ticket manager errors."""
    pass


class TicketCreationError(TicketManagerError):
    """Exception raised when ticket creation fails."""
    pass


class UserManagementError(TicketManagerError):
    """Exception raised when user management operations fail."""
    pass


class PermissionError(TicketManagerError):
    """Exception raised when user lacks required permissions."""
    pass


class TicketClosingError(TicketManagerError):
    """Exception raised when ticket closing fails."""
    pass


class TranscriptError(TicketManagerError):
    """Exception raised when transcript generation fails."""
    pass


class TicketManager:
    """
    Core ticket management system.
    
    Handles ticket lifecycle operations including creation, user management,
    and integration with Discord channels and database storage.
    """
    
    def __init__(self, bot: commands.Bot, database_adapter: DatabaseAdapter, config_manager: ConfigManager):
        """
        Initialize TicketManager.
        
        Args:
            bot: Discord bot instance
            database_adapter: Database adapter for ticket storage
            config_manager: Configuration manager for bot settings
        """
        self.bot = bot
        self.database = database_adapter
        self.config = config_manager
        self._ticket_locks: Dict[str, asyncio.Lock] = {}
    
    def _generate_ticket_id(self) -> str:
        """
        Generate a unique ticket ID.
        
        Returns:
            str: Unique ticket identifier (8 characters, alphanumeric)
        """
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(8))
    
    async def _get_ticket_lock(self, ticket_id: str) -> asyncio.Lock:
        """
        Get or create a lock for a specific ticket to prevent race conditions.
        
        Args:
            ticket_id: Ticket identifier
            
        Returns:
            asyncio.Lock: Lock for the ticket
        """
        if ticket_id not in self._ticket_locks:
            self._ticket_locks[ticket_id] = asyncio.Lock()
        return self._ticket_locks[ticket_id]
    
    async def _create_ticket_channel(self, guild: discord.Guild, ticket_id: str, 
                                   creator: discord.Member, guild_config: GuildConfig) -> discord.TextChannel:
        """
        Create a Discord channel for the ticket.
        
        Args:
            guild: Discord guild where ticket is created
            ticket_id: Unique ticket identifier
            creator: User who created the ticket
            guild_config: Guild-specific configuration
            
        Returns:
            discord.TextChannel: Created ticket channel
            
        Raises:
            TicketCreationError: If channel creation fails
        """
        try:
            # Determine category for ticket channel
            category = None
            if guild_config.ticket_category:
                category = guild.get_channel(guild_config.ticket_category)
                if not category or not isinstance(category, discord.CategoryChannel):
                    logger.warning(f"Invalid ticket category {guild_config.ticket_category} for guild {guild.id}")
            
            # Create channel name
            channel_name = f"ticket-{ticket_id.lower()}"
            
            # Set up channel permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                creator: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    read_message_history=True
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    read_message_history=True
                )
            }
            
            # Add staff roles to channel permissions
            for role_id in guild_config.staff_roles:
                role = guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True,
                        read_message_history=True
                    )
            
            # Create the channel
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Support ticket {ticket_id} - Created by {creator.display_name}",
                reason=f"Ticket {ticket_id} created by {creator}"
            )
            
            logger.info(f"Created ticket channel {channel.id} for ticket {ticket_id}")
            return channel
            
        except discord.Forbidden:
            raise TicketCreationError("Bot lacks permission to create channels")
        except discord.HTTPException as e:
            raise TicketCreationError(f"Failed to create channel: {e}")
        except Exception as e:
            raise TicketCreationError(f"Unexpected error creating channel: {e}")
    
    async def create_ticket(self, user: discord.Member, guild: discord.Guild) -> Ticket:
        """
        Create a new support ticket.
        
        Args:
            user: Discord member creating the ticket
            guild: Discord guild where ticket is created
            
        Returns:
            Ticket: Created ticket object
            
        Raises:
            TicketCreationError: If ticket creation fails
            PermissionError: If user already has an active ticket
        """
        try:
            # Check if user already has an active ticket
            existing_ticket = await self.database.get_active_ticket_for_user(user.id, guild.id)
            if existing_ticket:
                raise PermissionError(f"User {user.id} already has an active ticket: {existing_ticket.ticket_id}")
            
            # Get guild configuration
            guild_config = self.config.get_guild_config(guild.id)
            
            # Generate unique ticket ID
            ticket_id = self._generate_ticket_id()
            
            # Ensure ticket ID is unique (retry if collision)
            max_retries = 5
            for attempt in range(max_retries):
                existing = await self.database.get_ticket(ticket_id)
                if not existing:
                    break
                ticket_id = self._generate_ticket_id()
                if attempt == max_retries - 1:
                    raise TicketCreationError("Failed to generate unique ticket ID")
            
            # Create Discord channel
            channel = await self._create_ticket_channel(guild, ticket_id, user, guild_config)
            
            # Create ticket object
            ticket = Ticket(
                ticket_id=ticket_id,
                guild_id=guild.id,
                channel_id=channel.id,
                creator_id=user.id,
                status=TicketStatus.OPEN,
                created_at=datetime.utcnow(),
                participants=[user.id]
            )
            
            # Save ticket to database
            await self.database.create_ticket(ticket)
            
            # Send welcome message to ticket channel
            embed = discord.Embed(
                title=f"Ticket {ticket_id}",
                description=f"Hello {user.mention}! Your support ticket has been created.\n\n"
                           f"Please describe your issue and a staff member will assist you shortly.",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Ticket ID", value=ticket_id, inline=True)
            embed.add_field(name="Created by", value=user.mention, inline=True)
            embed.set_footer(text="Ticket System")
            
            await channel.send(embed=embed)
            
            logger.info(f"Created ticket {ticket_id} for user {user.id} in guild {guild.id}")
            return ticket
            
        except PermissionError:
            raise
        except TicketCreationError:
            raise
        except DatabaseError as e:
            raise TicketCreationError(f"Database error during ticket creation: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating ticket: {e}")
            raise TicketCreationError(f"Unexpected error: {e}")
    
    async def add_user_to_ticket(self, channel: discord.TextChannel, user: discord.Member, 
                               staff: discord.Member) -> bool:
        """
        Add a user to an existing ticket.
        
        Args:
            channel: Ticket channel
            user: User to add to the ticket
            staff: Staff member performing the action
            
        Returns:
            bool: True if user was added successfully
            
        Raises:
            UserManagementError: If adding user fails
            PermissionError: If staff member lacks permission
            TicketNotFoundError: If ticket is not found
        """
        try:
            # Get ticket from database using channel ID
            tickets = await self.database.get_tickets_by_guild(channel.guild.id)
            ticket = None
            for t in tickets:
                if t.channel_id == channel.id:
                    ticket = t
                    break
            
            if not ticket:
                raise TicketNotFoundError(f"No ticket found for channel {channel.id}")
            
            # Check if ticket is open
            if ticket.status != TicketStatus.OPEN:
                raise UserManagementError(f"Cannot add user to {ticket.status.value} ticket")
            
            # Verify staff permissions
            guild_config = self.config.get_guild_config(channel.guild.id)
            if not any(role.id in guild_config.staff_roles for role in staff.roles):
                raise PermissionError(f"User {staff.id} is not authorized to manage tickets")
            
            # Check if user is already in ticket
            if user.id in ticket.participants:
                raise UserManagementError(f"User {user.id} is already in ticket {ticket.ticket_id}")
            
            # Get ticket lock to prevent race conditions
            lock = await self._get_ticket_lock(ticket.ticket_id)
            async with lock:
                # Add user to channel permissions
                await channel.set_permissions(
                    user,
                    read_messages=True,
                    send_messages=True,
                    read_message_history=True,
                    reason=f"Added to ticket {ticket.ticket_id} by {staff}"
                )
                
                # Update database
                success = await self.database.add_participant(ticket.ticket_id, user.id)
                if not success:
                    # Revert channel permissions if database update failed
                    await channel.set_permissions(user, overwrite=None)
                    raise UserManagementError(f"Failed to add user {user.id} to ticket database")
                
                # Send notification message
                embed = discord.Embed(
                    title="User Added",
                    description=f"{user.mention} has been added to this ticket by {staff.mention}",
                    color=discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )
                await channel.send(embed=embed)
                
                logger.info(f"Added user {user.id} to ticket {ticket.ticket_id} by staff {staff.id}")
                return True
                
        except (PermissionError, UserManagementError, TicketNotFoundError):
            raise
        except discord.Forbidden:
            raise UserManagementError("Bot lacks permission to modify channel permissions")
        except discord.HTTPException as e:
            raise UserManagementError(f"Discord API error: {e}")
        except DatabaseError as e:
            raise UserManagementError(f"Database error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error adding user to ticket: {e}")
            raise UserManagementError(f"Unexpected error: {e}")
    
    async def remove_user_from_ticket(self, channel: discord.TextChannel, user: discord.Member, 
                                    staff: discord.Member) -> bool:
        """
        Remove a user from an existing ticket.
        
        Args:
            channel: Ticket channel
            user: User to remove from the ticket
            staff: Staff member performing the action
            
        Returns:
            bool: True if user was removed successfully
            
        Raises:
            UserManagementError: If removing user fails
            PermissionError: If staff member lacks permission or trying to remove creator
            TicketNotFoundError: If ticket is not found
        """
        try:
            # Get ticket from database using channel ID
            tickets = await self.database.get_tickets_by_guild(channel.guild.id)
            ticket = None
            for t in tickets:
                if t.channel_id == channel.id:
                    ticket = t
                    break
            
            if not ticket:
                raise TicketNotFoundError(f"No ticket found for channel {channel.id}")
            
            # Check if ticket is open
            if ticket.status != TicketStatus.OPEN:
                raise UserManagementError(f"Cannot remove user from {ticket.status.value} ticket")
            
            # Verify staff permissions
            guild_config = self.config.get_guild_config(channel.guild.id)
            if not any(role.id in guild_config.staff_roles for role in staff.roles):
                raise PermissionError(f"User {staff.id} is not authorized to manage tickets")
            
            # Check if trying to remove ticket creator (requires confirmation)
            if user.id == ticket.creator_id:
                raise PermissionError(f"Cannot remove ticket creator {user.id} without additional confirmation")
            
            # Check if user is in ticket
            if user.id not in ticket.participants:
                raise UserManagementError(f"User {user.id} is not in ticket {ticket.ticket_id}")
            
            # Get ticket lock to prevent race conditions
            lock = await self._get_ticket_lock(ticket.ticket_id)
            async with lock:
                # Remove user from channel permissions
                await channel.set_permissions(
                    user,
                    overwrite=None,
                    reason=f"Removed from ticket {ticket.ticket_id} by {staff}"
                )
                
                # Update database
                success = await self.database.remove_participant(ticket.ticket_id, user.id)
                if not success:
                    # Revert channel permissions if database update failed
                    await channel.set_permissions(
                        user,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True
                    )
                    raise UserManagementError(f"Failed to remove user {user.id} from ticket database")
                
                # Send notification message
                embed = discord.Embed(
                    title="User Removed",
                    description=f"{user.mention} has been removed from this ticket by {staff.mention}",
                    color=discord.Color.orange(),
                    timestamp=datetime.utcnow()
                )
                await channel.send(embed=embed)
                
                logger.info(f"Removed user {user.id} from ticket {ticket.ticket_id} by staff {staff.id}")
                return True
                
        except (PermissionError, UserManagementError, TicketNotFoundError):
            raise
        except discord.Forbidden:
            raise UserManagementError("Bot lacks permission to modify channel permissions")
        except discord.HTTPException as e:
            raise UserManagementError(f"Discord API error: {e}")
        except DatabaseError as e:
            raise UserManagementError(f"Database error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error removing user from ticket: {e}")
            raise UserManagementError(f"Unexpected error: {e}")
    
    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Ticket]:
        """
        Get ticket information by channel ID.
        
        Args:
            channel_id: Discord channel ID
            
        Returns:
            Optional[Ticket]: Ticket object if found, None otherwise
        """
        try:
            # This is a helper method that will be useful for other operations
            # We need to search through tickets to find one with matching channel_id
            # This could be optimized with a database index in the future
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return None
            
            tickets = await self.database.get_tickets_by_guild(channel.guild.id)
            for ticket in tickets:
                if ticket.channel_id == channel_id:
                    return ticket
            
            return None
            
        except DatabaseError as e:
            logger.error(f"Database error getting ticket by channel {channel_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting ticket by channel {channel_id}: {e}")
            return None
    
    async def is_user_staff(self, user: discord.Member) -> bool:
        """
        Check if a user has staff permissions in their guild.
        
        Args:
            user: Discord member to check
            
        Returns:
            bool: True if user is staff, False otherwise
        """
        try:
            guild_config = self.config.get_guild_config(user.guild.id)
            return any(role.id in guild_config.staff_roles for role in user.roles)
        except Exception as e:
            logger.error(f"Error checking staff status for user {user.id}: {e}")
            return False
    
    async def get_user_active_ticket(self, user_id: int, guild_id: int) -> Optional[Ticket]:
        """
        Get the active ticket for a user in a guild.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            Optional[Ticket]: Active ticket if found, None otherwise
        """
        try:
            return await self.database.get_active_ticket_for_user(user_id, guild_id)
        except DatabaseError as e:
            logger.error(f"Database error getting active ticket for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting active ticket for user {user_id}: {e}")
            return None
    
    async def _generate_transcript(self, channel: discord.TextChannel) -> str:
        """
        Generate a text transcript of the ticket conversation.
        
        Args:
            channel: Discord channel to generate transcript from
            
        Returns:
            str: Formatted transcript content
            
        Raises:
            TranscriptError: If transcript generation fails
        """
        try:
            transcript_lines = []
            transcript_lines.append(f"Ticket Transcript - {channel.name}")
            transcript_lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            transcript_lines.append("=" * 50)
            transcript_lines.append("")
            
            # Fetch all messages from the channel
            messages = []
            async for message in channel.history(limit=None, oldest_first=True):
                messages.append(message)
            
            # Format messages into transcript
            for message in messages:
                timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
                author = f"{message.author.display_name} ({message.author.id})"
                
                # Handle different message types
                if message.content:
                    content = message.content
                elif message.embeds:
                    content = "[Embed Message]"
                    for embed in message.embeds:
                        if embed.title:
                            content += f" Title: {embed.title}"
                        if embed.description:
                            content += f" Description: {embed.description}"
                elif message.attachments:
                    content = f"[{len(message.attachments)} Attachment(s)]"
                    for attachment in message.attachments:
                        content += f" {attachment.filename}"
                else:
                    content = "[System Message]"
                
                transcript_lines.append(f"[{timestamp}] {author}: {content}")
            
            transcript_lines.append("")
            transcript_lines.append("=" * 50)
            transcript_lines.append("End of Transcript")
            
            return "\n".join(transcript_lines)
            
        except discord.Forbidden:
            raise TranscriptError("Bot lacks permission to read message history")
        except discord.HTTPException as e:
            raise TranscriptError(f"Discord API error generating transcript: {e}")
        except Exception as e:
            logger.error(f"Unexpected error generating transcript for channel {channel.id}: {e}")
            raise TranscriptError(f"Unexpected error: {e}")
    
    async def _save_transcript(self, transcript_content: str, ticket_id: str, guild_id: int) -> Optional[str]:
        """
        Save transcript content to file and return the file path.
        
        Args:
            transcript_content: The transcript text content
            ticket_id: Unique ticket identifier
            guild_id: Discord guild ID
            
        Returns:
            Optional[str]: File path to saved transcript, None if saving failed
            
        Raises:
            TranscriptError: If transcript saving fails
        """
        try:
            # Create transcripts directory if it doesn't exist
            transcripts_dir = Path("transcripts") / str(guild_id)
            transcripts_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"ticket_{ticket_id}_{timestamp}.txt"
            file_path = transcripts_dir / filename
            
            # Write transcript to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(transcript_content)
            
            logger.info(f"Saved transcript for ticket {ticket_id} to {file_path}")
            return str(file_path)
            
        except OSError as e:
            logger.error(f"Failed to save transcript for ticket {ticket_id}: {e}")
            raise TranscriptError(f"Failed to save transcript: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving transcript for ticket {ticket_id}: {e}")
            raise TranscriptError(f"Unexpected error: {e}")
    
    async def _archive_channel(self, channel: discord.TextChannel, ticket_id: str) -> None:
        """
        Archive the ticket channel by moving it to archive category or deleting it.
        
        Args:
            channel: Discord channel to archive
            ticket_id: Unique ticket identifier
            
        Raises:
            TicketClosingError: If channel archiving fails
        """
        try:
            guild_config = self.config.get_guild_config(channel.guild.id)
            
            # Check if there's an archive category configured
            archive_category_id = getattr(guild_config, 'archive_category', None)
            
            if archive_category_id:
                # Move channel to archive category
                archive_category = channel.guild.get_channel(archive_category_id)
                if archive_category and isinstance(archive_category, discord.CategoryChannel):
                    # Rename channel to indicate it's closed
                    new_name = f"closed-{channel.name}"
                    await channel.edit(
                        name=new_name,
                        category=archive_category,
                        reason=f"Archived ticket {ticket_id}"
                    )
                    
                    # Remove permissions for non-staff users
                    overwrites = channel.overwrites
                    for target, overwrite in overwrites.items():
                        if isinstance(target, discord.Member):
                            # Remove access for regular members, keep staff access
                            if not any(role.id in guild_config.staff_roles for role in target.roles):
                                await channel.set_permissions(
                                    target,
                                    overwrite=None,
                                    reason=f"Archived ticket {ticket_id}"
                                )
                    
                    logger.info(f"Archived channel {channel.id} for ticket {ticket_id}")
                    return
            
            # If no archive category or it's invalid, delete the channel after a delay
            await asyncio.sleep(5)  # Give time for final messages
            await channel.delete(reason=f"Closed ticket {ticket_id}")
            logger.info(f"Deleted channel {channel.id} for ticket {ticket_id}")
            
        except discord.Forbidden:
            raise TicketClosingError("Bot lacks permission to archive/delete channel")
        except discord.HTTPException as e:
            raise TicketClosingError(f"Discord API error archiving channel: {e}")
        except Exception as e:
            logger.error(f"Unexpected error archiving channel {channel.id}: {e}")
            raise TicketClosingError(f"Unexpected error: {e}")
    
    async def close_ticket(self, channel: discord.TextChannel, staff: discord.Member, 
                          reason: Optional[str] = None) -> bool:
        """
        Close a ticket with transcript generation and channel archiving.
        
        Args:
            channel: Ticket channel to close
            staff: Staff member closing the ticket
            reason: Optional reason for closing the ticket
            
        Returns:
            bool: True if ticket was closed successfully
            
        Raises:
            TicketClosingError: If ticket closing fails
            PermissionError: If staff member lacks permission
            TicketNotFoundError: If ticket is not found
        """
        try:
            # Get ticket from database using channel ID
            ticket = await self.get_ticket_by_channel(channel.id)
            if not ticket:
                raise TicketNotFoundError(f"No ticket found for channel {channel.id}")
            
            # Check if ticket is already closed
            if ticket.status != TicketStatus.OPEN:
                raise TicketClosingError(f"Ticket {ticket.ticket_id} is already {ticket.status.value}")
            
            # Verify staff permissions
            guild_config = self.config.get_guild_config(channel.guild.id)
            if not any(role.id in guild_config.staff_roles for role in staff.roles):
                raise PermissionError(f"User {staff.id} is not authorized to close tickets")
            
            # Get ticket lock to prevent race conditions
            lock = await self._get_ticket_lock(ticket.ticket_id)
            async with lock:
                # Send closing notification
                embed = discord.Embed(
                    title="Ticket Closing",
                    description=f"This ticket is being closed by {staff.mention}",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                if reason:
                    embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Ticket ID", value=ticket.ticket_id, inline=True)
                embed.add_field(name="Closed by", value=staff.mention, inline=True)
                embed.set_footer(text="Generating transcript...")
                
                closing_message = await channel.send(embed=embed)
                
                # Generate transcript
                try:
                    transcript_content = await self._generate_transcript(channel)
                    transcript_path = await self._save_transcript(
                        transcript_content, 
                        ticket.ticket_id, 
                        channel.guild.id
                    )
                    
                    # Update database with closed status and transcript
                    success = await self.database.close_ticket(ticket.ticket_id, transcript_path)
                    if not success:
                        raise TicketClosingError(f"Failed to update ticket {ticket.ticket_id} in database")
                    
                    # Update closing message with transcript info
                    embed.set_footer(text="Transcript saved successfully")
                    if transcript_path:
                        embed.add_field(name="Transcript", value=f"Saved to: `{transcript_path}`", inline=False)
                    await closing_message.edit(embed=embed)
                    
                except TranscriptError as e:
                    logger.warning(f"Failed to generate transcript for ticket {ticket.ticket_id}: {e}")
                    # Still close the ticket even if transcript fails
                    success = await self.database.close_ticket(ticket.ticket_id, None)
                    if not success:
                        raise TicketClosingError(f"Failed to update ticket {ticket.ticket_id} in database")
                    
                    embed.set_footer(text="Transcript generation failed")
                    embed.add_field(name="Warning", value="Transcript could not be generated", inline=False)
                    await closing_message.edit(embed=embed)
                
                # Send final notification to participants
                creator = channel.guild.get_member(ticket.creator_id)
                if creator:
                    try:
                        dm_embed = discord.Embed(
                            title="Ticket Closed",
                            description=f"Your ticket `{ticket.ticket_id}` has been closed.",
                            color=discord.Color.blue(),
                            timestamp=datetime.utcnow()
                        )
                        if reason:
                            dm_embed.add_field(name="Reason", value=reason, inline=False)
                        dm_embed.add_field(name="Closed by", value=staff.display_name, inline=True)
                        dm_embed.set_footer(text=f"Server: {channel.guild.name}")
                        
                        await creator.send(embed=dm_embed)
                    except discord.Forbidden:
                        # User has DMs disabled, skip notification
                        pass
                    except Exception as e:
                        logger.warning(f"Failed to send DM notification to user {creator.id}: {e}")
                
                # Log the closure
                logger.info(f"Ticket {ticket.ticket_id} closed by staff {staff.id} in guild {channel.guild.id}")
                
                # Archive or delete the channel
                await self._archive_channel(channel, ticket.ticket_id)
                
                return True
                
        except (PermissionError, TicketClosingError, TicketNotFoundError):
            raise
        except DatabaseError as e:
            raise TicketClosingError(f"Database error closing ticket: {e}")
        except Exception as e:
            logger.error(f"Unexpected error closing ticket: {e}")
            raise TicketClosingError(f"Unexpected error: {e}")
    
    async def force_close_ticket(self, ticket_id: str, staff: discord.Member, 
                                reason: Optional[str] = None) -> bool:
        """
        Force close a ticket by ticket ID (useful when channel is deleted).
        
        Args:
            ticket_id: Unique ticket identifier
            staff: Staff member closing the ticket
            reason: Optional reason for closing the ticket
            
        Returns:
            bool: True if ticket was closed successfully
            
        Raises:
            TicketClosingError: If ticket closing fails
            PermissionError: If staff member lacks permission
            TicketNotFoundError: If ticket is not found
        """
        try:
            # Get ticket from database
            ticket = await self.database.get_ticket(ticket_id)
            if not ticket:
                raise TicketNotFoundError(f"Ticket {ticket_id} not found")
            
            # Check if ticket is already closed
            if ticket.status != TicketStatus.OPEN:
                raise TicketClosingError(f"Ticket {ticket_id} is already {ticket.status.value}")
            
            # Verify staff permissions
            guild = self.bot.get_guild(ticket.guild_id)
            if not guild:
                raise TicketClosingError(f"Guild {ticket.guild_id} not found")
            
            guild_config = self.config.get_guild_config(guild.id)
            if not any(role.id in guild_config.staff_roles for role in staff.roles):
                raise PermissionError(f"User {staff.id} is not authorized to close tickets")
            
            # Get ticket lock to prevent race conditions
            lock = await self._get_ticket_lock(ticket_id)
            async with lock:
                # Close ticket in database (no transcript since channel may be gone)
                success = await self.database.close_ticket(ticket_id, None)
                if not success:
                    raise TicketClosingError(f"Failed to update ticket {ticket_id} in database")
                
                # Send DM notification to creator if possible
                creator = guild.get_member(ticket.creator_id)
                if creator:
                    try:
                        dm_embed = discord.Embed(
                            title="Ticket Closed",
                            description=f"Your ticket `{ticket_id}` has been closed.",
                            color=discord.Color.blue(),
                            timestamp=datetime.utcnow()
                        )
                        if reason:
                            dm_embed.add_field(name="Reason", value=reason, inline=False)
                        dm_embed.add_field(name="Closed by", value=staff.display_name, inline=True)
                        dm_embed.set_footer(text=f"Server: {guild.name}")
                        
                        await creator.send(embed=dm_embed)
                    except discord.Forbidden:
                        # User has DMs disabled, skip notification
                        pass
                    except Exception as e:
                        logger.warning(f"Failed to send DM notification to user {creator.id}: {e}")
                
                logger.info(f"Force closed ticket {ticket_id} by staff {staff.id} in guild {guild.id}")
                return True
                
        except (PermissionError, TicketClosingError, TicketNotFoundError):
            raise
        except DatabaseError as e:
            raise TicketClosingError(f"Database error force closing ticket: {e}")
        except Exception as e:
            logger.error(f"Unexpected error force closing ticket {ticket_id}: {e}")
            raise TicketClosingError(f"Unexpected error: {e}")