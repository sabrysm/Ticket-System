"""
Abstract database adapter interface for the Discord ticket bot.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from models.ticket import Ticket


class DatabaseError(Exception):
    """Base exception for database-related errors."""
    pass


class ConnectionError(DatabaseError):
    """Exception raised when database connection fails."""
    pass


class TicketNotFoundError(DatabaseError):
    """Exception raised when a ticket is not found in the database."""
    pass


class DuplicateTicketError(DatabaseError):
    """Exception raised when attempting to create a duplicate ticket."""
    pass


class DatabaseAdapter(ABC):
    """
    Abstract base class for database adapters.
    
    This interface defines the contract that all database adapters must implement
    to provide ticket CRUD operations and connection management.
    """
    
    def __init__(self, connection_string: str, **kwargs):
        """
        Initialize the database adapter.
        
        Args:
            connection_string: Database connection string
            **kwargs: Additional configuration parameters
        """
        self.connection_string = connection_string
        self.config = kwargs
        self._connection = None
    
    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the database.
        
        Raises:
            ConnectionError: If connection cannot be established
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close the database connection and cleanup resources.
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if the database connection is active.
        
        Returns:
            bool: True if connected, False otherwise
        """
        pass
    
    @abstractmethod
    async def create_ticket(self, ticket: Ticket) -> str:
        """
        Create a new ticket in the database.
        
        Args:
            ticket: Ticket object to create
            
        Returns:
            str: The ticket ID of the created ticket
            
        Raises:
            DuplicateTicketError: If ticket with same ID already exists
            DatabaseError: If creation fails
        """
        pass
    
    @abstractmethod
    async def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """
        Retrieve a ticket by its ID.
        
        Args:
            ticket_id: Unique ticket identifier
            
        Returns:
            Optional[Ticket]: Ticket object if found, None otherwise
            
        Raises:
            DatabaseError: If retrieval fails
        """
        pass
    
    @abstractmethod
    async def get_tickets_by_user(self, user_id: int, guild_id: int) -> List[Ticket]:
        """
        Retrieve all tickets created by a specific user in a guild.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            List[Ticket]: List of tickets created by the user
            
        Raises:
            DatabaseError: If retrieval fails
        """
        pass
    
    @abstractmethod
    async def get_tickets_by_guild(self, guild_id: int, status: Optional[str] = None) -> List[Ticket]:
        """
        Retrieve all tickets for a specific guild, optionally filtered by status.
        
        Args:
            guild_id: Discord guild ID
            status: Optional status filter
            
        Returns:
            List[Ticket]: List of tickets in the guild
            
        Raises:
            DatabaseError: If retrieval fails
        """
        pass
    
    @abstractmethod
    async def update_ticket(self, ticket_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update ticket fields.
        
        Args:
            ticket_id: Unique ticket identifier
            updates: Dictionary of field updates
            
        Returns:
            bool: True if update was successful, False if ticket not found
            
        Raises:
            DatabaseError: If update fails
        """
        pass
    
    @abstractmethod
    async def close_ticket(self, ticket_id: str, transcript_url: Optional[str] = None) -> bool:
        """
        Close a ticket and optionally set transcript URL.
        
        Args:
            ticket_id: Unique ticket identifier
            transcript_url: Optional URL to the ticket transcript
            
        Returns:
            bool: True if ticket was closed, False if ticket not found
            
        Raises:
            DatabaseError: If closing fails
        """
        pass
    
    @abstractmethod
    async def delete_ticket(self, ticket_id: str) -> bool:
        """
        Delete a ticket from the database.
        
        Args:
            ticket_id: Unique ticket identifier
            
        Returns:
            bool: True if ticket was deleted, False if ticket not found
            
        Raises:
            DatabaseError: If deletion fails
        """
        pass
    
    @abstractmethod
    async def add_participant(self, ticket_id: str, user_id: int) -> bool:
        """
        Add a participant to a ticket.
        
        Args:
            ticket_id: Unique ticket identifier
            user_id: Discord user ID to add
            
        Returns:
            bool: True if participant was added, False if ticket not found
            
        Raises:
            DatabaseError: If addition fails
        """
        pass
    
    @abstractmethod
    async def remove_participant(self, ticket_id: str, user_id: int) -> bool:
        """
        Remove a participant from a ticket.
        
        Args:
            ticket_id: Unique ticket identifier
            user_id: Discord user ID to remove
            
        Returns:
            bool: True if participant was removed, False if ticket not found
            
        Raises:
            DatabaseError: If removal fails
        """
        pass
    
    @abstractmethod
    async def get_active_ticket_for_user(self, user_id: int, guild_id: int) -> Optional[Ticket]:
        """
        Get the active (open) ticket for a user in a guild.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            Optional[Ticket]: Active ticket if found, None otherwise
            
        Raises:
            DatabaseError: If retrieval fails
        """
        pass
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()