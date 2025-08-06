"""
Unit tests for the TicketManager class.
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import List, Optional

import discord
from discord.ext import commands

from core.ticket_manager import (
    TicketManager, TicketManagerError, TicketCreationError, 
    UserManagementError, PermissionError
)
from models.ticket import Ticket, TicketStatus
from database.adapter import DatabaseAdapter, TicketNotFoundError, DatabaseError
from config.config_manager import ConfigManager, GuildConfig


class MockDatabaseAdapter(DatabaseAdapter):
    """Mock database adapter for testing."""
    
    def __init__(self):
        super().__init__("mock://test")
        self.tickets = {}
        self.connected = True
    
    async def connect(self):
        self.connected = True
    
    async def disconnect(self):
        self.connected = False
    
    async def is_connected(self):
        return self.connected
    
    async def create_ticket(self, ticket: Ticket) -> str:
        if ticket.ticket_id in self.tickets:
            raise DatabaseError(f"Ticket {ticket.ticket_id} already exists")
        self.tickets[ticket.ticket_id] = ticket
        return ticket.ticket_id
    
    async def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        return self.tickets.get(ticket_id)
    
    async def get_tickets_by_user(self, user_id: int, guild_id: int) -> List[Ticket]:
        return [t for t in self.tickets.values() 
                if t.creator_id == user_id and t.guild_id == guild_id]
    
    async def get_tickets_by_guild(self, guild_id: int, status: Optional[str] = None) -> List[Ticket]:
        tickets = [t for t in self.tickets.values() if t.guild_id == guild_id]
        if status:
            tickets = [t for t in tickets if t.status.value == status]
        return tickets
    
    async def update_ticket(self, ticket_id: str, updates: dict) -> bool:
        if ticket_id not in self.tickets:
            return False
        ticket = self.tickets[ticket_id]
        for key, value in updates.items():
            setattr(ticket, key, value)
        return True
    
    async def close_ticket(self, ticket_id: str, transcript_url: Optional[str] = None) -> bool:
        if ticket_id not in self.tickets:
            return False
        ticket = self.tickets[ticket_id]
        ticket.status = TicketStatus.CLOSED
        ticket.closed_at = datetime.utcnow()
        if transcript_url:
            ticket.transcript_url = transcript_url
        return True
    
    async def delete_ticket(self, ticket_id: str) -> bool:
        if ticket_id not in self.tickets:
            return False
        del self.tickets[ticket_id]
        return True
    
    async def add_participant(self, ticket_id: str, user_id: int) -> bool:
        if ticket_id not in self.tickets:
            return False
        ticket = self.tickets[ticket_id]
        if user_id not in ticket.participants:
            ticket.participants.append(user_id)
        return True
    
    async def remove_participant(self, ticket_id: str, user_id: int) -> bool:
        if ticket_id not in self.tickets:
            return False
        ticket = self.tickets[ticket_id]
        if user_id in ticket.participants:
            ticket.participants.remove(user_id)
        return True
    
    async def get_active_ticket_for_user(self, user_id: int, guild_id: int) -> Optional[Ticket]:
        for ticket in self.tickets.values():
            if (ticket.creator_id == user_id and 
                ticket.guild_id == guild_id and 
                ticket.status == TicketStatus.OPEN):
                return ticket
        return None


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = MagicMock(spec=commands.Bot)
    bot.get_channel = MagicMock()
    return bot


@pytest.fixture
def mock_database():
    """Create a mock database adapter."""
    return MockDatabaseAdapter()


@pytest.fixture
def mock_config():
    """Create a mock configuration manager."""
    config = MagicMock(spec=ConfigManager)
    guild_config = GuildConfig(
        guild_id=12345,
        staff_roles=[67890, 11111],
        ticket_category=22222,
        log_channel=33333
    )
    config.get_guild_config.return_value = guild_config
    return config


@pytest.fixture
def ticket_manager(mock_bot, mock_database, mock_config):
    """Create a TicketManager instance for testing."""
    return TicketManager(mock_bot, mock_database, mock_config)


@pytest.fixture
def mock_guild():
    """Create a mock Discord guild."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 12345
    guild.default_role = MagicMock()
    guild.me = MagicMock()
    guild.get_role.return_value = MagicMock()
    guild.get_channel.return_value = MagicMock(spec=discord.CategoryChannel)
    guild.create_text_channel = AsyncMock()
    return guild


