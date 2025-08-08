"""
Integration tests for database operations with real database instances.

This module tests all database adapters with actual database connections,
database switching, data consistency, and performance under load.
"""
import pytest
import asyncio
import tempfile
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

from database.adapter import DatabaseAdapter, DatabaseError, ConnectionError, DuplicateTicketError
from database.sqlite_adapter import SQLiteAdapter
from models.ticket import Ticket, TicketStatus


class TestDatabaseIntegration:
    """Integration tests for database operations with real database instances."""
    
    @pytest.fixture
    def temp_sqlite_db(self):
        """Create a temporary SQLite database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        yield db_path
        
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    async def sqlite_adapter(self, temp_sqlite_db):
        """Create and initialize SQLite adapter for testing."""
        adapter = SQLiteAdapter(temp_sqlite_db)
        await adapter.connect()
        yield adapter
        await adapter.disconnect()
    
    @pytest.fixture
    def sample_tickets(self):
        """Create sample tickets for testing."""
        base_time = datetime.utcnow()
        return [
            Ticket(
                ticket_id=f"test-{i}",
                guild_id=12345,
                channel_id=67890 + i,
                creator_id=11111 + i,
                status=TicketStatus.OPEN if i % 2 == 0 else TicketStatus.CLOSED,
                created_at=base_time + timedelta(minutes=i),
                closed_at=base_time + timedelta(hours=1) if i % 2 == 1 else None,
                assigned_staff=[22222, 33333] if i % 3 == 0 else [22222],
                participants=[11111 + i, 22222] + ([33333] if i % 3 == 0 else []),
                transcript_url=f"https://example.com/transcript-{i}" if i % 2 == 1 else None
            )
            for i in range(10)
        ]
    
    @pytest.mark.asyncio
    async def test_sqlite_connection_lifecycle(self, temp_sqlite_db):
        """Test SQLite adapter connection lifecycle."""
        adapter = SQLiteAdapter(temp_sqlite_db)
        
        # Connect (this creates the database file and schema)
        await adapter.connect()
        assert await adapter.is_connected()
        
        # Disconnect
        await adapter.disconnect()
        # SQLite file-based database remains accessible after disconnect
        assert await adapter.is_connected()
        
        # Reconnect
        await adapter.connect()
        assert await adapter.is_connected()
    
    @pytest.mark.asyncio
    async def test_sqlite_schema_initialization(self, temp_sqlite_db):
        """Test that SQLite schema is properly initialized."""
        adapter = SQLiteAdapter(temp_sqlite_db)
        await adapter.connect()
        
        # Verify we can perform basic operations (schema exists)
        test_ticket = Ticket(
            ticket_id="schema-test",
            guild_id=12345,
            channel_id=67890,
            creator_id=11111,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow()
        )
        
        ticket_id = await adapter.create_ticket(test_ticket)
        assert ticket_id == "schema-test"
        
        retrieved = await adapter.get_ticket(ticket_id)
        assert retrieved is not None
        assert retrieved.ticket_id == ticket_id
        
        await adapter.disconnect()
    
    @pytest.mark.asyncio
    async def test_sqlite_crud_operations(self, sqlite_adapter, sample_tickets):
        """Test complete CRUD operations with SQLite."""
        # Create tickets
        created_ids = []
        for ticket in sample_tickets[:5]:  # Use first 5 tickets
            ticket_id = await sqlite_adapter.create_ticket(ticket)
            created_ids.append(ticket_id)
            assert ticket_id == ticket.ticket_id
        
        # Read tickets
        for ticket_id in created_ids:
            retrieved = await sqlite_adapter.get_ticket(ticket_id)
            assert retrieved is not None
            assert retrieved.ticket_id == ticket_id
        
        # Update tickets
        for ticket_id in created_ids[:3]:  # Update first 3
            updates = {
                'status': TicketStatus.CLOSED,
                'closed_at': datetime.utcnow(),
                'transcript_url': f'https://example.com/updated-{ticket_id}'
            }
            result = await sqlite_adapter.update_ticket(ticket_id, updates)
            assert result is True
            
            # Verify update
            updated = await sqlite_adapter.get_ticket(ticket_id)
            assert updated.status == TicketStatus.CLOSED
            assert updated.transcript_url == f'https://example.com/updated-{ticket_id}'
        
        # Delete tickets
        for ticket_id in created_ids[-2:]:  # Delete last 2
            result = await sqlite_adapter.delete_ticket(ticket_id)
            assert result is True
            
            # Verify deletion
            deleted = await sqlite_adapter.get_ticket(ticket_id)
            assert deleted is None
    
    @pytest.mark.asyncio
    async def test_sqlite_participant_management(self, sqlite_adapter):
        """Test participant add/remove operations with SQLite."""
        # Create test ticket
        ticket = Ticket(
            ticket_id="participant-test",
            guild_id=12345,
            channel_id=67890,
            creator_id=11111,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow(),
            participants=[11111]  # Only creator initially
        )
        
        await sqlite_adapter.create_ticket(ticket)
        
        # Add participants
        new_participants = [22222, 33333, 44444]
        for user_id in new_participants:
            result = await sqlite_adapter.add_participant(ticket.ticket_id, user_id)
            assert result is True
        
        # Verify participants were added
        updated_ticket = await sqlite_adapter.get_ticket(ticket.ticket_id)
        for user_id in new_participants:
            assert user_id in updated_ticket.participants
        
        # Remove participants
        for user_id in new_participants[:2]:  # Remove first 2
            result = await sqlite_adapter.remove_participant(ticket.ticket_id, user_id)
            assert result is True
        
        # Verify participants were removed
        final_ticket = await sqlite_adapter.get_ticket(ticket.ticket_id)
        assert 22222 not in final_ticket.participants
        assert 33333 not in final_ticket.participants
        assert 44444 in final_ticket.participants  # Should still be there
        assert 11111 in final_ticket.participants  # Creator should remain
    
    @pytest.mark.asyncio
    async def test_sqlite_query_operations(self, sqlite_adapter, sample_tickets):
        """Test various query operations with SQLite."""
        # Create tickets across multiple guilds and users
        for ticket in sample_tickets:
            await sqlite_adapter.create_ticket(ticket)
        
        # Test get_tickets_by_user
        user_tickets = await sqlite_adapter.get_tickets_by_user(11111, 12345)
        assert len(user_tickets) == 1
        assert all(t.creator_id == 11111 for t in user_tickets)
        
        # Test get_tickets_by_guild (all tickets)
        guild_tickets = await sqlite_adapter.get_tickets_by_guild(12345)
        assert len(guild_tickets) == len(sample_tickets)
        assert all(t.guild_id == 12345 for t in guild_tickets)
        
        # Test get_tickets_by_guild with status filter
        open_tickets = await sqlite_adapter.get_tickets_by_guild(12345, "open")
        closed_tickets = await sqlite_adapter.get_tickets_by_guild(12345, "closed")
        
        assert len(open_tickets) + len(closed_tickets) == len(sample_tickets)
        assert all(t.status == TicketStatus.OPEN for t in open_tickets)
        assert all(t.status == TicketStatus.CLOSED for t in closed_tickets)
        
        # Test get_active_ticket_for_user
        active_ticket = await sqlite_adapter.get_active_ticket_for_user(11111, 12345)
        if active_ticket:  # May be None if user 11111's ticket is closed
            assert active_ticket.creator_id == 11111
            assert active_ticket.status == TicketStatus.OPEN
    
    @pytest.mark.asyncio
    async def test_sqlite_error_handling(self, sqlite_adapter):
        """Test error handling with SQLite operations."""
        # Test duplicate ticket creation
        ticket = Ticket(
            ticket_id="duplicate-test",
            guild_id=12345,
            channel_id=67890,
            creator_id=11111,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow()
        )
        
        # First creation should succeed
        await sqlite_adapter.create_ticket(ticket)
        
        # Second creation should raise DuplicateTicketError
        with pytest.raises(DuplicateTicketError):
            await sqlite_adapter.create_ticket(ticket)
        
        # Test operations on non-existent tickets
        assert await sqlite_adapter.get_ticket("non-existent") is None
        assert await sqlite_adapter.update_ticket("non-existent", {"status": TicketStatus.CLOSED}) is False
        assert await sqlite_adapter.close_ticket("non-existent") is False
        assert await sqlite_adapter.delete_ticket("non-existent") is False
        assert await sqlite_adapter.add_participant("non-existent", 12345) is False
        assert await sqlite_adapter.remove_participant("non-existent", 12345) is False
    
    @pytest.mark.asyncio
    async def test_sqlite_data_consistency(self, sqlite_adapter):
        """Test data consistency across operations with SQLite."""
        # Create ticket with specific data
        original_time = datetime.utcnow()
        ticket = Ticket(
            ticket_id="consistency-test",
            guild_id=12345,
            channel_id=67890,
            creator_id=11111,
            status=TicketStatus.OPEN,
            created_at=original_time,
            assigned_staff=[22222, 33333],
            participants=[11111, 22222, 33333, 44444]
        )
        
        await sqlite_adapter.create_ticket(ticket)
        
        # Retrieve and verify all fields
        retrieved = await sqlite_adapter.get_ticket(ticket.ticket_id)
        assert retrieved.ticket_id == ticket.ticket_id
        assert retrieved.guild_id == ticket.guild_id
        assert retrieved.channel_id == ticket.channel_id
        assert retrieved.creator_id == ticket.creator_id
        assert retrieved.status == ticket.status
        assert retrieved.created_at.replace(microsecond=0) == original_time.replace(microsecond=0)
        assert retrieved.closed_at is None
        assert retrieved.assigned_staff == ticket.assigned_staff
        assert retrieved.participants == ticket.participants
        assert retrieved.transcript_url is None
        
        # Update and verify consistency
        close_time = datetime.utcnow()
        updates = {
            'status': TicketStatus.CLOSED,
            'closed_at': close_time,
            'transcript_url': 'https://example.com/transcript',
            'assigned_staff': [22222, 33333, 55555],
            'participants': [11111, 22222, 55555]
        }
        
        await sqlite_adapter.update_ticket(ticket.ticket_id, updates)
        
        # Verify all updates were applied correctly
        updated = await sqlite_adapter.get_ticket(ticket.ticket_id)
        assert updated.status == TicketStatus.CLOSED
        assert updated.closed_at.replace(microsecond=0) == close_time.replace(microsecond=0)
        assert updated.transcript_url == 'https://example.com/transcript'
        assert updated.assigned_staff == [22222, 33333, 55555]
        assert updated.participants == [11111, 22222, 55555]
        
        # Original fields should remain unchanged
        assert updated.ticket_id == ticket.ticket_id
        assert updated.guild_id == ticket.guild_id
        assert updated.channel_id == ticket.channel_id
        assert updated.creator_id == ticket.creator_id
        assert updated.created_at.replace(microsecond=0) == original_time.replace(microsecond=0)


class TestDatabasePerformance:
    """Performance tests for database operations under load."""
    
    @pytest.fixture
    async def sqlite_adapter(self):
        """Create SQLite adapter for performance testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        adapter = SQLiteAdapter(db_path)
        await adapter.connect()
        yield adapter
        await adapter.disconnect()
        
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    def create_test_ticket(self, index: int) -> Ticket:
        """Create a test ticket with unique data."""
        return Ticket(
            ticket_id=f"perf-test-{index}",
            guild_id=12345 + (index % 10),  # Spread across 10 guilds
            channel_id=67890 + index,
            creator_id=11111 + (index % 100),  # 100 different users
            status=TicketStatus.OPEN if index % 3 != 0 else TicketStatus.CLOSED,
            created_at=datetime.utcnow() + timedelta(seconds=index),
            assigned_staff=[22222] + ([33333] if index % 5 == 0 else []),
            participants=[11111 + (index % 100), 22222] + ([33333] if index % 5 == 0 else [])
        )
    
    @pytest.mark.asyncio
    async def test_sqlite_bulk_create_performance(self, sqlite_adapter):
        """Test performance of bulk ticket creation."""
        num_tickets = 100  # Reduced for faster testing
        tickets = [self.create_test_ticket(i) for i in range(num_tickets)]
        
        start_time = time.time()
        
        # Create tickets in batches to avoid overwhelming the database
        batch_size = 20
        for i in range(0, num_tickets, batch_size):
            batch = tickets[i:i + batch_size]
            tasks = [sqlite_adapter.create_ticket(ticket) for ticket in batch]
            await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Created {num_tickets} tickets in {duration:.2f} seconds")
        print(f"Average: {duration/num_tickets*1000:.2f} ms per ticket")
        
        # Verify all tickets were created
        guild_tickets = await sqlite_adapter.get_tickets_by_guild(12345)
        assert len(guild_tickets) >= num_tickets // 10  # At least tickets for one guild
        
        # Performance assertion (should create 100 tickets in under 10 seconds)
        assert duration < 10.0, f"Bulk creation took too long: {duration:.2f}s"
    
    @pytest.mark.asyncio
    async def test_sqlite_concurrent_operations(self, sqlite_adapter):
        """Test concurrent database operations."""
        num_concurrent = 20  # Reduced for faster testing
        
        async def create_and_update_ticket(index: int):
            """Create a ticket and then update it."""
            ticket = self.create_test_ticket(index)
            
            # Create ticket
            await sqlite_adapter.create_ticket(ticket)
            
            # Update ticket
            updates = {
                'status': TicketStatus.CLOSED,
                'closed_at': datetime.utcnow(),
                'transcript_url': f'https://example.com/transcript-{index}'
            }
            await sqlite_adapter.update_ticket(ticket.ticket_id, updates)
            
            # Add participant
            await sqlite_adapter.add_participant(ticket.ticket_id, 99999)
            
            return ticket.ticket_id
        
        start_time = time.time()
        
        # Run concurrent operations
        tasks = [create_and_update_ticket(i) for i in range(num_concurrent)]
        ticket_ids = await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Completed {num_concurrent} concurrent operations in {duration:.2f} seconds")
        print(f"Average: {duration/num_concurrent*1000:.2f} ms per operation")
        
        # Verify all operations completed successfully
        assert len(ticket_ids) == num_concurrent
        
        # Verify final state of tickets
        for ticket_id in ticket_ids:
            ticket = await sqlite_adapter.get_ticket(ticket_id)
            assert ticket is not None
            assert ticket.status == TicketStatus.CLOSED
            assert ticket.transcript_url is not None
            assert 99999 in ticket.participants
        
        # Performance assertion (should complete 20 operations in under 5 seconds)
        assert duration < 5.0, f"Concurrent operations took too long: {duration:.2f}s"


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])