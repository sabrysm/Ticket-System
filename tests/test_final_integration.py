#!/usr/bin/env python3
"""
Final Integration Test Suite for Discord Ticket Bot

This module runs comprehensive integration tests that validate the complete
bot functionality, including real Discord server simulation, command validation,
database operations under load, and error recovery mechanisms.
"""
import pytest
import asyncio
import tempfile
import os
import json
import time
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import discord
from discord.ext import commands

# Import all components for testing
from bot import TicketBot, validate_environment
from database.sqlite_adapter import SQLiteAdapter
from models.ticket import Ticket, TicketStatus
from core.ticket_manager import TicketManager
from config.config_manager import ConfigManager, GuildConfig
from commands.ticket_commands import TicketCommands
from commands.admin_commands import AdminCommands
from errors import *
from logging_config import setup_logging, get_logger


class FinalIntegrationTestSuite:
    """Comprehensive final integration test suite."""
    
    def __init__(self):
        self.test_results = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'errors': []
        }
        
        # Setup test logging
        setup_logging(log_dir="test_logs", log_level="DEBUG")
        self.logger = get_logger(__name__)
    
    async def run_all_tests(self):
        """Run all integration tests and return results."""
        self.logger.info("Starting final integration test suite...")
        
        test_methods = [
            self.test_bot_initialization,
            self.test_complete_ticket_workflow,
            self.test_permission_system,
            self.test_database_operations_under_load,
            self.test_error_handling_and_recovery,
            self.test_command_validation,
            self.test_concurrent_operations,
            self.test_configuration_management,
            self.test_audit_logging,
            self.test_resource_cleanup
        ]
        
        for test_method in test_methods:
            self.test_results['total_tests'] += 1
            try:
                self.logger.info(f"Running test: {test_method.__name__}")
                await test_method()
                self.test_results['passed_tests'] += 1
                self.logger.info(f"✅ {test_method.__name__} PASSED")
            except Exception as e:
                self.test_results['failed_tests'] += 1
                error_msg = f"❌ {test_method.__name__} FAILED: {str(e)}"
                self.logger.error(error_msg)
                self.test_results['errors'].append(error_msg)
        
        return self.test_results
    
    async def test_bot_initialization(self):
        """Test complete bot initialization process."""
        self.logger.info("Testing bot initialization...")
        
        # Create temporary config
        config_data = {
            "global": {
                "database_type": "sqlite",
                "database_url": ":memory:",
                "log_level": "INFO"
            },
            "guilds": {
                "12345": {
                    "staff_roles": [22222],
                    "ticket_category": 55555,
                    "log_channel": 66666,
                    "embed_settings": {}
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(config_data, tmp)
            config_path = tmp.name
        
        try:
            # Test environment validation
            with patch.dict(os.environ, {'DISCORD_TOKEN': 'test_token'}):
                assert validate_environment() == True
            
            # Test bot creation (without actually connecting to Discord)
            with patch.dict(os.environ, {'CONFIG_FILE': config_path}):
                bot = TicketBot()
                
                # Test component initialization
                await bot._initialize_config()
                assert bot.config_manager is not None
                
                await bot._initialize_database()
                assert bot.database_adapter is not None
                
                await bot._initialize_ticket_manager()
                assert bot.ticket_manager is not None
                
                # Test readiness check
                bot._startup_complete = True
                assert bot.is_ready_for_operation() == True
                
                # Test cleanup
                await bot.close()
        
        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)
    
    async def test_complete_ticket_workflow(self):
        """Test complete ticket workflow from creation to closure."""
        self.logger.info("Testing complete ticket workflow...")
        
        # Setup test environment
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            # Initialize components
            database = SQLiteAdapter(db_path)
            await database.connect()
            
            mock_bot = MagicMock(spec=TicketBot)
            ticket_manager = TicketManager(mock_bot, database)
            
            # Create mock Discord objects
            guild = MagicMock(spec=discord.Guild)
            guild.id = 12345
            guild.name = "Test Guild"
            
            creator = MagicMock(spec=discord.Member)
            creator.id = 11111
            creator.name = "Creator"
            creator.display_name = "Creator"
            creator.mention = "<@11111>"
            creator.roles = []
            
            staff = MagicMock(spec=discord.Member)
            staff.id = 22222
            staff.name = "Staff"
            staff.roles = [MagicMock(id=22222)]
            
            other_user = MagicMock(spec=discord.Member)
            other_user.id = 33333
            other_user.name = "OtherUser"
            other_user.roles = []
            
            # Mock channel creation
            ticket_channel = MagicMock(spec=discord.TextChannel)
            ticket_channel.id = 99999
            ticket_channel.name = "ticket-abc123"
            ticket_channel.guild = guild
            ticket_channel.send = AsyncMock()
            ticket_channel.set_permissions = AsyncMock()
            ticket_channel.history = MagicMock()
            
            guild.create_text_channel = AsyncMock(return_value=ticket_channel)
            
            # Step 1: Create ticket
            ticket = await ticket_manager.create_ticket(creator, guild)
            assert ticket is not None
            assert ticket.creator_id == creator.id
            assert ticket.status == TicketStatus.OPEN
            
            # Step 2: Add user to ticket
            success = await ticket_manager.add_user_to_ticket(ticket_channel, other_user, staff)
            assert success == True
            
            # Verify user was added
            updated_ticket = await database.get_ticket(ticket.ticket_id)
            assert other_user.id in updated_ticket.participants
            
            # Step 3: Remove user from ticket
            success = await ticket_manager.remove_user_from_ticket(ticket_channel, other_user, staff)
            assert success == True
            
            # Step 4: Close ticket
            with patch('pathlib.Path.mkdir'), patch('builtins.open', create=True):
                # Mock message history
                async def mock_history(*args, **kwargs):
                    return
                    yield  # Empty generator
                
                ticket_channel.history.return_value = mock_history()
                
                success = await ticket_manager.close_ticket(ticket_channel, staff)
                assert success == True
            
            # Verify ticket was closed
            closed_ticket = await database.get_ticket(ticket.ticket_id)
            assert closed_ticket.status == TicketStatus.CLOSED
            
        finally:
            await database.disconnect()
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    async def test_permission_system(self):
        """Test permission system validation."""
        self.logger.info("Testing permission system...")
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            # Setup
            database = SQLiteAdapter(db_path)
            await database.connect()
            
            mock_bot = MagicMock(spec=TicketBot)
            ticket_manager = TicketManager(mock_bot, database)
            
            # Create mock objects
            guild = MagicMock(spec=discord.Guild)
            guild.id = 12345
            
            regular_user = MagicMock(spec=discord.Member)
            regular_user.id = 11111
            regular_user.roles = []
            
            staff_user = MagicMock(spec=discord.Member)
            staff_user.id = 22222
            staff_user.roles = [MagicMock(id=22222)]  # Has staff role
            
            non_staff = MagicMock(spec=discord.Member)
            non_staff.id = 33333
            non_staff.roles = []
            
            # Create a ticket first
            ticket_channel = MagicMock(spec=discord.TextChannel)
            ticket_channel.id = 99999
            ticket_channel.guild = guild
            ticket_channel.set_permissions = AsyncMock()
            
            guild.create_text_channel = AsyncMock(return_value=ticket_channel)
            
            ticket = await ticket_manager.create_ticket(regular_user, guild)
            
            # Test 1: Non-staff cannot add users
            with pytest.raises(TicketPermissionError):
                await ticket_manager.add_user_to_ticket(ticket_channel, regular_user, non_staff)
            
            # Test 2: Staff can add users
            success = await ticket_manager.add_user_to_ticket(ticket_channel, non_staff, staff_user)
            assert success == True
            
            # Test 3: Non-staff cannot remove users
            with pytest.raises(TicketPermissionError):
                await ticket_manager.remove_user_from_ticket(ticket_channel, non_staff, non_staff)
            
            # Test 4: Cannot remove ticket creator
            with pytest.raises(TicketPermissionError):
                await ticket_manager.remove_user_from_ticket(ticket_channel, regular_user, staff_user)
            
        finally:
            await database.disconnect()
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    async def test_database_operations_under_load(self):
        """Test database operations under concurrent load."""
        self.logger.info("Testing database operations under load...")
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            database = SQLiteAdapter(db_path)
            await database.connect()
            
            # Test concurrent ticket creation
            async def create_ticket_task(i):
                ticket_data = {
                    'ticket_id': f'load-test-{i}',
                    'guild_id': 12345,
                    'channel_id': 90000 + i,
                    'creator_id': 10000 + i,
                    'status': TicketStatus.OPEN.value,
                    'participants': [10000 + i]
                }
                return await database.create_ticket(ticket_data)
            
            # Run 50 concurrent operations
            tasks = [create_ticket_task(i) for i in range(50)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify results
            successful = [r for r in results if not isinstance(r, Exception)]
            failed = [r for r in results if isinstance(r, Exception)]
            
            self.logger.info(f"Load test: {len(successful)} successful, {len(failed)} failed")
            
            # Should have high success rate
            assert len(successful) >= 45  # At least 90% success rate
            
            # Test concurrent read operations
            async def read_task():
                return await database.get_tickets_by_guild(12345)
            
            read_tasks = [read_task() for _ in range(20)]
            read_results = await asyncio.gather(*read_tasks, return_exceptions=True)
            
            successful_reads = [r for r in read_results if not isinstance(r, Exception)]
            assert len(successful_reads) >= 18  # At least 90% success rate
            
        finally:
            await database.disconnect()
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        self.logger.info("Testing error handling and recovery...")
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            database = SQLiteAdapter(db_path)
            await database.connect()
            
            mock_bot = MagicMock(spec=TicketBot)
            ticket_manager = TicketManager(mock_bot, database)
            
            # Test 1: Database failure recovery
            original_execute = database.execute
            database.execute = AsyncMock(side_effect=Exception("Database error"))
            
            guild = MagicMock(spec=discord.Guild)
            guild.id = 12345
            user = MagicMock(spec=discord.Member)
            user.id = 11111
            user.roles = []
            
            # Should handle database error gracefully
            with pytest.raises(TicketCreationError):
                await ticket_manager.create_ticket(user, guild)
            
            # Restore database
            database.execute = original_execute
            
            # Should work again
            ticket_channel = MagicMock(spec=discord.TextChannel)
            ticket_channel.id = 99999
            ticket_channel.guild = guild
            ticket_channel.send = AsyncMock()
            ticket_channel.set_permissions = AsyncMock()
            
            guild.create_text_channel = AsyncMock(return_value=ticket_channel)
            
            ticket = await ticket_manager.create_ticket(user, guild)
            assert ticket is not None
            
            # Test 2: Discord API error handling
            guild.create_text_channel.side_effect = discord.Forbidden()
            
            with pytest.raises(TicketCreationError):
                await ticket_manager.create_ticket(user, guild)
            
        finally:
            await database.disconnect()
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    async def test_command_validation(self):
        """Test command validation and execution."""
        self.logger.info("Testing command validation...")
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            # Setup components
            database = SQLiteAdapter(db_path)
            await database.connect()
            
            mock_bot = MagicMock(spec=TicketBot)
            ticket_manager = TicketManager(mock_bot, database)
            
            # Create command cog
            ticket_commands = TicketCommands(mock_bot)
            ticket_commands.ticket_manager = ticket_manager
            
            # Create mock interaction
            user = MagicMock(spec=discord.Member)
            user.id = 11111
            user.roles = []
            
            guild = MagicMock(spec=discord.Guild)
            guild.id = 12345
            
            channel = MagicMock(spec=discord.TextChannel)
            channel.id = 67890
            channel.guild = guild
            
            interaction = MagicMock(spec=discord.Interaction)
            interaction.user = user
            interaction.guild = guild
            interaction.channel = channel
            interaction.response = MagicMock()
            interaction.response.defer = AsyncMock()
            interaction.followup = MagicMock()
            interaction.followup.send = AsyncMock()
            
            # Mock channel creation
            ticket_channel = MagicMock(spec=discord.TextChannel)
            ticket_channel.id = 99999
            ticket_channel.guild = guild
            ticket_channel.send = AsyncMock()
            ticket_channel.set_permissions = AsyncMock()
            
            guild.create_text_channel = AsyncMock(return_value=ticket_channel)
            mock_bot.get_channel.return_value = ticket_channel
            
            # Test new ticket command
            await ticket_commands.new_ticket(interaction)
            
            # Verify command executed
            interaction.response.defer.assert_called_once()
            interaction.followup.send.assert_called_once()
            
            # Verify ticket was created
            tickets = await database.get_tickets_by_user(user.id, guild.id)
            assert len(tickets) == 1
            
        finally:
            await database.disconnect()
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    async def test_concurrent_operations(self):
        """Test concurrent ticket operations."""
        self.logger.info("Testing concurrent operations...")
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            database = SQLiteAdapter(db_path)
            await database.connect()
            
            mock_bot = MagicMock(spec=TicketBot)
            ticket_manager = TicketManager(mock_bot, database)
            
            # Create test ticket
            guild = MagicMock(spec=discord.Guild)
            guild.id = 12345
            
            user = MagicMock(spec=discord.Member)
            user.id = 11111
            user.roles = []
            
            ticket_channel = MagicMock(spec=discord.TextChannel)
            ticket_channel.id = 99999
            ticket_channel.guild = guild
            ticket_channel.send = AsyncMock()
            ticket_channel.set_permissions = AsyncMock()
            
            guild.create_text_channel = AsyncMock(return_value=ticket_channel)
            
            ticket = await ticket_manager.create_ticket(user, guild)
            
            # Test concurrent user additions
            staff = MagicMock(spec=discord.Member)
            staff.id = 22222
            staff.roles = [MagicMock(id=22222)]
            
            users_to_add = []
            for i in range(5):
                test_user = MagicMock(spec=discord.Member)
                test_user.id = 30000 + i
                test_user.roles = []
                users_to_add.append(test_user)
            
            # Run concurrent add operations
            async def add_user_task(user_to_add):
                try:
                    return await ticket_manager.add_user_to_ticket(ticket_channel, user_to_add, staff)
                except Exception as e:
                    return e
            
            tasks = [add_user_task(user) for user in users_to_add]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Should have some successful operations
            successful = [r for r in results if r is True]
            assert len(successful) > 0
            
        finally:
            await database.disconnect()
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    async def test_configuration_management(self):
        """Test configuration management system."""
        self.logger.info("Testing configuration management...")
        
        # Create test config
        config_data = {
            "global": {
                "database_type": "sqlite",
                "database_url": ":memory:",
                "log_level": "INFO"
            },
            "guilds": {
                "12345": {
                    "staff_roles": [22222, 33333],
                    "ticket_category": 55555,
                    "log_channel": 66666,
                    "embed_settings": {
                        "color": "0x00ff00"
                    }
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(config_data, tmp)
            config_path = tmp.name
        
        try:
            # Test config loading
            config_manager = ConfigManager(config_path)
            
            # Test guild config retrieval
            guild_config = config_manager.get_guild_config(12345)
            assert guild_config is not None
            assert 22222 in guild_config.staff_roles
            assert guild_config.ticket_category == 55555
            
            # Test config validation
            errors = config_manager.validate_configuration()
            assert isinstance(errors, list)
            
            # Test global config
            db_type = config_manager.get_global_config('database_type')
            assert db_type == 'sqlite'
            
        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)
    
    async def test_audit_logging(self):
        """Test audit logging functionality."""
        self.logger.info("Testing audit logging...")
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            database = SQLiteAdapter(db_path)
            await database.connect()
            
            mock_bot = MagicMock(spec=TicketBot)
            
            # Patch audit logger
            with patch('core.ticket_manager.get_audit_logger') as mock_audit_logger:
                mock_logger = MagicMock()
                mock_audit_logger.return_value = mock_logger
                
                ticket_manager = TicketManager(mock_bot, database)
                
                # Create test objects
                guild = MagicMock(spec=discord.Guild)
                guild.id = 12345
                
                user = MagicMock(spec=discord.Member)
                user.id = 11111
                user.roles = []
                
                ticket_channel = MagicMock(spec=discord.TextChannel)
                ticket_channel.id = 99999
                ticket_channel.guild = guild
                ticket_channel.send = AsyncMock()
                ticket_channel.set_permissions = AsyncMock()
                
                guild.create_text_channel = AsyncMock(return_value=ticket_channel)
                
                # Perform operations that should be logged
                ticket = await ticket_manager.create_ticket(user, guild)
                
                # Verify audit log was called
                assert mock_logger.info.called
                
                # Check log message content
                log_calls = mock_logger.info.call_args_list
                assert len(log_calls) > 0
                
                # Verify ticket creation was logged
                log_messages = [call[0][0] for call in log_calls]
                ticket_created = any("Ticket created" in msg for msg in log_messages)
                assert ticket_created
        
        finally:
            await database.disconnect()
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    async def test_resource_cleanup(self):
        """Test resource cleanup and memory management."""
        self.logger.info("Testing resource cleanup...")
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            database = SQLiteAdapter(db_path)
            await database.connect()
            
            # Create and close many tickets to test cleanup
            for i in range(10):
                ticket_data = {
                    'ticket_id': f'cleanup-test-{i}',
                    'guild_id': 12345,
                    'channel_id': 80000 + i,
                    'creator_id': 20000 + i,
                    'status': TicketStatus.OPEN.value,
                    'participants': [20000 + i]
                }
                
                ticket_id = await database.create_ticket(ticket_data)
                
                # Close ticket
                await database.update_ticket(ticket_id, {
                    'status': TicketStatus.CLOSED.value
                })
            
            # Verify all tickets were processed
            connection = await database.get_connection()
            cursor = await connection.execute(
                "SELECT COUNT(*) FROM tickets WHERE status = ?",
                (TicketStatus.CLOSED.value,)
            )
            count = (await cursor.fetchone())[0]
            await cursor.close()
            
            assert count == 10
            
            # Test database cleanup
            await database.disconnect()
            assert not await database.is_connected()
            
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


async def run_final_integration_tests():
    """Run the complete final integration test suite."""
    print("🚀 Starting Final Integration Test Suite for Discord Ticket Bot")
    print("=" * 70)
    
    test_suite = FinalIntegrationTestSuite()
    
    start_time = time.time()
    results = await test_suite.run_all_tests()
    end_time = time.time()
    
    duration = end_time - start_time
    
    print("\n" + "=" * 70)
    print("📊 FINAL INTEGRATION TEST RESULTS")
    print("=" * 70)
    print(f"Total Tests: {results['total_tests']}")
    print(f"Passed: {results['passed_tests']} ✅")
    print(f"Failed: {results['failed_tests']} ❌")
    print(f"Success Rate: {(results['passed_tests'] / results['total_tests'] * 100):.1f}%")
    print(f"Duration: {duration:.2f} seconds")
    
    if results['errors']:
        print("\n❌ FAILED TESTS:")
        for error in results['errors']:
            print(f"  - {error}")
    
    print("\n" + "=" * 70)
    
    if results['failed_tests'] == 0:
        print("🎉 ALL TESTS PASSED! The Discord Ticket Bot is ready for deployment.")
        return True
    else:
        print("⚠️  Some tests failed. Please review and fix issues before deployment.")
        return False


if __name__ == "__main__":
    # Run the final integration tests
    success = asyncio.run(run_final_integration_tests())
    exit(0 if success else 1)