@pytest.fixture
def mock_user():
    """Create a mock Discord member."""
    user = MagicMock(spec=discord.Member)
    user.id = 54321
    user.display_name = "TestUser"
    user.mention = "<@54321>"
    user.roles = []
    return user


@pytest.fixture
def mock_staff():
    """Create a mock staff Discord member."""
    staff = MagicMock(spec=discord.Member)
    staff.id = 98765
    staff.display_name = "StaffUser"
    staff.mention = "<@98765>"
    # Create mock roles with staff role ID
    role = MagicMock()
    role.id = 67890
    staff.roles = [role]
    return staff


@pytest.fixture
def mock_channel():
    """Create a mock Discord text channel."""
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 44444
    channel.guild = MagicMock()
    channel.guild.id = 12345
    channel.send = AsyncMock()
    channel.set_permissions = AsyncMock()
    return channel


class TestTicketManager:
    """Test cases for TicketManager class."""
    
    def test_init(self, mock_bot, mock_database, mock_config):
        """Test TicketManager initialization."""
        manager = TicketManager(mock_bot, mock_database, mock_config)
        
        assert manager.bot == mock_bot
        assert manager.database == mock_database
        assert manager.config == mock_config
        assert isinstance(manager._ticket_locks, dict)
    
    def test_generate_ticket_id(self, ticket_manager):
        """Test ticket ID generation."""
        ticket_id = ticket_manager._generate_ticket_id()
        
        assert isinstance(ticket_id, str)
        assert len(ticket_id) == 8
        assert ticket_id.isalnum()
        assert ticket_id.isupper()
    
    def test_generate_unique_ticket_ids(self, ticket_manager):
        """Test that generated ticket IDs are unique."""
        ids = set()
        for _ in range(100):
            ticket_id = ticket_manager._generate_ticket_id()
            assert ticket_id not in ids
            ids.add(ticket_id)
    
    @pytest.mark.asyncio
    async def test_get_ticket_lock(self, ticket_manager):
        """Test ticket lock creation and retrieval."""
        ticket_id = "TEST1234"
        
        # First call should create a new lock
        lock1 = await ticket_manager._get_ticket_lock(ticket_id)
        assert isinstance(lock1, asyncio.Lock)
        
        # Second call should return the same lock
        lock2 = await ticket_manager._get_ticket_lock(ticket_id)
        assert lock1 is lock2
    
    @pytest.mark.asyncio
    async def test_create_ticket_channel_success(self, ticket_manager, mock_guild, mock_user):
        """Test successful ticket channel creation."""
        ticket_id = "TEST1234"
        guild_config = GuildConfig(guild_id=12345, staff_roles=[67890], ticket_category=22222)
        
        # Mock channel creation
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.id = 44444
        mock_guild.create_text_channel.return_value = mock_channel
        
        channel = await ticket_manager._create_ticket_channel(
            mock_guild, ticket_id, mock_user, guild_config
        )
        
        assert channel == mock_channel
        mock_guild.create_text_channel.assert_called_once()
        
        # Verify call arguments
        call_args = mock_guild.create_text_channel.call_args
        assert call_args[1]['name'] == 'ticket-test1234'
        assert 'overwrites' in call_args[1]
        assert call_args[1]['topic'] == f"Support ticket {ticket_id} - Created by {mock_user.display_name}"
    
    @pytest.mark.asyncio
    async def test_create_ticket_channel_forbidden(self, ticket_manager, mock_guild, mock_user):
        """Test ticket channel creation with insufficient permissions."""
        ticket_id = "TEST1234"
        guild_config = GuildConfig(guild_id=12345)
        
        # Mock permission error
        mock_guild.create_text_channel.side_effect = discord.Forbidden(
            MagicMock(), "Insufficient permissions"
        )
        
        with pytest.raises(TicketCreationError, match="Bot lacks permission to create channels"):
            await ticket_manager._create_ticket_channel(
                mock_guild, ticket_id, mock_user, guild_config
            )
    
    @pytest.mark.asyncio
    async def test_create_ticket_success(self, ticket_manager, mock_guild, mock_user):
        """Test successful ticket creation."""
        # Mock no existing ticket
        ticket_manager.database.get_active_ticket_for_user = AsyncMock(return_value=None)
        ticket_manager.database.get_ticket = AsyncMock(return_value=None)
        ticket_manager.database.create_ticket = AsyncMock()
        
        # Mock channel creation
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.id = 44444
        mock_channel.send = AsyncMock()
        
        with patch.object(ticket_manager, '_create_ticket_channel', return_value=mock_channel):
            ticket = await ticket_manager.create_ticket(mock_user, mock_guild)
        
        assert isinstance(ticket, Ticket)
        assert ticket.guild_id == mock_guild.id
        assert ticket.channel_id == mock_channel.id
        assert ticket.creator_id == mock_user.id
        assert ticket.status == TicketStatus.OPEN
        assert mock_user.id in ticket.participants
        
        # Verify database calls
        ticket_manager.database.get_active_ticket_for_user.assert_called_once_with(
            mock_user.id, mock_guild.id
        )
        ticket_manager.database.create_ticket.assert_called_once()
        
        # Verify welcome message sent
        mock_channel.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_ticket_user_has_active_ticket(self, ticket_manager, mock_guild, mock_user):
        """Test ticket creation when user already has an active ticket."""
        # Mock existing active ticket
        existing_ticket = Ticket(
            ticket_id="EXISTING1",
            guild_id=mock_guild.id,
            channel_id=11111,
            creator_id=mock_user.id,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow()
        )
        ticket_manager.database.get_active_ticket_for_user = AsyncMock(return_value=existing_ticket)
        
        with pytest.raises(PermissionError, match="already has an active ticket"):
            await ticket_manager.create_ticket(mock_user, mock_guild)
    
    @pytest.mark.asyncio
    async def test_add_user_to_ticket_success(self, ticket_manager, mock_channel, mock_user, mock_staff):
        """Test successfully adding a user to a ticket."""
        # Create test ticket
        ticket = Ticket(
            ticket_id="TEST1234",
            guild_id=12345,
            channel_id=mock_channel.id,
            creator_id=99999,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow(),
            participants=[99999]
        )
        
        # Mock database responses
        ticket_manager.database.get_tickets_by_guild = AsyncMock(return_value=[ticket])
        ticket_manager.database.add_participant = AsyncMock(return_value=True)
        
        result = await ticket_manager.add_user_to_ticket(mock_channel, mock_user, mock_staff)
        
        assert result is True
        mock_channel.set_permissions.assert_called_once_with(
            mock_user,
            read_messages=True,
            send_messages=True,
            read_message_history=True,
            reason=f"Added to ticket {ticket.ticket_id} by {mock_staff}"
        )
        ticket_manager.database.add_participant.assert_called_once_with(ticket.ticket_id, mock_user.id)
        mock_channel.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_user_to_ticket_not_found(self, ticket_manager, mock_channel, mock_user, mock_staff):
        """Test adding user to non-existent ticket."""
        # Mock no tickets found
        ticket_manager.database.get_tickets_by_guild = AsyncMock(return_value=[])
        
        with pytest.raises(TicketNotFoundError):
            await ticket_manager.add_user_to_ticket(mock_channel, mock_user, mock_staff)
    
    @pytest.mark.asyncio
    async def test_add_user_to_ticket_not_staff(self, ticket_manager, mock_channel, mock_user):
        """Test adding user to ticket without staff permissions."""
        # Create non-staff user
        non_staff = MagicMock(spec=discord.Member)
        non_staff.id = 11111
        non_staff.roles = []  # No staff roles
        
        # Create test ticket
        ticket = Ticket(
            ticket_id="TEST1234",
            guild_id=12345,
            channel_id=mock_channel.id,
            creator_id=99999,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow()
        )
        
        ticket_manager.database.get_tickets_by_guild = AsyncMock(return_value=[ticket])
        
        with pytest.raises(PermissionError, match="not authorized to manage tickets"):
            await ticket_manager.add_user_to_ticket(mock_channel, mock_user, non_staff)
    
    @pytest.mark.asyncio
    async def test_add_user_already_in_ticket(self, ticket_manager, mock_channel, mock_user, mock_staff):
        """Test adding user who is already in the ticket."""
        # Create test ticket with user already as participant
        ticket = Ticket(
            ticket_id="TEST1234",
            guild_id=12345,
            channel_id=mock_channel.id,
            creator_id=99999,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow(),
            participants=[99999, mock_user.id]  # User already in ticket
        )
        
        ticket_manager.database.get_tickets_by_guild = AsyncMock(return_value=[ticket])
        
        with pytest.raises(UserManagementError, match="already in ticket"):
            await ticket_manager.add_user_to_ticket(mock_channel, mock_user, mock_staff)
    
    @pytest.mark.asyncio
    async def test_remove_user_from_ticket_success(self, ticket_manager, mock_channel, mock_user, mock_staff):
        """Test successfully removing a user from a ticket."""
        # Create test ticket with user as participant
        ticket = Ticket(
            ticket_id="TEST1234",
            guild_id=12345,
            channel_id=mock_channel.id,
            creator_id=99999,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow(),
            participants=[99999, mock_user.id]
        )
        
        # Mock database responses
        ticket_manager.database.get_tickets_by_guild = AsyncMock(return_value=[ticket])
        ticket_manager.database.remove_participant = AsyncMock(return_value=True)
        
        result = await ticket_manager.remove_user_from_ticket(mock_channel, mock_user, mock_staff)
        
        assert result is True
        mock_channel.set_permissions.assert_called_once_with(
            mock_user,
            overwrite=None,
            reason=f"Removed from ticket {ticket.ticket_id} by {mock_staff}"
        )
        ticket_manager.database.remove_participant.assert_called_once_with(ticket.ticket_id, mock_user.id)
        mock_channel.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_remove_ticket_creator(self, ticket_manager, mock_channel, mock_user, mock_staff):
        """Test attempting to remove the ticket creator."""
        # Create test ticket with user as creator
        ticket = Ticket(
            ticket_id="TEST1234",
            guild_id=12345,
            channel_id=mock_channel.id,
            creator_id=mock_user.id,  # User is the creator
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow(),
            participants=[mock_user.id]
        )
        
        ticket_manager.database.get_tickets_by_guild = AsyncMock(return_value=[ticket])
        
        with pytest.raises(PermissionError, match="Cannot remove ticket creator"):
            await ticket_manager.remove_user_from_ticket(mock_channel, mock_user, mock_staff)
    
    @pytest.mark.asyncio
    async def test_remove_user_not_in_ticket(self, ticket_manager, mock_channel, mock_user, mock_staff):
        """Test removing user who is not in the ticket."""
        # Create test ticket without user as participant
        ticket = Ticket(
            ticket_id="TEST1234",
            guild_id=12345,
            channel_id=mock_channel.id,
            creator_id=99999,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow(),
            participants=[99999]  # User not in participants
        )
        
        ticket_manager.database.get_tickets_by_guild = AsyncMock(return_value=[ticket])
        
        with pytest.raises(UserManagementError, match="not in ticket"):
            await ticket_manager.remove_user_from_ticket(mock_channel, mock_user, mock_staff)
    
    @pytest.mark.asyncio
    async def test_get_ticket_by_channel_success(self, ticket_manager, mock_bot):
        """Test getting ticket by channel ID."""
        channel_id = 44444
        guild_id = 12345
        
        # Mock channel
        mock_channel = MagicMock()
        mock_channel.guild.id = guild_id
        mock_bot.get_channel.return_value = mock_channel
        
        # Create test ticket
        ticket = Ticket(
            ticket_id="TEST1234",
            guild_id=guild_id,
            channel_id=channel_id,
            creator_id=54321,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow()
        )
        
        ticket_manager.database.get_tickets_by_guild = AsyncMock(return_value=[ticket])
        
        result = await ticket_manager.get_ticket_by_channel(channel_id)
        
        assert result == ticket
        mock_bot.get_channel.assert_called_once_with(channel_id)
        ticket_manager.database.get_tickets_by_guild.assert_called_once_with(guild_id)
    
    @pytest.mark.asyncio
    async def test_get_ticket_by_channel_not_found(self, ticket_manager, mock_bot):
        """Test getting ticket by channel ID when channel doesn't exist."""
        channel_id = 44444
        mock_bot.get_channel.return_value = None
        
        result = await ticket_manager.get_ticket_by_channel(channel_id)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_is_user_staff_true(self, ticket_manager, mock_staff):
        """Test checking if user is staff (positive case)."""
        mock_staff.guild.id = 12345
        
        result = await ticket_manager.is_user_staff(mock_staff)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_is_user_staff_false(self, ticket_manager, mock_user):
        """Test checking if user is staff (negative case)."""
        mock_user.guild.id = 12345
        
        result = await ticket_manager.is_user_staff(mock_user)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_user_active_ticket_success(self, ticket_manager):
        """Test getting user's active ticket."""
        user_id = 54321
        guild_id = 12345
        
        ticket = Ticket(
            ticket_id="TEST1234",
            guild_id=guild_id,
            channel_id=44444,
            creator_id=user_id,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow()
        )
        
        ticket_manager.database.get_active_ticket_for_user = AsyncMock(return_value=ticket)
        
        result = await ticket_manager.get_user_active_ticket(user_id, guild_id)
        
        assert result == ticket
        ticket_manager.database.get_active_ticket_for_user.assert_called_once_with(user_id, guild_id)
    
    @pytest.mark.asyncio
    async def test_get_user_active_ticket_none(self, ticket_manager):
        """Test getting user's active ticket when none exists."""
        user_id = 54321
        guild_id = 12345
        
        ticket_manager.database.get_active_ticket_for_user = AsyncMock(return_value=None)
        
        result = await ticket_manager.get_user_active_ticket(user_id, guild_id)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self, ticket_manager, mock_channel, mock_user, mock_staff):
        """Test handling of database errors."""
        # Mock database error
        ticket_manager.database.get_tickets_by_guild = AsyncMock(
            side_effect=DatabaseError("Database connection failed")
        )
        
        with pytest.raises(UserManagementError, match="Database error"):
            await ticket_manager.add_user_to_ticket(mock_channel, mock_user, mock_staff)
    
    @pytest.mark.asyncio
    async def test_discord_api_error_handling(self, ticket_manager, mock_channel, mock_user, mock_staff):
        """Test handling of Discord API errors."""
        # Create test ticket
        ticket = Ticket(
            ticket_id="TEST1234",
            guild_id=12345,
            channel_id=mock_channel.id,
            creator_id=99999,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow(),
            participants=[99999]
        )
        
        ticket_manager.database.get_tickets_by_guild = AsyncMock(return_value=[ticket])
        
        # Mock Discord API error
        mock_channel.set_permissions.side_effect = discord.HTTPException(
            MagicMock(), "API Error"
        )
        
        with pytest.raises(UserManagementError, match="Discord API error"):
            await ticket_manager.add_user_to_ticket(mock_channel, mock_user, mock_staff)


if __name__ == "__main__":
    pytest.main([__file__])