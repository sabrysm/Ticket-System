"""
Unit tests for the DatabaseAdapter abstract interface.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from typing import List, Optional, Dict, Any

from database.adapter import (
    DatabaseAdapter,
    DatabaseError,
    ConnectionError,
    TicketNotFoundError,
    DuplicateTicketError
)
from models.ticket import Ticket, TicketStatus


class MockDatabaseAdapter(DatabaseAdapter):
    """Mock implementation of DatabaseAdapter for testing."""
    
    def __init__(self, connection_string: str, **kwargs):
        super().__init__(connection_string, **kwargs)
        self._tickets = {}
        self._connected = False
    
    async def connect(self) -> None:
        """Mock connect implementation."""
        if "fail_connect" in self.config:
            raise ConnectionError("Mock connection failure")
        self._connected = True
    
    async def disconnect(self) -> None:
        """Mock disconnect implementation."""
        self._connected = False
    
    async def is_connected(self) -> bool:
        """Mock connection check."""
        return self._connected
    
    async def create_ticket(self, ticket: Ticket) -> str:
        """Mock create ticket implementation."""
        if ticket.ticket_id in self._tickets:
            raise DuplicateTicketError(f"Ticket {ticket.ticket_id} already exists")
        self._tickets[ticket.ticket_id] = ticket
        return ticket.ticket_id
    
    async def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Mock get ticket implementation."""
        return self._tickets.get(ticket_id)
    
    async def get_tickets_by_user(self, user_id: int, guild_id: int) -> List[Ticket]:
        """Mock get tickets by user implementation."""
        return [
            ticket for ticket in self._tickets.values()
            if ticket.creator_id == user_id and ticket.guild_id == guild_id
        ]
    
    async def get_tickets_by_guild(self, guild_id: int, status: Optional[str] = None) -> List[Ticket]:
        """Mock get tickets by guild implementation."""
        tickets = [
            ticket for ticket in self._tickets.values()
            if ticket.guild_id == guild_id
        ]
        if status:
            tickets = [t for t in tickets if t.status.value == status]
        return tickets
    
    async def update_ticket(self, ticket_id: str, updates: Dict[str, Any]) -> bool:
        """Mock update ticket implementation."""
        if ticket_id not in self._tickets:
            return False
        
        ticket = self._tickets[ticket_id]
        for key, value in updates.items():
            if hasattr(ticket, key):
                setattr(ticket, key, value)
        return True
    
    async def close_ticket(self, ticket_id: str, transcript_url: Optional[str] = None) -> bool:
        """Mock close ticket implementation."""
        if ticket_id not in self._tickets:
            return False
        
        ticket = self._tickets[ticket_id]
        ticket.status = TicketStatus.CLOSED
        ticket.closed_at = datetime.now()
        if transcript_url:
            ticket.transcript_url = transcript_url
        return True
    
    async def delete_ticket(self, ticket_id: str) -> bool:
        """Mock delete ticket implementation."""
        if ticket_id not in self._tickets:
            return False
        del self._tickets[ticket_id]
        return True
    
    async def add_participant(self, ticket_id: str, user_id: int) -> bool:
        """Mock add participant implementation."""
        if ticket_id not in self._tickets:
            return False
        
        ticket = self._tickets[ticket_id]
        if user_id not in ticket.participants:
            ticket.participants.append(user_id)
        return True
    
    async def remove_participant(self, ticket_id: str, user_id: int) -> bool:
        """Mock remove participant implementation."""
        if ticket_id not in self._tickets:
            return False
        
        ticket = self._tickets[ticket_id]
        if user_id in ticket.participants:
            ticket.participants.remove(user_id)
        return True
    
    async def get_active_ticket_for_user(self, user_id: int, guild_id: int) -> Optional[Ticket]:
        """Mock get active ticket for user implementation."""
        for ticket in self._tickets.values():
            if (ticket.creator_id == user_id and 
                ticket.guild_id == guild_id and 
                ticket.status == TicketStatus.OPEN):
                return ticket
        return None


@pytest.fixture
def sample_ticket():
    """Create a sample ticket for testing."""
    return Ticket(
        ticket_id="test-123",
        guild_id=12345,
        channel_id=67890,
        creator_id=11111,
        status=TicketStatus.OPEN,
        created_at=datetime.now(),
        assigned_staff=[22222],
        participants=[11111, 22222]
    )


@pytest.fixture
def mock_adapter():
    """Create a mock database adapter for testing."""
    return MockDatabaseAdapter("mock://connection")


