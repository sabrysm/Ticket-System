"""
Unit tests for the Ticket data model.
"""
import pytest
from datetime import datetime
from models.ticket import Ticket, TicketStatus


class TestTicketModel:
    """Test cases for the Ticket data model."""
    
    def test_ticket_creation(self):
        """Test basic ticket creation."""
        now = datetime.now()
        ticket = Ticket(
            ticket_id="test-123",
            guild_id=12345,
            channel_id=67890,
            creator_id=11111,
            status=TicketStatus.OPEN,
            created_at=now
        )
        
        assert ticket.ticket_id == "test-123"
        assert ticket.guild_id == 12345
        assert ticket.channel_id == 67890
        assert ticket.creator_id == 11111
        assert ticket.status == TicketStatus.OPEN
        assert ticket.created_at == now
        assert ticket.closed_at is None
        assert ticket.transcript_url is None
    
    def test_ticket_default_values(self):
        """Test that default values are set correctly."""
        ticket = Ticket(
            ticket_id="test-123",
            guild_id=12345,
            channel_id=67890,
            creator_id=11111,
            status=TicketStatus.OPEN,
            created_at=datetime.now()
        )
        
        # Default values should be set by __post_init__
        assert ticket.assigned_staff == []
        assert ticket.participants == [11111]  # Creator should be added
    
    def test_ticket_with_explicit_values(self):
        """Test ticket creation with explicit assigned_staff and participants."""
        ticket = Ticket(
            ticket_id="test-123",
            guild_id=12345,
            channel_id=67890,
            creator_id=11111,
            status=TicketStatus.OPEN,
            created_at=datetime.now(),
            assigned_staff=[22222, 33333],
            participants=[11111, 22222, 44444]
        )
        
        assert ticket.assigned_staff == [22222, 33333]
        assert ticket.participants == [11111, 22222, 44444]
    
    def test_ticket_to_dict(self):
        """Test converting ticket to dictionary."""
        now = datetime.now()
        ticket = Ticket(
            ticket_id="test-123",
            guild_id=12345,
            channel_id=67890,
            creator_id=11111,
            status=TicketStatus.OPEN,
            created_at=now,
            assigned_staff=[22222],
            participants=[11111, 22222]
        )
        
        ticket_dict = ticket.to_dict()
        
        expected = {
            'ticket_id': "test-123",
            'guild_id': 12345,
            'channel_id': 67890,
            'creator_id': 11111,
            'status': "open",
            'created_at': now,
            'closed_at': None,
            'assigned_staff': [22222],
            'participants': [11111, 22222],
            'transcript_url': None
        }
        
        assert ticket_dict == expected
    
    def test_ticket_from_dict(self):
        """Test creating ticket from dictionary."""
        now = datetime.now()
        ticket_data = {
            'ticket_id': "test-123",
            'guild_id': 12345,
            'channel_id': 67890,
            'creator_id': 11111,
            'status': "open",
            'created_at': now,
            'closed_at': None,
            'assigned_staff': [22222],
            'participants': [11111, 22222],
            'transcript_url': None
        }
        
        ticket = Ticket.from_dict(ticket_data)
        
        assert ticket.ticket_id == "test-123"
        assert ticket.guild_id == 12345
        assert ticket.channel_id == 67890
        assert ticket.creator_id == 11111
        assert ticket.status == TicketStatus.OPEN
        assert ticket.created_at == now
        assert ticket.closed_at is None
        assert ticket.assigned_staff == [22222]
        assert ticket.participants == [11111, 22222]
        assert ticket.transcript_url is None
    
    def test_ticket_from_dict_minimal(self):
        """Test creating ticket from dictionary with minimal data."""
        now = datetime.now()
        ticket_data = {
            'ticket_id': "test-123",
            'guild_id': 12345,
            'channel_id': 67890,
            'creator_id': 11111,
            'status': "open",
            'created_at': now
        }
        
        ticket = Ticket.from_dict(ticket_data)
        
        assert ticket.ticket_id == "test-123"
        assert ticket.assigned_staff == []
        assert ticket.participants == [11111]  # Creator should be default
    
    def test_ticket_status_enum(self):
        """Test TicketStatus enum values."""
        assert TicketStatus.OPEN.value == "open"
        assert TicketStatus.CLOSED.value == "closed"
        assert TicketStatus.ARCHIVED.value == "archived"
    
    def test_ticket_roundtrip_conversion(self):
        """Test that to_dict and from_dict are inverse operations."""
        now = datetime.now()
        original_ticket = Ticket(
            ticket_id="test-123",
            guild_id=12345,
            channel_id=67890,
            creator_id=11111,
            status=TicketStatus.CLOSED,
            created_at=now,
            closed_at=now,
            assigned_staff=[22222, 33333],
            participants=[11111, 22222, 44444],
            transcript_url="https://example.com/transcript"
        )
        
        # Convert to dict and back
        ticket_dict = original_ticket.to_dict()
        reconstructed_ticket = Ticket.from_dict(ticket_dict)
        
        # Should be identical
        assert reconstructed_ticket.ticket_id == original_ticket.ticket_id
        assert reconstructed_ticket.guild_id == original_ticket.guild_id
        assert reconstructed_ticket.channel_id == original_ticket.channel_id
        assert reconstructed_ticket.creator_id == original_ticket.creator_id
        assert reconstructed_ticket.status == original_ticket.status
        assert reconstructed_ticket.created_at == original_ticket.created_at
        assert reconstructed_ticket.closed_at == original_ticket.closed_at
        assert reconstructed_ticket.assigned_staff == original_ticket.assigned_staff
        assert reconstructed_ticket.participants == original_ticket.participants
        assert reconstructed_ticket.transcript_url == original_ticket.transcript_url