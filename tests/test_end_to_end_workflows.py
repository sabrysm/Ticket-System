"""
End-to-end workflow tests for the Discord ticket bot.

This module tests complete ticket workflows from creation to closure,
multi-user scenarios, and error handling in realistic conditions.
"""
import pytest
import asyncio
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

import discord
from discord.ext import commands

from database.sqlite_adapter import SQLiteAdapter
from models.ticket import Ticket, TicketStatus
from core.ticket_manager import TicketManager
from config.config_manager import ConfigManager, GuildConfig
from commands.ticket_commands import TicketCommands
from errors import (
    TicketCreationError, UserManagementError, PermissionError as TicketPermissionError,
    TicketClosingError, TicketNotFoundError
)


class MockDiscordObjects:
    """Factory for creating mock Discord objects for testing."""
    
    @staticmethod
    def create_mock_user(user_id: int, name: str = "TestUser", roles: List[int] = None) -> MagicMock:
        """Create a mock Discord member."""
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
        return user
    
    @staticmethod
    def create_mock_guild(guild_id: int, name: str = "TestGuild") -> MagicMock:
        """Create a mock Discord guild."""
        guild = MagicMock(spec=discord.Guild)
        guild.id = guild_id
        guild.name = name
        
        # Mock default role
        default_role = MagicMock(spec=discord.Role)
        default_role.id = guild_id  # Default role has same ID as guild
        guild.default_role = default_role
        
        # Mock bot member
        bot_member = MagicMock(spec=discord.Member)
        bot_member.id = 12345  # Bot ID
        guild.me = bot_member
        
        # Mock methods
        guild.get_role = MagicMock(return_value=None)
        guild.get_channel = MagicMock(return_value=None)
        guild.create_text_channel = AsyncMock()
        
        return guild
    
    @staticmethod
    def create_mock_channel(channel_id: int, guild: MagicMock, name: str = "test-channel") -> MagicMock:
        """Create a mock Discord text channel."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = channel_id
        channel.name = name
        channel.guild = guild
        channel.mention = f"<#{channel_id}>"
        
        # Mock async methods
        channel.send = AsyncMock()
        channel.set_permissions = AsyncMock()
        channel.edit = AsyncMock()
        channel.delete = AsyncMock()
        channel.history = MagicMock()
        
        return channel
    
    @staticmethod
    def create_mock_interaction(user: MagicMock, guild: MagicMock, channel: MagicMock) -> MagicMock:
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = user
        interaction.guild = guild
        interaction.channel = channel
        
        # Mock response methods
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        
        return interaction
    
    @staticmethod
    def create_mock_bot() -> MagicMock:
        """Create a mock Discord bot."""
        bot = MagicMock(spec=commands.Bot)
        bot.get_user = MagicMock(return_value=None)
        bot.get_channel = MagicMock(return_value=None)
        return bot


class TestEndToEndWorkflows:
    """End-to-end workflow tests for complete ticket operations."""
    
    @pytest.fixture
    async def database_adapter(self):
        """Create a temporary SQLite database adapter for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        adapter = SQLiteAdapter(db_path)
        await adapter.connect()
        yield adapter
        await adapter.disconnect()
        
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock configuration manager."""
        config_manager = MagicMock(spec=ConfigManager)
        
        # Create default guild config
        guild_config = GuildConfig(
            guild_id=12345,
            staff_roles=[22222, 33333],  # Staff role IDs
            ticket_category=55555,  # Category ID for tickets
            log_channel=66666,  # Log channel ID
            embed_settings={},
            database_config={}
        )
        
        config_manager.get_guild_config = MagicMock(return_value=guild_config)
        return config_manager
    
    @pytest.fixture
    async def ticket_manager(self, database_adapter, mock_config_manager):
        """Create a ticket manager with real database and mock Discord components."""
        mock_bot = MockDiscordObjects.create_mock_bot()
        
        manager = TicketManager(mock_bot, database_adapter, mock_config_manager)
        return manager
    
    @pytest.fixture
    def mock_discord_objects(self):
        """Create a set of mock Discord objects for testing."""
        # Create users
        regular_user = MockDiscordObjects.create_mock_user(11111, "RegularUser")
        staff_user = MockDiscordObjects.create_mock_user(22222, "StaffUser", roles=[22222])
        admin_user = MockDiscordObjects.create_mock_user(33333, "AdminUser", roles=[33333])
        other_user = MockDiscordObjects.create_mock_user(44444, "OtherUser")
        
        # Create guild
        guild = MockDiscordObjects.create_mock_guild(12345, "TestGuild")
        
        # Create channels
        ticket_channel = MockDiscordObjects.create_mock_channel(67890, guild, "ticket-test123")
        general_channel = MockDiscordObjects.create_mock_channel(67891, guild, "general")
        
        return {
            'regular_user': regular_user,
            'staff_user': staff_user,
            'admin_user': admin_user,
            'other_user': other_user,
            'guild': guild,
            'ticket_channel': ticket_channel,
            'general_channel': general_channel
        }
    
    @pytest.mark.asyncio
    async def test_complete_ticket_creation_workflow(self, ticket_manager, mock_discord_objects):
        """Test complete ticket creation workflow from start to finish."""
        user = mock_discord_objects['regular_user']
        guild = mock_discord_objects['guild']
        
        # Mock channel creation
        created_channel = MockDiscordObjects.create_mock_channel(99999, guild, "ticket-abc123")
        guild.create_text_channel.return_value = created_channel
        
        # Create ticket
        ticket = await ticket_manager.create_ticket(user, guild)
        
        # Verify ticket was created correctly
        assert ticket is not None
        assert ticket.guild_id == guild.id
        assert ticket.creator_id == user.id
        assert ticket.status == TicketStatus.OPEN
        assert ticket.channel_id == created_channel.id
        assert user.id in ticket.participants
        
        # Verify channel was created with correct parameters
        guild.create_text_channel.assert_called_once()
        call_args = guild.create_text_channel.call_args
        assert call_args[1]['name'].startswith('ticket-')
        assert call_args[1]['topic'].startswith('Support ticket')
        
        # Verify welcome message was sent
        created_channel.send.assert_called_once()
        
        # Verify ticket exists in database
        retrieved_ticket = await ticket_manager.database.get_ticket(ticket.ticket_id)
        assert retrieved_ticket is not None
        assert retrieved_ticket.ticket_id == ticket.ticket_id
    
    @pytest.mark.asyncio
    async def test_prevent_duplicate_ticket_creation(self, ticket_manager, mock_discord_objects):
        """Test that users cannot create multiple active tickets."""
        user = mock_discord_objects['regular_user']
        guild = mock_discord_objects['guild']
        
        # Mock channel creation
        created_channel = MockDiscordObjects.create_mock_channel(99999, guild, "ticket-abc123")
        guild.create_text_channel.return_value = created_channel
        
        # Create first ticket
        ticket1 = await ticket_manager.create_ticket(user, guild)
        assert ticket1 is not None
        
        # Attempt to create second ticket should fail
        with pytest.raises(TicketPermissionError, match="already has an active ticket"):
            await ticket_manager.create_ticket(user, guild)
        
        # Verify only one ticket exists
        user_tickets = await ticket_manager.database.get_tickets_by_user(user.id, guild.id)
        assert len(user_tickets) == 1
    
    @pytest.mark.asyncio
    async def test_multi_user_ticket_workflow(self, ticket_manager, mock_discord_objects):
        """Test complete workflow with multiple users being added and removed."""
        creator = mock_discord_objects['regular_user']
        staff = mock_discord_objects['staff_user']
        other_user = mock_discord_objects['other_user']
        guild = mock_discord_objects['guild']
        
        # Mock channel creation
        ticket_channel = MockDiscordObjects.create_mock_channel(99999, guild, "ticket-abc123")
        guild.create_text_channel.return_value = ticket_channel
        
        # Step 1: Create ticket
        ticket = await ticket_manager.create_ticket(creator, guild)
        assert ticket is not None
        
        # Step 2: Add another user to the ticket
        success = await ticket_manager.add_user_to_ticket(ticket_channel, other_user, staff)
        assert success is True
        
        # Verify user was added to channel permissions
        ticket_channel.set_permissions.assert_called()
        
        # Verify user was added to database
        updated_ticket = await ticket_manager.database.get_ticket(ticket.ticket_id)
        assert other_user.id in updated_ticket.participants
        
        # Step 3: Try to add the same user again (should handle gracefully)
        with pytest.raises(UserManagementError, match="already in ticket"):
            await ticket_manager.add_user_to_ticket(ticket_channel, other_user, staff)
        
        # Step 4: Remove the user from the ticket
        success = await ticket_manager.remove_user_from_ticket(ticket_channel, other_user, staff)
        assert success is True
        
        # Verify user was removed from database
        final_ticket = await ticket_manager.database.get_ticket(ticket.ticket_id)
        assert other_user.id not in final_ticket.participants
        assert creator.id in final_ticket.participants  # Creator should remain
    
    @pytest.mark.asyncio
    async def test_ticket_closing_workflow(self, ticket_manager, mock_discord_objects):
        """Test complete ticket closing workflow with transcript generation."""
        creator = mock_discord_objects['regular_user']
        staff = mock_discord_objects['staff_user']
        guild = mock_discord_objects['guild']
        
        # Mock channel creation
        ticket_channel = MockDiscordObjects.create_mock_channel(99999, guild, "ticket-abc123")
        guild.create_text_channel.return_value = ticket_channel
        
        # Mock message history for transcript
        mock_message = MagicMock()
        mock_message.created_at = datetime.utcnow()
        mock_message.author = creator
        mock_message.content = "Test message content"
        mock_message.embeds = []
        mock_message.attachments = []
        
        # Create async iterator for message history
        async def mock_history(*args, **kwargs):
            yield mock_message
        
        ticket_channel.history.return_value = mock_history()
        
        # Step 1: Create ticket
        ticket = await ticket_manager.create_ticket(creator, guild)
        assert ticket is not None
        
        # Step 2: Close the ticket
        with patch('pathlib.Path.mkdir'), patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            success = await ticket_manager.close_ticket(ticket_channel, staff, "Issue resolved")
            assert success is True
        
        # Verify ticket status was updated in database
        closed_ticket = await ticket_manager.database.get_ticket(ticket.ticket_id)
        assert closed_ticket.status == TicketStatus.CLOSED
        assert closed_ticket.closed_at is not None
        
        # Verify transcript was generated (file operations were called)
        mock_open.assert_called_once()
        mock_file.write.assert_called_once()
        
        # Verify channel was processed for archiving/deletion
        # (The actual archiving behavior depends on configuration)
    
    @pytest.mark.asyncio
    async def test_permission_error_scenarios(self, ticket_manager, mock_discord_objects):
        """Test various permission error scenarios."""
        creator = mock_discord_objects['regular_user']
        non_staff = mock_discord_objects['other_user']  # User without staff role
        staff = mock_discord_objects['staff_user']
        guild = mock_discord_objects['guild']
        
        # Mock channel creation
        ticket_channel = MockDiscordObjects.create_mock_channel(99999, guild, "ticket-abc123")
        guild.create_text_channel.return_value = ticket_channel
        
        # Create ticket
        ticket = await ticket_manager.create_ticket(creator, guild)
        
        # Test 1: Non-staff user trying to add someone to ticket
        with pytest.raises(TicketPermissionError, match="not authorized"):
            await ticket_manager.add_user_to_ticket(ticket_channel, non_staff, non_staff)
        
        # Test 2: Non-staff user trying to remove someone from ticket
        with pytest.raises(TicketPermissionError, match="not authorized"):
            await ticket_manager.remove_user_from_ticket(ticket_channel, creator, non_staff)
        
        # Test 3: Staff trying to remove ticket creator (should require confirmation)
        with pytest.raises(TicketPermissionError, match="Cannot remove ticket creator"):
            await ticket_manager.remove_user_from_ticket(ticket_channel, creator, staff)
        
        # Test 4: Non-staff user trying to close ticket
        with pytest.raises(TicketPermissionError, match="not authorized"):
            await ticket_manager.close_ticket(ticket_channel, non_staff)
    
    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self, ticket_manager, mock_discord_objects):
        """Test error recovery in various failure scenarios."""
        creator = mock_discord_objects['regular_user']
        staff = mock_discord_objects['staff_user']
        guild = mock_discord_objects['guild']
        
        # Test 1: Channel creation failure
        guild.create_text_channel.side_effect = discord.Forbidden()
        
        with pytest.raises(TicketCreationError, match="lacks permission"):
            await ticket_manager.create_ticket(creator, guild)
        
        # Reset mock
        guild.create_text_channel.side_effect = None
        ticket_channel = MockDiscordObjects.create_mock_channel(99999, guild, "ticket-abc123")
        guild.create_text_channel.return_value = ticket_channel
        
        # Test 2: Database failure during ticket creation
        with patch.object(ticket_manager.database, 'create_ticket', side_effect=Exception("DB Error")):
            with pytest.raises(TicketCreationError, match="Unexpected error"):
                await ticket_manager.create_ticket(creator, guild)
        
        # Test 3: Permission error during user addition
        ticket = await ticket_manager.create_ticket(creator, guild)
        ticket_channel.set_permissions.side_effect = discord.Forbidden()
        
        with pytest.raises(UserManagementError, match="lacks permission"):
            await ticket_manager.add_user_to_ticket(ticket_channel, staff, staff)
    
    @pytest.mark.asyncio
    async def test_concurrent_ticket_operations(self, ticket_manager, mock_discord_objects):
        """Test concurrent operations on the same ticket."""
        creator = mock_discord_objects['regular_user']
        staff = mock_discord_objects['staff_user']
        other_user = mock_discord_objects['other_user']
        guild = mock_discord_objects['guild']
        
        # Mock channel creation
        ticket_channel = MockDiscordObjects.create_mock_channel(99999, guild, "ticket-abc123")
        guild.create_text_channel.return_value = ticket_channel
        
        # Create ticket
        ticket = await ticket_manager.create_ticket(creator, guild)
        
        # Simulate concurrent operations
        async def add_user_task():
            return await ticket_manager.add_user_to_ticket(ticket_channel, other_user, staff)
        
        async def update_ticket_task():
            return await ticket_manager.database.update_ticket(
                ticket.ticket_id, 
                {'assigned_staff': [staff.id]}
            )
        
        # Run concurrent operations
        results = await asyncio.gather(add_user_task(), update_ticket_task(), return_exceptions=True)
        
        # Both operations should succeed (or at least not cause corruption)
        assert len(results) == 2
        
        # Verify final state is consistent
        final_ticket = await ticket_manager.database.get_ticket(ticket.ticket_id)
        assert final_ticket is not None
        assert final_ticket.status == TicketStatus.OPEN
    
    @pytest.mark.asyncio
    async def test_ticket_not_found_scenarios(self, ticket_manager, mock_discord_objects):
        """Test scenarios where tickets are not found."""
        staff = mock_discord_objects['staff_user']
        other_user = mock_discord_objects['other_user']
        guild = mock_discord_objects['guild']
        
        # Create a channel that's not associated with any ticket
        non_ticket_channel = MockDiscordObjects.create_mock_channel(88888, guild, "general")
        
        # Test 1: Try to add user to non-ticket channel
        with pytest.raises(TicketNotFoundError, match="No ticket found"):
            await ticket_manager.add_user_to_ticket(non_ticket_channel, other_user, staff)
        
        # Test 2: Try to remove user from non-ticket channel
        with pytest.raises(TicketNotFoundError, match="No ticket found"):
            await ticket_manager.remove_user_from_ticket(non_ticket_channel, other_user, staff)
        
        # Test 3: Try to close non-ticket channel
        with pytest.raises(TicketNotFoundError, match="No ticket found"):
            await ticket_manager.close_ticket(non_ticket_channel, staff)
        
        # Test 4: Get ticket by non-existent channel
        result = await ticket_manager.get_ticket_by_channel(99999)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_closed_ticket_operations(self, ticket_manager, mock_discord_objects):
        """Test operations on already closed tickets."""
        creator = mock_discord_objects['regular_user']
        staff = mock_discord_objects['staff_user']
        other_user = mock_discord_objects['other_user']
        guild = mock_discord_objects['guild']
        
        # Mock channel creation
        ticket_channel = MockDiscordObjects.create_mock_channel(99999, guild, "ticket-abc123")
        guild.create_text_channel.return_value = ticket_channel
        
        # Mock message history for transcript
        async def mock_history(*args, **kwargs):
            return
            yield  # Empty generator
        
        ticket_channel.history.return_value = mock_history()
        
        # Create and close ticket
        ticket = await ticket_manager.create_ticket(creator, guild)
        
        with patch('pathlib.Path.mkdir'), patch('builtins.open', create=True):
            await ticket_manager.close_ticket(ticket_channel, staff)
        
        # Test 1: Try to add user to closed ticket
        with pytest.raises(UserManagementError, match="Cannot add user to closed ticket"):
            await ticket_manager.add_user_to_ticket(ticket_channel, other_user, staff)
        
        # Test 2: Try to remove user from closed ticket
        with pytest.raises(UserManagementError, match="Cannot remove user from closed ticket"):
            await ticket_manager.remove_user_from_ticket(ticket_channel, creator, staff)
        
        # Test 3: Try to close already closed ticket
        with pytest.raises(TicketClosingError, match="already closed"):
            await ticket_manager.close_ticket(ticket_channel, staff)


class TestCommandIntegration:
    """Integration tests for ticket commands with real workflow scenarios."""
    
    @pytest.fixture
    async def setup_command_test(self):
        """Set up command testing environment."""
        # Create database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        database_adapter = SQLiteAdapter(db_path)
        await database_adapter.connect()
        
        # Create mock config manager
        config_manager = MagicMock(spec=ConfigManager)
        guild_config = GuildConfig(
            guild_id=12345,
            staff_roles=[22222],
            ticket_category=55555,
            log_channel=66666,
            embed_settings={},
            database_config={}
        )
        config_manager.get_guild_config = MagicMock(return_value=guild_config)
        
        # Create mock bot
        mock_bot = MockDiscordObjects.create_mock_bot()
        
        # Create ticket manager
        ticket_manager = TicketManager(mock_bot, database_adapter, config_manager)
        
        # Create command cog
        ticket_commands = TicketCommands(mock_bot)
        ticket_commands.ticket_manager = ticket_manager
        
        yield {
            'database': database_adapter,
            'ticket_manager': ticket_manager,
            'commands': ticket_commands,
            'bot': mock_bot
        }
        
        # Cleanup
        await database_adapter.disconnect()
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_new_ticket_command_workflow(self, setup_command_test):
        """Test the complete new ticket command workflow."""
        components = setup_command_test
        commands_cog = components['commands']
        
        # Create mock Discord objects
        user = MockDiscordObjects.create_mock_user(11111, "TestUser")
        guild = MockDiscordObjects.create_mock_guild(12345)
        channel = MockDiscordObjects.create_mock_channel(67890, guild)
        
        # Mock channel creation
        created_channel = MockDiscordObjects.create_mock_channel(99999, guild, "ticket-abc123")
        guild.create_text_channel.return_value = created_channel
        components['bot'].get_channel.return_value = created_channel
        
        # Create interaction
        interaction = MockDiscordObjects.create_mock_interaction(user, guild, channel)
        
        # Execute command
        await commands_cog.new_ticket(interaction)
        
        # Verify response was deferred
        interaction.response.defer.assert_called_once_with(ephemeral=True)
        
        # Verify success message was sent
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        embed = call_args[1]['embed']
        assert "✅ Ticket Created" in embed.title
        
        # Verify ticket was created in database
        tickets = await components['database'].get_tickets_by_user(user.id, guild.id)
        assert len(tickets) == 1
        assert tickets[0].creator_id == user.id
    
    @pytest.mark.asyncio
    async def test_add_user_command_workflow(self, setup_command_test):
        """Test the complete add user command workflow."""
        components = setup_command_test
        commands_cog = components['commands']
        
        # Create mock Discord objects
        creator = MockDiscordObjects.create_mock_user(11111, "Creator")
        staff = MockDiscordObjects.create_mock_user(22222, "Staff", roles=[22222])
        other_user = MockDiscordObjects.create_mock_user(33333, "OtherUser")
        guild = MockDiscordObjects.create_mock_guild(12345)
        
        # Create ticket first
        ticket_channel = MockDiscordObjects.create_mock_channel(99999, guild, "ticket-abc123")
        guild.create_text_channel.return_value = ticket_channel
        
        ticket = await components['ticket_manager'].create_ticket(creator, guild)
        
        # Create interaction for add command
        interaction = MockDiscordObjects.create_mock_interaction(staff, guild, ticket_channel)
        
        # Execute add command
        await commands_cog.add_user(interaction, other_user)
        
        # Verify response was deferred
        interaction.response.defer.assert_called_once()
        
        # Verify success message was sent
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        embed = call_args[1]['embed']
        assert "✅ User Added" in embed.title
        
        # Verify user was added to database
        updated_ticket = await components['database'].get_ticket(ticket.ticket_id)
        assert other_user.id in updated_ticket.participants
    
    @pytest.mark.asyncio
    async def test_command_error_handling(self, setup_command_test):
        """Test command error handling in various scenarios."""
        components = setup_command_test
        commands_cog = components['commands']
        
        # Create mock Discord objects
        user = MockDiscordObjects.create_mock_user(11111, "TestUser")
        guild = MockDiscordObjects.create_mock_guild(12345)
        channel = MockDiscordObjects.create_mock_channel(67890, guild)
        
        # Test 1: New ticket command when user already has active ticket
        # First create a ticket
        ticket_channel = MockDiscordObjects.create_mock_channel(99999, guild, "ticket-abc123")
        guild.create_text_channel.return_value = ticket_channel
        await components['ticket_manager'].create_ticket(user, guild)
        
        # Try to create another ticket
        interaction = MockDiscordObjects.create_mock_interaction(user, guild, channel)
        await commands_cog.new_ticket(interaction)
        
        # Should send error message about existing ticket
        interaction.followup.send.assert_called()
        call_args = interaction.followup.send.call_args
        embed = call_args[1]['embed']
        assert "❌ Ticket Already Exists" in embed.title
        
        # Test 2: Add user command in non-ticket channel
        non_staff = MockDiscordObjects.create_mock_user(44444, "NonStaff")
        other_user = MockDiscordObjects.create_mock_user(55555, "OtherUser")
        interaction2 = MockDiscordObjects.create_mock_interaction(non_staff, guild, channel)
        
        await commands_cog.add_user(interaction2, other_user)
        
        # Should send error about not being a ticket channel
        interaction2.followup.send.assert_called()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])