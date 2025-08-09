"""
System Integration Tests for Discord Ticket Bot

This module provides comprehensive system-level integration tests that validate
the complete bot functionality in a simulated Discord server environment,
including command validation, database operations under load, and error recovery.
"""
import pytest
import asyncio
import tempfile
import os
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

import discord
from discord.ext import commands

from bot import TicketBot
from database.sqlite_adapter import SQLiteAdapter
from models.ticket import Ticket, TicketStatus
from core.ticket_manager import TicketManager
from config.config_manager import ConfigManager, GuildConfig
from commands.ticket_commands import TicketCommands
from commands.admin_commands import AdminCommands
from errors import (
    TicketCreationError, UserManagementError, PermissionError as TicketPermissionError,
    TicketClosingError, TicketNotFoundError, DatabaseError
)

c
lass MockDiscordEnvironment:
    """Mock Discord environment for system testing."""
    
    def __init__(self):
        self.guilds = {}
        self.users = {}
        self.channels = {}
        self.messages = {}
        self.interactions = []
        
    def create_guild(self, guild_id: int, name: str = "Test Guild") -> MagicMock:
        """Create a mock guild."""
        guild = MagicMock(spec=discord.Guild)
        guild.id = guild_id
        guild.name = name
        guild.channels = []
        guild.members = []
        
        # Mock methods
        guild.create_text_channel = AsyncMock()
        guild.get_channel = MagicMock(return_value=None)
        guild.get_role = MagicMock(return_value=None)
        
        self.guilds[guild_id] = guild
        return guild
    
    def create_user(self, user_id: int, name: str, roles: List[int] = None) -> MagicMock:
        """Create a mock user."""
        user = MagicMock(spec=discord.Member)
        user.id = user_id
        user.name = name
        user.display_name = name
        user.mention = f"<@{user_id}>"
        
        # Create mock roles
        mock_roles = []
        if roles:
            for role_id in roles:
                role = MagicMock(spec=discord.Role)
                role.id = role_id
                mock_roles.append(role)
        
        user.roles = mock_roles
        self.users[user_id] = user
        return user
    
    def create_channel(self, channel_id: int, guild_id: int, name: str) -> MagicMock:
        """Create a mock channel."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = channel_id
        channel.name = name
        channel.guild = self.guilds[guild_id]
        channel.mention = f"<#{channel_id}>"
        
        # Mock async methods
        channel.send = AsyncMock()
        channel.set_permissions = AsyncMock()
        channel.edit = AsyncMock()
        channel.delete = AsyncMock()
        channel.history = MagicMock()
        
        self.channels[channel_id] = channel
        return channel
    
    def simulate_interaction(self, user_id: int, guild_id: int, channel_id: int) -> MagicMock:
        """Simulate a Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = self.users[user_id]
        interaction.guild = self.guilds[guild_id]
        interaction.channel = self.channels.get(channel_id)
        
        # Mock response methods
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        
        self.interactions.append(interaction)
        return interaction


