"""
Ticket data model for the Discord ticket bot.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class TicketStatus(Enum):
    """Enumeration for ticket status values."""
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


@dataclass
class Ticket:
    """
    Data model representing a support ticket.
    
    Attributes:
        ticket_id: Unique identifier for the ticket
        guild_id: Discord guild (server) ID where ticket was created
        channel_id: Discord channel ID for the ticket
        creator_id: Discord user ID of the ticket creator
        status: Current status of the ticket
        created_at: Timestamp when ticket was created
        closed_at: Timestamp when ticket was closed (None if still open)
        assigned_staff: List of Discord user IDs of assigned staff members
        participants: List of Discord user IDs of all ticket participants
        transcript_url: URL to saved transcript (None if not saved)
    """
    ticket_id: str
    guild_id: int
    channel_id: int
    creator_id: int
    status: TicketStatus
    created_at: datetime
    closed_at: Optional[datetime] = None
    assigned_staff: List[int] = None
    participants: List[int] = None
    transcript_url: Optional[str] = None
    
    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.assigned_staff is None:
            self.assigned_staff = []
        if self.participants is None:
            self.participants = [self.creator_id]
    
    def to_dict(self) -> dict:
        """Convert ticket to dictionary representation."""
        return {
            'ticket_id': self.ticket_id,
            'guild_id': self.guild_id,
            'channel_id': self.channel_id,
            'creator_id': self.creator_id,
            'status': self.status.value,
            'created_at': self.created_at,
            'closed_at': self.closed_at,
            'assigned_staff': self.assigned_staff,
            'participants': self.participants,
            'transcript_url': self.transcript_url
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Ticket':
        """Create ticket instance from dictionary representation."""
        return cls(
            ticket_id=data['ticket_id'],
            guild_id=data['guild_id'],
            channel_id=data['channel_id'],
            creator_id=data['creator_id'],
            status=TicketStatus(data['status']),
            created_at=data['created_at'],
            closed_at=data.get('closed_at'),
            assigned_staff=data.get('assigned_staff', []),
            participants=data.get('participants', [data['creator_id']]),
            transcript_url=data.get('transcript_url')
        )