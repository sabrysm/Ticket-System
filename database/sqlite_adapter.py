"""
SQLite database adapter implementation for the Discord ticket bot.
"""
import aiosqlite
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from database.adapter import DatabaseAdapter, DatabaseError, ConnectionError, TicketNotFoundError, DuplicateTicketError
from models.ticket import Ticket, TicketStatus


logger = logging.getLogger(__name__)


class SQLiteAdapter(DatabaseAdapter):
    """
    SQLite implementation of the DatabaseAdapter interface.
    
    Provides ticket CRUD operations using SQLite database with connection pooling
    and proper error handling.
    """
    
    def __init__(self, connection_string: str, **kwargs):
        """
        Initialize SQLite adapter.
        
        Args:
            connection_string: Path to SQLite database file
            **kwargs: Additional configuration (pool_size, timeout, etc.)
        """
        super().__init__(connection_string, **kwargs)
        self.db_path = connection_string
        self.pool_size = kwargs.get('pool_size', 5)
        self.timeout = kwargs.get('timeout', 30.0)
        self._connection_pool = []
        self._schema_initialized = False
    
    async def connect(self) -> None:
        """
        Establish connection pool to SQLite database.
        
        Raises:
            ConnectionError: If connection cannot be established
        """
        try:
            # Ensure database directory exists
            db_path = Path(self.db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Test connection
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as conn:
                await conn.execute("SELECT 1")
            
            # Initialize schema if needed
            if not self._schema_initialized:
                await self._initialize_schema()
                self._schema_initialized = True
            
            logger.info(f"Connected to SQLite database: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to connect to SQLite database: {e}")
            raise ConnectionError(f"Failed to connect to SQLite database: {e}")
    
    async def disconnect(self) -> None:
        """Close all database connections and cleanup resources."""
        # SQLite connections are managed per-operation, no persistent pool to close
        self._connection_pool.clear()
        logger.info("Disconnected from SQLite database")
    
    async def is_connected(self) -> bool:
        """
        Check if database is accessible.
        
        Returns:
            bool: True if database is accessible, False otherwise
        """
        try:
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as conn:
                await conn.execute("SELECT 1")
                return True
        except Exception:
            return False
    
    async def _get_connection(self):
        """Get a database connection with proper configuration."""
        conn = await aiosqlite.connect(self.db_path, timeout=self.timeout)
        conn.row_factory = aiosqlite.Row
        return conn
    
    async def _initialize_schema(self) -> None:
        """Initialize database schema with tables and indexes."""
        try:
            async with await self._get_connection() as conn:
                # Create tickets table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS tickets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket_id TEXT UNIQUE NOT NULL,
                        guild_id INTEGER NOT NULL,
                        channel_id INTEGER NOT NULL,
                        creator_id INTEGER NOT NULL,
                        status TEXT DEFAULT 'open',
                        created_at TIMESTAMP NOT NULL,
                        closed_at TIMESTAMP NULL,
                        transcript_url TEXT NULL,
                        assigned_staff TEXT DEFAULT '[]',
                        participants TEXT DEFAULT '[]'
                    )
                """)
                
                # Create indexes for better query performance
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tickets_ticket_id 
                    ON tickets(ticket_id)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tickets_guild_id 
                    ON tickets(guild_id)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tickets_creator_id 
                    ON tickets(creator_id, guild_id)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tickets_status 
                    ON tickets(status, guild_id)
                """)
                
                await conn.commit()
                logger.info("SQLite schema initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize SQLite schema: {e}")
            raise DatabaseError(f"Failed to initialize schema: {e}")
    
    def _ticket_from_row(self, row) -> Ticket:
        """Convert database row to Ticket object."""
        return Ticket(
            ticket_id=row['ticket_id'],
            guild_id=row['guild_id'],
            channel_id=row['channel_id'],
            creator_id=row['creator_id'],
            status=TicketStatus(row['status']),
            created_at=datetime.fromisoformat(row['created_at']),
            closed_at=datetime.fromisoformat(row['closed_at']) if row['closed_at'] else None,
            assigned_staff=json.loads(row['assigned_staff']),
            participants=json.loads(row['participants']),
            transcript_url=row['transcript_url']
        )
    
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
        try:
            async with await self._get_connection() as conn:
                await conn.execute("""
                    INSERT INTO tickets (
                        ticket_id, guild_id, channel_id, creator_id, status,
                        created_at, closed_at, transcript_url, assigned_staff, participants
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticket.ticket_id,
                    ticket.guild_id,
                    ticket.channel_id,
                    ticket.creator_id,
                    ticket.status.value,
                    ticket.created_at.isoformat(),
                    ticket.closed_at.isoformat() if ticket.closed_at else None,
                    ticket.transcript_url,
                    json.dumps(ticket.assigned_staff),
                    json.dumps(ticket.participants)
                ))
                await conn.commit()
                
                logger.info(f"Created ticket {ticket.ticket_id} in SQLite database")
                return ticket.ticket_id
                
        except aiosqlite.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                raise DuplicateTicketError(f"Ticket {ticket.ticket_id} already exists")
            raise DatabaseError(f"Failed to create ticket: {e}")
        except Exception as e:
            logger.error(f"Failed to create ticket {ticket.ticket_id}: {e}")
            raise DatabaseError(f"Failed to create ticket: {e}")
    
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
        try:
            async with await self._get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM tickets WHERE ticket_id = ?
                """, (ticket_id,))
                row = await cursor.fetchone()
                
                if row:
                    return self._ticket_from_row(row)
                return None
                
        except Exception as e:
            logger.error(f"Failed to get ticket {ticket_id}: {e}")
            raise DatabaseError(f"Failed to retrieve ticket: {e}")
    
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
        try:
            async with await self._get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM tickets 
                    WHERE creator_id = ? AND guild_id = ?
                    ORDER BY created_at DESC
                """, (user_id, guild_id))
                rows = await cursor.fetchall()
                
                return [self._ticket_from_row(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get tickets for user {user_id} in guild {guild_id}: {e}")
            raise DatabaseError(f"Failed to retrieve user tickets: {e}")
    
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
        try:
            async with await self._get_connection() as conn:
                if status:
                    cursor = await conn.execute("""
                        SELECT * FROM tickets 
                        WHERE guild_id = ? AND status = ?
                        ORDER BY created_at DESC
                    """, (guild_id, status))
                else:
                    cursor = await conn.execute("""
                        SELECT * FROM tickets 
                        WHERE guild_id = ?
                        ORDER BY created_at DESC
                    """, (guild_id,))
                
                rows = await cursor.fetchall()
                return [self._ticket_from_row(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get tickets for guild {guild_id}: {e}")
            raise DatabaseError(f"Failed to retrieve guild tickets: {e}")
    
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
        try:
            # Build dynamic update query
            set_clauses = []
            values = []
            
            for field, value in updates.items():
                if field == 'status' and isinstance(value, TicketStatus):
                    set_clauses.append("status = ?")
                    values.append(value.value)
                elif field == 'closed_at' and isinstance(value, datetime):
                    set_clauses.append("closed_at = ?")
                    values.append(value.isoformat())
                elif field == 'transcript_url':
                    set_clauses.append("transcript_url = ?")
                    values.append(value)
                elif field in ['assigned_staff', 'participants']:
                    set_clauses.append(f"{field} = ?")
                    values.append(json.dumps(value))
                else:
                    set_clauses.append(f"{field} = ?")
                    values.append(value)
            
            if not set_clauses:
                return False
            
            values.append(ticket_id)
            query = f"UPDATE tickets SET {', '.join(set_clauses)} WHERE ticket_id = ?"
            
            async with await self._get_connection() as conn:
                cursor = await conn.execute(query, values)
                await conn.commit()
                
                updated = cursor.rowcount > 0
                if updated:
                    logger.info(f"Updated ticket {ticket_id} in SQLite database")
                return updated
                
        except Exception as e:
            logger.error(f"Failed to update ticket {ticket_id}: {e}")
            raise DatabaseError(f"Failed to update ticket: {e}")
    
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
        try:
            updates = {
                'status': TicketStatus.CLOSED,
                'closed_at': datetime.utcnow()
            }
            if transcript_url:
                updates['transcript_url'] = transcript_url
            
            return await self.update_ticket(ticket_id, updates)
            
        except Exception as e:
            logger.error(f"Failed to close ticket {ticket_id}: {e}")
            raise DatabaseError(f"Failed to close ticket: {e}")
    
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
        try:
            async with await self._get_connection() as conn:
                cursor = await conn.execute("""
                    DELETE FROM tickets WHERE ticket_id = ?
                """, (ticket_id,))
                await conn.commit()
                
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"Deleted ticket {ticket_id} from SQLite database")
                return deleted
                
        except Exception as e:
            logger.error(f"Failed to delete ticket {ticket_id}: {e}")
            raise DatabaseError(f"Failed to delete ticket: {e}")
    
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
        try:
            ticket = await self.get_ticket(ticket_id)
            if not ticket:
                return False
            
            if user_id not in ticket.participants:
                ticket.participants.append(user_id)
                return await self.update_ticket(ticket_id, {'participants': ticket.participants})
            
            return True  # User already in participants
            
        except Exception as e:
            logger.error(f"Failed to add participant {user_id} to ticket {ticket_id}: {e}")
            raise DatabaseError(f"Failed to add participant: {e}")
    
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
        try:
            ticket = await self.get_ticket(ticket_id)
            if not ticket:
                return False
            
            if user_id in ticket.participants:
                ticket.participants.remove(user_id)
                return await self.update_ticket(ticket_id, {'participants': ticket.participants})
            
            return True  # User not in participants
            
        except Exception as e:
            logger.error(f"Failed to remove participant {user_id} from ticket {ticket_id}: {e}")
            raise DatabaseError(f"Failed to remove participant: {e}")
    
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
        try:
            async with await self._get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM tickets 
                    WHERE creator_id = ? AND guild_id = ? AND status = 'open'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (user_id, guild_id))
                row = await cursor.fetchone()
                
                if row:
                    return self._ticket_from_row(row)
                return None
                
        except Exception as e:
            logger.error(f"Failed to get active ticket for user {user_id} in guild {guild_id}: {e}")
            raise DatabaseError(f"Failed to retrieve active ticket: {e}")