class TestSystemIntegration:
    """Comprehensive system integration tests."""
    
    @pytest.fixture
    async def system_setup(self):
        """Set up complete system for testing."""
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        # Create temporary config file
        config_data = {
            "global": {
                "database_type": "sqlite",
                "database_url": db_path,
                "log_level": "INFO"
            },
            "guilds": {
                "12345": {
                    "staff_roles": [22222, 33333],
                    "ticket_category": 55555,
                    "log_channel": 66666,
                    "embed_settings": {
                        "color": "0x00ff00",
                        "title": "Create a Ticket"
                    }
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(config_data, tmp)
            config_path = tmp.name
        
        # Initialize components
        config_manager = ConfigManager(config_path)
        database_adapter = SQLiteAdapter(db_path)
        await database_adapter.connect()
        
        # Create mock bot
        mock_bot = MagicMock(spec=TicketBot)
        mock_bot.get_user = MagicMock(return_value=None)
        mock_bot.get_channel = MagicMock(return_value=None)
        
        # Create ticket manager
        ticket_manager = TicketManager(mock_bot, database_adapter)
        
        # Create command cogs
        ticket_commands = TicketCommands(mock_bot)
        ticket_commands.ticket_manager = ticket_manager
        
        admin_commands = AdminCommands(mock_bot)
        admin_commands.config_manager = config_manager
        
        # Create mock Discord environment
        discord_env = MockDiscordEnvironment()
        
        yield {
            'database': database_adapter,
            'config_manager': config_manager,
            'ticket_manager': ticket_manager,
            'ticket_commands': ticket_commands,
            'admin_commands': admin_commands,
            'discord_env': discord_env,
            'bot': mock_bot
        }
        
        # Cleanup
        await database_adapter.disconnect()
        if os.path.exists(db_path):
            os.unlink(db_path)
        if os.path.exists(config_path):
            os.unlink(config_path)
    
    @pytest.mark.asyncio
    async def test_complete_bot_functionality_simulation(self, system_setup):
        """Test complete bot functionality in simulated Discord environment."""
        components = system_setup
        discord_env = components['discord_env']
        
        # Set up Discord environment
        guild = discord_env.create_guild(12345, "Test Server")
        regular_user = discord_env.create_user(11111, "RegularUser")
        staff_user = discord_env.create_user(22222, "StaffUser", roles=[22222])
        admin_user = discord_env.create_user(33333, "AdminUser", roles=[33333])
        other_user = discord_env.create_user(44444, "OtherUser")
        
        general_channel = discord_env.create_channel(67890, 12345, "general")
        
        # Mock channel creation for tickets
        ticket_channel = discord_env.create_channel(99999, 12345, "ticket-abc123")
        guild.create_text_channel.return_value = ticket_channel
        components['bot'].get_channel.return_value = ticket_channel
        
        # Test 1: Admin sets up ticket system
        admin_interaction = discord_env.simulate_interaction(33333, 12345, 67890)
        await components['admin_commands'].setup_tickets(admin_interaction)
        
        # Verify setup response
        admin_interaction.response.defer.assert_called_once()
        admin_interaction.followup.send.assert_called_once()
        
        # Test 2: User creates a ticket
        user_interaction = discord_env.simulate_interaction(11111, 12345, 67890)
        await components['ticket_commands'].new_ticket(user_interaction)
        
        # Verify ticket creation
        user_interaction.response.defer.assert_called_once()
        user_interaction.followup.send.assert_called_once()
        
        # Verify ticket exists in database
        tickets = await components['database'].get_tickets_by_user(11111, 12345)
        assert len(tickets) == 1
        ticket = tickets[0]
        assert ticket.creator_id == 11111
        assert ticket.status == TicketStatus.OPEN
        
        # Test 3: Staff adds another user to ticket
        staff_interaction = discord_env.simulate_interaction(22222, 12345, 99999)
        await components['ticket_commands'].add_user(staff_interaction, other_user)
        
        # Verify user addition
        staff_interaction.response.defer.assert_called_once()
        staff_interaction.followup.send.assert_called_once()
        
        # Verify user was added to database
        updated_ticket = await components['database'].get_ticket(ticket.ticket_id)
        assert other_user.id in updated_ticket.participants
        
        # Test 4: Staff removes user from ticket
        await components['ticket_commands'].remove_user(staff_interaction, other_user)
        
        # Verify user removal
        final_ticket = await components['database'].get_ticket(ticket.ticket_id)
        assert other_user.id not in final_ticket.participants
        
        # Test 5: Staff closes ticket
        with patch('pathlib.Path.mkdir'), patch('builtins.open', create=True):
            # Mock message history for transcript
            async def mock_history(*args, **kwargs):
                return
                yield  # Empty generator
            
            ticket_channel.history.return_value = mock_history()
            
            await components['ticket_commands'].close_ticket(staff_interaction, "Issue resolved")
        
        # Verify ticket closure
        closed_ticket = await components['database'].get_ticket(ticket.ticket_id)
        assert closed_ticket.status == TicketStatus.CLOSED
        assert closed_ticket.closed_at is not None
    
    @pytest.mark.asyncio
    async def test_permission_validation_across_commands(self, system_setup):
        """Test permission validation across all commands."""
        components = system_setup
        discord_env = components['discord_env']
        
        # Set up Discord environment
        guild = discord_env.create_guild(12345, "Test Server")
        regular_user = discord_env.create_user(11111, "RegularUser")
        non_staff = discord_env.create_user(44444, "NonStaff")
        staff_user = discord_env.create_user(22222, "StaffUser", roles=[22222])
        
        general_channel = discord_env.create_channel(67890, 12345, "general")
        ticket_channel = discord_env.create_channel(99999, 12345, "ticket-abc123")
        
        # Create a ticket first
        guild.create_text_channel.return_value = ticket_channel
        await components['ticket_manager'].create_ticket(regular_user, guild)
        
        # Test 1: Non-staff trying to add user to ticket
        non_staff_interaction = discord_env.simulate_interaction(44444, 12345, 99999)
        await components['ticket_commands'].add_user(non_staff_interaction, regular_user)
        
        # Should receive permission error
        non_staff_interaction.followup.send.assert_called()
        call_args = non_staff_interaction.followup.send.call_args
        embed = call_args[1]['embed']
        assert "❌" in embed.title  # Error embed
        
        # Test 2: Non-staff trying to remove user from ticket
        await components['ticket_commands'].remove_user(non_staff_interaction, regular_user)
        
        # Should receive permission error
        assert non_staff_interaction.followup.send.call_count >= 2
        
        # Test 3: Non-staff trying to close ticket
        await components['ticket_commands'].close_ticket(non_staff_interaction)
        
        # Should receive permission error
        assert non_staff_interaction.followup.send.call_count >= 3
        
        # Test 4: Staff commands should work
        staff_interaction = discord_env.simulate_interaction(22222, 12345, 99999)
        other_user = discord_env.create_user(55555, "OtherUser")
        
        await components['ticket_commands'].add_user(staff_interaction, other_user)
        
        # Should succeed
        staff_interaction.response.defer.assert_called_once()
        staff_interaction.followup.send.assert_called_once()
        call_args = staff_interaction.followup.send.call_args
        embed = call_args[1]['embed']
        assert "✅" in embed.title  # Success embed
    
    @pytest.mark.asyncio
    async def test_database_operations_under_concurrent_load(self, system_setup):
        """Test database operations under concurrent load."""
        components = system_setup
        discord_env = components['discord_env']
        
        # Set up Discord environment
        guild = discord_env.create_guild(12345, "Test Server")
        
        # Create multiple users
        users = []
        for i in range(10):
            user = discord_env.create_user(10000 + i, f"User{i}")
            users.append(user)
        
        # Mock channel creation
        channels = []
        for i in range(10):
            channel = discord_env.create_channel(90000 + i, 12345, f"ticket-{i}")
            channels.append(channel)
        
        guild.create_text_channel.side_effect = channels
        
        # Test concurrent ticket creation
        async def create_ticket_task(user):
            try:
                return await components['ticket_manager'].create_ticket(user, guild)
            except Exception as e:
                return e
        
        # Run concurrent ticket creation
        tasks = [create_ticket_task(user) for user in users]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify results
        successful_creations = [r for r in results if isinstance(r, Ticket)]
        errors = [r for r in results if isinstance(r, Exception)]
        
        # Should have some successful creations
        assert len(successful_creations) > 0
        
        # Verify tickets in database
        all_tickets = []
        for user in users:
            user_tickets = await components['database'].get_tickets_by_user(user.id, 12345)
            all_tickets.extend(user_tickets)
        
        assert len(all_tickets) == len(successful_creations)
        
        # Test concurrent user operations on existing tickets
        if successful_creations:
            ticket = successful_creations[0]
            staff_user = discord_env.create_user(22222, "StaffUser", roles=[22222])
            
            # Get the ticket channel
            ticket_channel = None
            for channel in channels:
                if channel.id == ticket.channel_id:
                    ticket_channel = channel
                    break
            
            if ticket_channel:
                # Test concurrent add/remove operations
                async def add_user_task(user_to_add):
                    try:
                        return await components['ticket_manager'].add_user_to_ticket(
                            ticket_channel, user_to_add, staff_user
                        )
                    except Exception as e:
                        return e
                
                # Add multiple users concurrently
                add_tasks = [add_user_task(users[i]) for i in range(3)]
                add_results = await asyncio.gather(*add_tasks, return_exceptions=True)
                
                # Verify some operations succeeded
                successful_adds = [r for r in add_results if r is True]
                assert len(successful_adds) > 0
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery_mechanisms(self, system_setup):
        """Test error handling and recovery mechanisms."""
        components = system_setup
        discord_env = components['discord_env']
        
        # Set up Discord environment
        guild = discord_env.create_guild(12345, "Test Server")
        user = discord_env.create_user(11111, "TestUser")
        staff_user = discord_env.create_user(22222, "StaffUser", roles=[22222])
        
        # Test 1: Database connection failure recovery
        original_execute = components['database'].execute
        
        # Simulate database failure
        components['database'].execute = AsyncMock(side_effect=Exception("Database connection lost"))
        
        # Try to create ticket - should handle error gracefully
        with pytest.raises(TicketCreationError):
            await components['ticket_manager'].create_ticket(user, guild)
        
        # Restore database connection
        components['database'].execute = original_execute
        
        # Should work again
        ticket_channel = discord_env.create_channel(99999, 12345, "ticket-abc123")
        guild.create_text_channel.return_value = ticket_channel
        
        ticket = await components['ticket_manager'].create_ticket(user, guild)
        assert ticket is not None
        
        # Test 2: Discord API failure recovery
        # Simulate Discord permission error
        guild.create_text_channel.side_effect = discord.Forbidden()
        
        with pytest.raises(TicketCreationError):
            await components['ticket_manager'].create_ticket(user, guild)
        
        # Test 3: Partial operation failure recovery
        # Reset mock
        guild.create_text_channel.side_effect = None
        guild.create_text_channel.return_value = ticket_channel
        
        # Simulate permission error during user addition
        ticket_channel.set_permissions.side_effect = discord.Forbidden()
        
        with pytest.raises(UserManagementError):
            await components['ticket_manager'].add_user_to_ticket(
                ticket_channel, staff_user, staff_user
            )
        
        # Verify ticket still exists and is in consistent state
        existing_ticket = await components['database'].get_ticket(ticket.ticket_id)
        assert existing_ticket is not None
        assert existing_ticket.status == TicketStatus.OPEN
    
    @pytest.mark.asyncio
    async def test_configuration_validation_and_error_handling(self, system_setup):
        """Test configuration validation and error handling."""
        components = system_setup
        
        # Test 1: Invalid guild configuration
        invalid_config = GuildConfig(
            guild_id=99999,  # Non-existent guild
            staff_roles=[],  # Empty staff roles
            ticket_category=0,  # Invalid category
            log_channel=0,  # Invalid log channel
            embed_settings={},
            database_config={}
        )
        
        # Should handle invalid configuration gracefully
        components['config_manager'].guild_configs[99999] = invalid_config
        
        # Test 2: Missing configuration
        missing_guild_config = components['config_manager'].get_guild_config(88888)
        assert missing_guild_config is not None  # Should return default config
        
        # Test 3: Configuration validation
        errors = components['config_manager'].validate_configuration()
        # Should identify configuration issues but not crash
        assert isinstance(errors, list)
    
    @pytest.mark.asyncio
    async def test_memory_and_resource_management(self, system_setup):
        """Test memory and resource management under load."""
        components = system_setup
        discord_env = components['discord_env']
        
        # Set up Discord environment
        guild = discord_env.create_guild(12345, "Test Server")
        
        # Create and close many tickets to test resource cleanup
        for i in range(20):
            user = discord_env.create_user(20000 + i, f"User{i}")
            ticket_channel = discord_env.create_channel(80000 + i, 12345, f"ticket-{i}")
            guild.create_text_channel.return_value = ticket_channel
            
            # Create ticket
            ticket = await components['ticket_manager'].create_ticket(user, guild)
            assert ticket is not None
            
            # Mock message history for transcript
            async def mock_history(*args, **kwargs):
                return
                yield  # Empty generator
            
            ticket_channel.history.return_value = mock_history()
            
            # Close ticket immediately
            staff_user = discord_env.create_user(22222, "StaffUser", roles=[22222])
            
            with patch('pathlib.Path.mkdir'), patch('builtins.open', create=True):
                await components['ticket_manager'].close_ticket(ticket_channel, staff_user)
        
        # Verify all tickets were processed
        # Check database for closed tickets
        connection = await components['database'].get_connection()
        cursor = await connection.execute(
            "SELECT COUNT(*) FROM tickets WHERE status = ?",
            (TicketStatus.CLOSED.value,)
        )
        closed_count = (await cursor.fetchone())[0]
        await cursor.close()
        
        assert closed_count == 20
    
    @pytest.mark.asyncio
    async def test_audit_logging_and_tracking(self, system_setup):
        """Test audit logging and operation tracking."""
        components = system_setup
        discord_env = components['discord_env']
        
        # Set up Discord environment
        guild = discord_env.create_guild(12345, "Test Server")
        user = discord_env.create_user(11111, "TestUser")
        staff_user = discord_env.create_user(22222, "StaffUser", roles=[22222])
        other_user = discord_env.create_user(33333, "OtherUser")
        
        ticket_channel = discord_env.create_channel(99999, 12345, "ticket-abc123")
        guild.create_text_channel.return_value = ticket_channel
        
        # Patch audit logger to capture logs
        with patch('core.ticket_manager.get_audit_logger') as mock_audit_logger:
            mock_logger = MagicMock()
            mock_audit_logger.return_value = mock_logger
            
            # Create ticket
            ticket = await components['ticket_manager'].create_ticket(user, guild)
            
            # Add user
            await components['ticket_manager'].add_user_to_ticket(
                ticket_channel, other_user, staff_user
            )
            
            # Remove user
            await components['ticket_manager'].remove_user_from_ticket(
                ticket_channel, other_user, staff_user
            )
            
            # Close ticket
            with patch('pathlib.Path.mkdir'), patch('builtins.open', create=True):
                async def mock_history(*args, **kwargs):
                    return
                    yield  # Empty generator
                
                ticket_channel.history.return_value = mock_history()
                
                await components['ticket_manager'].close_ticket(ticket_channel, staff_user)
            
            # Verify audit logs were created
            assert mock_logger.info.call_count >= 4  # At least 4 operations logged
            
            # Verify log content includes relevant information
            log_calls = mock_logger.info.call_args_list
            log_messages = [call[0][0] for call in log_calls]
            
            # Check for key operations in logs
            ticket_created = any("Ticket created" in msg for msg in log_messages)
            user_added = any("User added to ticket" in msg for msg in log_messages)
            user_removed = any("User removed from ticket" in msg for msg in log_messages)
            ticket_closed = any("Ticket closed" in msg for msg in log_messages)
            
            assert ticket_created
            assert user_added
            assert user_removed
            assert ticket_closed


class TestPerformanceAndScalability:
    """Performance and scalability tests."""
    
    @pytest.fixture
    async def performance_setup(self):
        """Set up performance testing environment."""
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        database_adapter = SQLiteAdapter(db_path)
        await database_adapter.connect()
        
        # Create mock bot
        mock_bot = MagicMock(spec=TicketBot)
        
        # Create ticket manager
        ticket_manager = TicketManager(mock_bot, database_adapter)
        
        yield {
            'database': database_adapter,
            'ticket_manager': ticket_manager,
            'bot': mock_bot
        }
        
        # Cleanup
        await database_adapter.disconnect()
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_high_volume_ticket_creation(self, performance_setup):
        """Test high volume ticket creation performance."""
        components = performance_setup
        
        # Create mock Discord objects
        guild = MagicMock(spec=discord.Guild)
        guild.id = 12345
        guild.name = "Performance Test Guild"
        
        # Track timing
        start_time = time.time()
        
        # Create many tickets
        num_tickets = 100
        tickets_created = []
        
        for i in range(num_tickets):
            user = MagicMock(spec=discord.Member)
            user.id = 10000 + i
            user.name = f"User{i}"
            user.display_name = f"User{i}"
            user.mention = f"<@{user.id}>"
            user.roles = []
            
            # Mock channel creation
            channel = MagicMock(spec=discord.TextChannel)
            channel.id = 90000 + i
            channel.name = f"ticket-{i}"
            channel.guild = guild
            channel.send = AsyncMock()
            channel.set_permissions = AsyncMock()
            
            guild.create_text_channel = AsyncMock(return_value=channel)
            
            try:
                ticket = await components['ticket_manager'].create_ticket(user, guild)
                tickets_created.append(ticket)
            except Exception as e:
                print(f"Failed to create ticket {i}: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Performance assertions
        assert len(tickets_created) == num_tickets
        assert duration < 30  # Should complete within 30 seconds
        
        # Calculate throughput
        throughput = num_tickets / duration
        print(f"Ticket creation throughput: {throughput:.2f} tickets/second")
        
        # Verify all tickets in database
        connection = await components['database'].get_connection()
        cursor = await connection.execute("SELECT COUNT(*) FROM tickets")
        count = (await cursor.fetchone())[0]
        await cursor.close()
        
        assert count == num_tickets
    
    @pytest.mark.asyncio
    async def test_concurrent_database_operations(self, performance_setup):
        """Test concurrent database operations performance."""
        components = performance_setup
        
        # Create test data
        guild_id = 12345
        num_operations = 50
        
        # Pre-create some tickets
        tickets = []
        for i in range(10):
            ticket_data = {
                'ticket_id': f'test-{i}',
                'guild_id': guild_id,
                'channel_id': 90000 + i,
                'creator_id': 10000 + i,
                'status': TicketStatus.OPEN.value,
                'participants': [10000 + i]
            }
            ticket_id = await components['database'].create_ticket(ticket_data)
            tickets.append(ticket_id)
        
        # Define concurrent operations
        async def read_operation():
            return await components['database'].get_tickets_by_guild(guild_id)
        
        async def update_operation():
            if tickets:
                ticket_id = tickets[0]
                return await components['database'].update_ticket(
                    ticket_id, {'assigned_staff': [22222]}
                )
        
        async def create_operation():
            ticket_data = {
                'ticket_id': f'concurrent-{time.time()}',
                'guild_id': guild_id,
                'channel_id': int(time.time() * 1000) % 1000000,
                'creator_id': int(time.time() * 1000) % 1000000,
                'status': TicketStatus.OPEN.value,
                'participants': [int(time.time() * 1000) % 1000000]
            }
            return await components['database'].create_ticket(ticket_data)
        
        # Run concurrent operations
        start_time = time.time()
        
        tasks = []
        for i in range(num_operations):
            if i % 3 == 0:
                tasks.append(read_operation())
            elif i % 3 == 1:
                tasks.append(update_operation())
            else:
                tasks.append(create_operation())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Performance assertions
        successful_operations = [r for r in results if not isinstance(r, Exception)]
        failed_operations = [r for r in results if isinstance(r, Exception)]
        
        print(f"Concurrent operations: {len(successful_operations)} successful, {len(failed_operations)} failed")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Throughput: {len(successful_operations) / duration:.2f} operations/second")
        
        # Should have mostly successful operations
        assert len(successful_operations) > num_operations * 0.8  # At least 80% success rate
        assert duration < 10  # Should complete within 10 seconds
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, performance_setup):
        """Test memory usage under sustained load."""
        import psutil
        import gc
        
        components = performance_setup
        process = psutil.Process()
        
        # Get initial memory usage
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create and process many tickets
        for batch in range(5):  # 5 batches of 20 tickets each
            batch_tickets = []
            
            for i in range(20):
                ticket_id = f'memory-test-{batch}-{i}'
                ticket_data = {
                    'ticket_id': ticket_id,
                    'guild_id': 12345,
                    'channel_id': 80000 + (batch * 20) + i,
                    'creator_id': 20000 + (batch * 20) + i,
                    'status': TicketStatus.OPEN.value,
                    'participants': [20000 + (batch * 20) + i]
                }
                
                created_id = await components['database'].create_ticket(ticket_data)
                batch_tickets.append(created_id)
            
            # Process tickets (simulate operations)
            for ticket_id in batch_tickets:
                # Update ticket
                await components['database'].update_ticket(
                    ticket_id, {'assigned_staff': [22222]}
                )
                
                # Close ticket
                await components['database'].update_ticket(
                    ticket_id, {'status': TicketStatus.CLOSED.value}
                )
            
            # Force garbage collection
            gc.collect()
            
            # Check memory usage
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            print(f"Batch {batch + 1}: Memory usage: {current_memory:.2f} MB (+{memory_increase:.2f} MB)")
            
            # Memory should not grow excessively
            assert memory_increase < 100  # Less than 100MB increase
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_increase = final_memory - initial_memory
        
        print(f"Total memory increase: {total_increase:.2f} MB")
        assert total_increase < 150  # Total increase should be reasonable


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])