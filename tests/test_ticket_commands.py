"""
Unit tests for TicketCommands cog.

Tests all ticket command functionality including edge cases and error handling.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import discord
from discord.ext import commands

from commands.ticket_commands import TicketCommands
from core.ticket_manager import (
    TicketManager, TicketCreationError, UserManagementError, 
    PermissionError as TicketPermissionError, TicketClosingError, TicketNotFoundError
)
from models.ticket import Ticket, TicketStatus


class TestTicketCommands:
    """Test suite for TicketCommands cog."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        bot = AsyncMock(spec=commands.Bot)
        bot.get_channel = MagicMock()
        bot.get_user = MagicMock()
        return bot
    
    @pytest.fixture
    def mock_ticket_manager(self):
        """Create a mock ticket manager."""
        return AsyncMock(spec=TicketManager)
    
    @pytest.fixture
    def ticket_commands(self, mock_bot, mock_ticket_manager):
        """Create TicketCommands cog instance with mocked dependencies."""
        cog = TicketCommands(mock_bot)
        cog.ticket_manager = mock_ticket_manager
        return cog
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.user = MagicMock(spec=discord.Member)
        interaction.user.id = 12345
        interaction.user.mention = "<@12345>"
        interaction.guild = MagicMock(spec=discord.Guild)
        interaction.guild.id = 67890
        interaction.channel = MagicMock(spec=discord.TextChannel)
        interaction.channel.id = 11111
        return interaction
    
    @pytest.fixture
    def sample_ticket(self):
        """Create a sample ticket for testing."""
        return Ticket(
            ticket_id="TEST1234",
            guild_id=67890,
            channel_id=11111,
            creator_id=12345,
            status=TicketStatus.OPEN,
            created_at=datetime.now(timezone.utc),
            participants=[12345]
        )
    
    class TestNewTicketCommand:
        """Tests for the new ticket command."""
        
        @pytest.mark.asyncio
        async def test_new_ticket_success(self, ticket_commands, mock_interaction, sample_ticket):
            """Test successful ticket creation."""
            # Setup
            mock_channel = MagicMock(spec=discord.TextChannel)
            mock_channel.mention = "<#11111>"
            ticket_commands.bot.get_channel.return_value = mock_channel
            ticket_commands.ticket_manager.create_ticket.return_value = sample_ticket
            
            # Execute
            await ticket_commands.new_ticket.callback(ticket_commands, mock_interaction)
            
            # Verify
            ticket_commands.ticket_manager.create_ticket.assert_called_once_with(
                mock_interaction.user, mock_interaction.guild
            )
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_interaction.followup.send.assert_called_once()
            
            # Check embed content
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "✅ Ticket Created" in embed.title
            assert sample_ticket.ticket_id in embed.description
        
        @pytest.mark.asyncio
        async def test_new_ticket_already_exists(self, ticket_commands, mock_interaction):
            """Test ticket creation when user already has active ticket."""
            # Setup
            ticket_commands.ticket_manager.create_ticket.side_effect = TicketPermissionError(
                "User already has active ticket"
            )
            
            # Execute
            await ticket_commands.new_ticket.callback(ticket_commands, mock_interaction)
            
            # Verify
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "❌ Ticket Already Exists" in embed.title
        
        @pytest.mark.asyncio
        async def test_new_ticket_creation_error(self, ticket_commands, mock_interaction):
            """Test ticket creation failure."""
            # Setup
            ticket_commands.ticket_manager.create_ticket.side_effect = TicketCreationError(
                "Channel creation failed"
            )
            
            # Execute
            await ticket_commands.new_ticket.callback(ticket_commands, mock_interaction)
            
            # Verify
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "❌ Ticket Creation Failed" in embed.title
        
        @pytest.mark.asyncio
        async def test_new_ticket_no_manager(self, mock_bot, mock_interaction):
            """Test ticket creation when ticket manager is unavailable."""
            # Setup
            cog = TicketCommands(mock_bot)
            cog.ticket_manager = None
            mock_interaction.response.is_done.return_value = False
            
            # Execute
            await cog.new_ticket.callback(cog, mock_interaction)
            
            # Verify - The method should call send_error_embed which calls response.send_message
            # Since the ticket manager is None, it should return early with an error
            assert mock_interaction.response.send_message.called or mock_interaction.followup.send.called
    
    class TestAddUserCommand:
        """Tests for the add user command."""
        
        @pytest.fixture
        def mock_user_to_add(self):
            """Create a mock user to add to ticket."""
            user = MagicMock(spec=discord.Member)
            user.id = 54321
            user.mention = "<@54321>"
            return user
        
        @pytest.mark.asyncio
        async def test_add_user_success(self, ticket_commands, mock_interaction, mock_user_to_add, sample_ticket):
            """Test successful user addition to ticket."""
            # Setup
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = sample_ticket
            ticket_commands.ticket_manager.add_user_to_ticket.return_value = True
            
            # Execute
            await ticket_commands.add_user.callback(ticket_commands, mock_interaction, mock_user_to_add)
            
            # Verify
            ticket_commands.ticket_manager.add_user_to_ticket.assert_called_once_with(
                mock_interaction.channel, mock_user_to_add, mock_interaction.user
            )
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "✅ User Added" in embed.title
        
        @pytest.mark.asyncio
        async def test_add_user_not_ticket_channel(self, ticket_commands, mock_interaction, mock_user_to_add):
            """Test add user command in non-ticket channel."""
            # Setup
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = None
            
            # Execute
            await ticket_commands.add_user.callback(ticket_commands, mock_interaction, mock_user_to_add)
            
            # Verify
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "❌ Not a Ticket Channel" in embed.title
        
        @pytest.mark.asyncio
        async def test_add_user_closed_ticket(self, ticket_commands, mock_interaction, mock_user_to_add, sample_ticket):
            """Test adding user to closed ticket."""
            # Setup
            sample_ticket.status = TicketStatus.CLOSED
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = sample_ticket
            
            # Execute
            await ticket_commands.add_user.callback(ticket_commands, mock_interaction, mock_user_to_add)
            
            # Verify
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "❌ Ticket Closed" in embed.title
        
        @pytest.mark.asyncio
        async def test_add_user_already_in_ticket(self, ticket_commands, mock_interaction, mock_user_to_add, sample_ticket):
            """Test adding user who is already in ticket."""
            # Setup
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = sample_ticket
            ticket_commands.ticket_manager.add_user_to_ticket.side_effect = UserManagementError(
                "User already in ticket"
            )
            
            # Execute
            await ticket_commands.add_user.callback(ticket_commands, mock_interaction, mock_user_to_add)
            
            # Verify
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "❌ User Already Added" in embed.title
        
        @pytest.mark.asyncio
        async def test_add_user_invalid_channel_type(self, ticket_commands, mock_user_to_add):
            """Test add user command in non-text channel."""
            # Setup
            interaction = AsyncMock(spec=discord.Interaction)
            interaction.response = AsyncMock()
            interaction.response.is_done.return_value = False
            interaction.followup = AsyncMock()
            interaction.channel = MagicMock(spec=discord.VoiceChannel)  # Not a text channel
            
            # Execute
            await ticket_commands.add_user.callback(ticket_commands, interaction, mock_user_to_add)
            
            # Verify - Should send an error message through either response or followup
            assert interaction.response.send_message.called or interaction.followup.send.called
    
    class TestRemoveUserCommand:
        """Tests for the remove user command."""
        
        @pytest.fixture
        def mock_user_to_remove(self):
            """Create a mock user to remove from ticket."""
            user = MagicMock(spec=discord.Member)
            user.id = 54321
            user.mention = "<@54321>"
            return user
        
        @pytest.mark.asyncio
        async def test_remove_user_success(self, ticket_commands, mock_interaction, mock_user_to_remove, sample_ticket):
            """Test successful user removal from ticket."""
            # Setup
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = sample_ticket
            ticket_commands.ticket_manager.remove_user_from_ticket.return_value = True
            
            # Execute
            await ticket_commands.remove_user.callback(ticket_commands, mock_interaction, mock_user_to_remove)
            
            # Verify
            ticket_commands.ticket_manager.remove_user_from_ticket.assert_called_once_with(
                mock_interaction.channel, mock_user_to_remove, mock_interaction.user
            )
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "✅ User Removed" in embed.title
        
        @pytest.mark.asyncio
        async def test_remove_user_not_in_ticket(self, ticket_commands, mock_interaction, mock_user_to_remove, sample_ticket):
            """Test removing user who is not in ticket."""
            # Setup
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = sample_ticket
            ticket_commands.ticket_manager.remove_user_from_ticket.side_effect = UserManagementError(
                "User not in ticket"
            )
            
            # Execute
            await ticket_commands.remove_user.callback(ticket_commands, mock_interaction, mock_user_to_remove)
            
            # Verify
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "❌ User Not Found" in embed.title
        
        @pytest.mark.asyncio
        async def test_remove_ticket_creator(self, ticket_commands, mock_interaction, mock_user_to_remove, sample_ticket):
            """Test removing ticket creator (should be prevented)."""
            # Setup
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = sample_ticket
            ticket_commands.ticket_manager.remove_user_from_ticket.side_effect = TicketPermissionError(
                "Cannot remove ticket creator"
            )
            
            # Execute
            await ticket_commands.remove_user.callback(ticket_commands, mock_interaction, mock_user_to_remove)
            
            # Verify
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "❌ Cannot Remove Creator" in embed.title
    
    class TestCloseTicketCommand:
        """Tests for the close ticket command."""
        
        @pytest.mark.asyncio
        async def test_close_ticket_success(self, ticket_commands, mock_interaction, sample_ticket):
            """Test successful ticket closing."""
            # Setup
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = sample_ticket
            ticket_commands.ticket_manager.close_ticket.return_value = True
            
            # Execute
            await ticket_commands.close_ticket.callback(ticket_commands, mock_interaction, "Issue resolved")
            
            # Verify
            ticket_commands.ticket_manager.close_ticket.assert_called_once_with(
                mock_interaction.channel, mock_interaction.user, "Issue resolved"
            )
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "🔒 Closing Ticket" in embed.title
        
        @pytest.mark.asyncio
        async def test_close_ticket_no_reason(self, ticket_commands, mock_interaction, sample_ticket):
            """Test closing ticket without reason."""
            # Setup
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = sample_ticket
            ticket_commands.ticket_manager.close_ticket.return_value = True
            
            # Execute
            await ticket_commands.close_ticket.callback(ticket_commands, mock_interaction)
            
            # Verify
            ticket_commands.ticket_manager.close_ticket.assert_called_once_with(
                mock_interaction.channel, mock_interaction.user, None
            )
        
        @pytest.mark.asyncio
        async def test_close_already_closed_ticket(self, ticket_commands, mock_interaction, sample_ticket):
            """Test closing already closed ticket."""
            # Setup
            sample_ticket.status = TicketStatus.CLOSED
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = sample_ticket
            
            # Execute
            await ticket_commands.close_ticket.callback(ticket_commands, mock_interaction)
            
            # Verify
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "❌ Ticket Already Closed" in embed.title
        
        @pytest.mark.asyncio
        async def test_close_ticket_error(self, ticket_commands, mock_interaction, sample_ticket):
            """Test ticket closing failure."""
            # Setup
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = sample_ticket
            ticket_commands.ticket_manager.close_ticket.side_effect = TicketClosingError(
                "Failed to generate transcript"
            )
            
            # Execute
            await ticket_commands.close_ticket.callback(ticket_commands, mock_interaction)
            
            # Verify
            # Should send closing message first, then error message
            assert mock_interaction.followup.send.call_count == 2
    
    class TestTicketInfoCommand:
        """Tests for the ticket info command."""
        
        @pytest.mark.asyncio
        async def test_ticket_info_success(self, ticket_commands, mock_interaction, sample_ticket):
            """Test successful ticket info display."""
            # Setup
            mock_creator = MagicMock()
            mock_creator.display_name = "TestUser"
            mock_creator.mention = "<@12345>"
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = sample_ticket
            ticket_commands.bot.get_user.return_value = mock_creator
            
            # Execute
            await ticket_commands.ticket_info.callback(ticket_commands, mock_interaction)
            
            # Verify
            mock_interaction.response.send_message.assert_called_once()
            call_args = mock_interaction.response.send_message.call_args
            embed = call_args[1]['embed']
            assert "📋 Ticket Information" in embed.title
            
            # Check that ticket ID is in embed fields
            field_values = [field.value for field in embed.fields]
            assert sample_ticket.ticket_id in field_values
        
        @pytest.mark.asyncio
        async def test_ticket_info_not_ticket_channel(self, ticket_commands, mock_interaction):
            """Test ticket info in non-ticket channel."""
            # Setup
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = None
            mock_interaction.response.is_done.return_value = False
            
            # Execute
            await ticket_commands.ticket_info.callback(ticket_commands, mock_interaction)
            
            # Verify - Should send an error message
            assert mock_interaction.response.send_message.called or mock_interaction.followup.send.called
        
        @pytest.mark.asyncio
        async def test_ticket_info_unknown_creator(self, ticket_commands, mock_interaction, sample_ticket):
            """Test ticket info with unknown creator."""
            # Setup
            ticket_commands.ticket_manager.get_ticket_by_channel.return_value = sample_ticket
            ticket_commands.bot.get_user.return_value = None  # Creator not found
            
            # Execute
            await ticket_commands.ticket_info.callback(ticket_commands, mock_interaction)
            
            # Verify
            mock_interaction.response.send_message.assert_called_once()
            call_args = mock_interaction.response.send_message.call_args
            embed = call_args[1]['embed']
            
            # Check that unknown user format is used
            creator_field = next(field for field in embed.fields if field.name == "Creator")
            assert f"Unknown User ({sample_ticket.creator_id})" in creator_field.value
    
    class TestCogLifecycle:
        """Tests for cog lifecycle methods."""
        
        @pytest.mark.asyncio
        async def test_cog_load_with_ticket_manager(self, mock_bot):
            """Test cog loading when ticket manager is available."""
            # Setup
            mock_ticket_manager = AsyncMock(spec=TicketManager)
            mock_bot.ticket_manager = mock_ticket_manager
            
            # Execute
            cog = TicketCommands(mock_bot)
            await cog.cog_load()
            
            # Verify
            assert cog.ticket_manager == mock_ticket_manager
        
        @pytest.mark.asyncio
        async def test_cog_load_without_ticket_manager(self, mock_bot):
            """Test cog loading when ticket manager is not available."""
            # Setup
            mock_bot.ticket_manager = None
            
            # Execute
            cog = TicketCommands(mock_bot)
            await cog.cog_load()
            
            # Verify
            assert cog.ticket_manager is None
        
        def test_validate_ticket_manager(self, ticket_commands):
            """Test ticket manager validation."""
            # Test with manager
            assert ticket_commands._validate_ticket_manager() is True
            
            # Test without manager
            ticket_commands.ticket_manager = None
            assert ticket_commands._validate_ticket_manager() is False
    
    class TestErrorHandling:
        """Tests for error handling scenarios."""
        
        @pytest.mark.asyncio
        async def test_unexpected_error_handling(self, ticket_commands, mock_interaction):
            """Test handling of unexpected errors."""
            # Setup
            ticket_commands.ticket_manager.create_ticket.side_effect = Exception("Unexpected error")
            
            # Execute
            await ticket_commands.new_ticket.callback(ticket_commands, mock_interaction)
            
            # Verify
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            embed = call_args[1]['embed']
            assert "❌ Unexpected Error" in embed.title
        
        @pytest.mark.asyncio
        async def test_database_error_handling(self, ticket_commands, mock_interaction):
            """Test handling of database-related errors."""
            # Setup
            ticket_commands.ticket_manager.get_ticket_by_channel.side_effect = Exception("Database connection failed")
            mock_interaction.response.is_done.return_value = False
            
            # Execute
            await ticket_commands.ticket_info.callback(ticket_commands, mock_interaction)
            
            # Verify - Should handle the error and send a message
            assert mock_interaction.response.send_message.called or mock_interaction.followup.send.called


@pytest.mark.asyncio
async def test_setup_function():
    """Test the setup function for the cog."""
    mock_bot = AsyncMock(spec=commands.Bot)
    
    # Import and test setup function
    from commands.ticket_commands import setup
    await setup(mock_bot)
    
    # Verify cog was added
    mock_bot.add_cog.assert_called_once()
    added_cog = mock_bot.add_cog.call_args[0][0]
    assert isinstance(added_cog, TicketCommands)


if __name__ == "__main__":
    pytest.main([__file__])