class TestDatabaseAdapter:
    """Test cases for DatabaseAdapter interface."""
    
    @pytest.mark.asyncio
    async def test_adapter_initialization(self):
        """Test adapter initialization with connection string and config."""
        adapter = MockDatabaseAdapter("test://connection", pool_size=10)
        assert adapter.connection_string == "test://connection"
        assert adapter.config["pool_size"] == 10
    
    @pytest.mark.asyncio
    async def test_connection_management(self, mock_adapter):
        """Test connection and disconnection."""
        # Initially not connected
        assert not await mock_adapter.is_connected()
        
        # Connect
        await mock_adapter.connect()
        assert await mock_adapter.is_connected()
        
        # Disconnect
        await mock_adapter.disconnect()
        assert not await mock_adapter.is_connected()
    
    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test connection failure handling."""
        adapter = MockDatabaseAdapter("test://connection", fail_connect=True)
        
        with pytest.raises(ConnectionError):
            await adapter.connect()
    
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_adapter):
        """Test async context manager functionality."""
        async with mock_adapter as adapter:
            assert await adapter.is_connected()
        
        # Should be disconnected after context exit
        assert not await mock_adapter.is_connected()
    
    @pytest.mark.asyncio
    async def test_create_ticket(self, mock_adapter, sample_ticket):
        """Test ticket creation."""
        await mock_adapter.connect()
        
        ticket_id = await mock_adapter.create_ticket(sample_ticket)
        assert ticket_id == sample_ticket.ticket_id
        
        # Verify ticket was stored
        retrieved = await mock_adapter.get_ticket(ticket_id)
        assert retrieved is not None
        assert retrieved.ticket_id == sample_ticket.ticket_id
    
    @pytest.mark.asyncio
    async def test_create_duplicate_ticket(self, mock_adapter, sample_ticket):
        """Test duplicate ticket creation raises error."""
        await mock_adapter.connect()
        
        # Create first ticket
        await mock_adapter.create_ticket(sample_ticket)
        
        # Attempt to create duplicate
        with pytest.raises(DuplicateTicketError):
            await mock_adapter.create_ticket(sample_ticket)
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_ticket(self, mock_adapter):
        """Test getting a ticket that doesn't exist."""
        await mock_adapter.connect()
        
        ticket = await mock_adapter.get_ticket("nonexistent")
        assert ticket is None
    
    @pytest.mark.asyncio
    async def test_get_tickets_by_user(self, mock_adapter):
        """Test retrieving tickets by user."""
        await mock_adapter.connect()
        
        # Create tickets for different users
        ticket1 = Ticket("t1", 123, 456, 111, TicketStatus.OPEN, datetime.now())
        ticket2 = Ticket("t2", 123, 457, 222, TicketStatus.OPEN, datetime.now())
        ticket3 = Ticket("t3", 123, 458, 111, TicketStatus.CLOSED, datetime.now())
        
        await mock_adapter.create_ticket(ticket1)
        await mock_adapter.create_ticket(ticket2)
        await mock_adapter.create_ticket(ticket3)
        
        # Get tickets for user 111
        user_tickets = await mock_adapter.get_tickets_by_user(111, 123)
        assert len(user_tickets) == 2
        assert all(t.creator_id == 111 for t in user_tickets)
    
    @pytest.mark.asyncio
    async def test_get_tickets_by_guild(self, mock_adapter):
        """Test retrieving tickets by guild."""
        await mock_adapter.connect()
        
        # Create tickets in different guilds
        ticket1 = Ticket("t1", 123, 456, 111, TicketStatus.OPEN, datetime.now())
        ticket2 = Ticket("t2", 456, 457, 222, TicketStatus.OPEN, datetime.now())
        ticket3 = Ticket("t3", 123, 458, 333, TicketStatus.CLOSED, datetime.now())
        
        await mock_adapter.create_ticket(ticket1)
        await mock_adapter.create_ticket(ticket2)
        await mock_adapter.create_ticket(ticket3)
        
        # Get all tickets for guild 123
        guild_tickets = await mock_adapter.get_tickets_by_guild(123)
        assert len(guild_tickets) == 2
        assert all(t.guild_id == 123 for t in guild_tickets)
        
        # Get only open tickets for guild 123
        open_tickets = await mock_adapter.get_tickets_by_guild(123, "open")
        assert len(open_tickets) == 1
        assert open_tickets[0].status == TicketStatus.OPEN
    
    @pytest.mark.asyncio
    async def test_update_ticket(self, mock_adapter, sample_ticket):
        """Test ticket updates."""
        await mock_adapter.connect()
        await mock_adapter.create_ticket(sample_ticket)
        
        # Update ticket
        updates = {"status": TicketStatus.CLOSED}
        result = await mock_adapter.update_ticket(sample_ticket.ticket_id, updates)
        assert result is True
        
        # Verify update
        updated_ticket = await mock_adapter.get_ticket(sample_ticket.ticket_id)
        assert updated_ticket.status == TicketStatus.CLOSED
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_ticket(self, mock_adapter):
        """Test updating a ticket that doesn't exist."""
        await mock_adapter.connect()
        
        result = await mock_adapter.update_ticket("nonexistent", {"status": TicketStatus.CLOSED})
        assert result is False
    
    @pytest.mark.asyncio
    async def test_close_ticket(self, mock_adapter, sample_ticket):
        """Test closing a ticket."""
        await mock_adapter.connect()
        await mock_adapter.create_ticket(sample_ticket)
        
        transcript_url = "https://example.com/transcript"
        result = await mock_adapter.close_ticket(sample_ticket.ticket_id, transcript_url)
        assert result is True
        
        # Verify ticket was closed
        closed_ticket = await mock_adapter.get_ticket(sample_ticket.ticket_id)
        assert closed_ticket.status == TicketStatus.CLOSED
        assert closed_ticket.transcript_url == transcript_url
        assert closed_ticket.closed_at is not None
    
    @pytest.mark.asyncio
    async def test_close_nonexistent_ticket(self, mock_adapter):
        """Test closing a ticket that doesn't exist."""
        await mock_adapter.connect()
        
        result = await mock_adapter.close_ticket("nonexistent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_ticket(self, mock_adapter, sample_ticket):
        """Test deleting a ticket."""
        await mock_adapter.connect()
        await mock_adapter.create_ticket(sample_ticket)
        
        # Verify ticket exists
        assert await mock_adapter.get_ticket(sample_ticket.ticket_id) is not None
        
        # Delete ticket
        result = await mock_adapter.delete_ticket(sample_ticket.ticket_id)
        assert result is True
        
        # Verify ticket is gone
        assert await mock_adapter.get_ticket(sample_ticket.ticket_id) is None
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_ticket(self, mock_adapter):
        """Test deleting a ticket that doesn't exist."""
        await mock_adapter.connect()
        
        result = await mock_adapter.delete_ticket("nonexistent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_add_participant(self, mock_adapter, sample_ticket):
        """Test adding a participant to a ticket."""
        await mock_adapter.connect()
        await mock_adapter.create_ticket(sample_ticket)
        
        new_user_id = 33333
        result = await mock_adapter.add_participant(sample_ticket.ticket_id, new_user_id)
        assert result is True
        
        # Verify participant was added
        updated_ticket = await mock_adapter.get_ticket(sample_ticket.ticket_id)
        assert new_user_id in updated_ticket.participants
    
    @pytest.mark.asyncio
    async def test_add_participant_to_nonexistent_ticket(self, mock_adapter):
        """Test adding participant to a ticket that doesn't exist."""
        await mock_adapter.connect()
        
        result = await mock_adapter.add_participant("nonexistent", 12345)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_remove_participant(self, mock_adapter, sample_ticket):
        """Test removing a participant from a ticket."""
        await mock_adapter.connect()
        await mock_adapter.create_ticket(sample_ticket)
        
        # Remove existing participant
        user_to_remove = sample_ticket.participants[0]
        result = await mock_adapter.remove_participant(sample_ticket.ticket_id, user_to_remove)
        assert result is True
        
        # Verify participant was removed
        updated_ticket = await mock_adapter.get_ticket(sample_ticket.ticket_id)
        assert user_to_remove not in updated_ticket.participants
    
    @pytest.mark.asyncio
    async def test_remove_participant_from_nonexistent_ticket(self, mock_adapter):
        """Test removing participant from a ticket that doesn't exist."""
        await mock_adapter.connect()
        
        result = await mock_adapter.remove_participant("nonexistent", 12345)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_active_ticket_for_user(self, mock_adapter):
        """Test getting active ticket for a user."""
        await mock_adapter.connect()
        
        # Create open and closed tickets for same user
        open_ticket = Ticket("open", 123, 456, 111, TicketStatus.OPEN, datetime.now())
        closed_ticket = Ticket("closed", 123, 457, 111, TicketStatus.CLOSED, datetime.now())
        
        await mock_adapter.create_ticket(open_ticket)
        await mock_adapter.create_ticket(closed_ticket)
        
        # Should return only the open ticket
        active_ticket = await mock_adapter.get_active_ticket_for_user(111, 123)
        assert active_ticket is not None
        assert active_ticket.ticket_id == "open"
        assert active_ticket.status == TicketStatus.OPEN
    
    @pytest.mark.asyncio
    async def test_get_active_ticket_for_user_none_found(self, mock_adapter):
        """Test getting active ticket when none exists."""
        await mock_adapter.connect()
        
        active_ticket = await mock_adapter.get_active_ticket_for_user(999, 123)
        assert active_ticket is None


class TestDatabaseExceptions:
    """Test database exception classes."""
    
    def test_database_error_inheritance(self):
        """Test that all database errors inherit from DatabaseError."""
        assert issubclass(ConnectionError, DatabaseError)
        assert issubclass(TicketNotFoundError, DatabaseError)
        assert issubclass(DuplicateTicketError, DatabaseError)
    
    def test_exception_messages(self):
        """Test exception message handling."""
        msg = "Test error message"
        
        db_error = DatabaseError(msg)
        assert str(db_error) == msg
        
        conn_error = ConnectionError(msg)
        assert str(conn_error) == msg
        
        not_found_error = TicketNotFoundError(msg)
        assert str(not_found_error) == msg
        
        duplicate_error = DuplicateTicketError(msg)
        assert str(duplicate_error) == msg