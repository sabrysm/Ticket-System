"""
Integration tests for the complete ticket creation workflow.

Tests the end-to-end ticket creation process including button interactions,
channel creation, permissions setup, and user notifications.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from datetime import datetime

from commands.admin_commands import TicketCreateView
from core.ticket_manager import TicketManager, TicketCreationError, PermissionError
from models.ticket import Ticket, TicketStatus
from config.config_manager import GuildConfig


class TestTicketCreationWorkflow:
    """Integration tests for the complete ticket creation workflow."""
    
    @pytest.fixture
    def mock_guild(self):
        """Create a mock Discord guild."""
        guild = MagicMock(spec=discord.Guild)
        guild.id = 12345
        guild.name = "Test Guild"
        guild.me = MagicMock()
        guild.me.id = 98765
        guild.default_role = MagicMock()
        guild.default_role.id = 11111
        guild.icon = None
        guild.get_role = MagicMock(return_value=None)
        guild.get_channel = MagicMock(return_value=None)
        guild.create_text_channel = AsyncMock()
        return guild
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock Discord user."""
        user = MagicMock(spec=discord.Member)
        user.id = 54321
        user.display_name = "TestUser"
        user.mention = "<@54321>"
        user.roles = []
        user.guild = MagicMock()
        return user
    
    @pytest.fixture
    def mock_channel(self):
        """Create a mock Discord text channel."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 77777
        channel.name = "ticket-ABC12345"
        channel.mention = "<#77777>"
        channel.send = AsyncMock()
        channel.set_permissions = AsyncMock()
        channel.guild = MagicMock()
        return channel
    
    @pytest.fixture
    def mock_interaction(self, mock_user, mock_guild):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = mock_user
        interaction.guild = mock_guild
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.client = MagicMock()
        return interaction
    
    @pytest.fixture
    def mock_database_adapter(self):
        """Create a mock database adapter."""
        adapter = MagicMock()
        adapter.get_active_ticket_for_user = AsyncMock(return_value=None)
        adapter.get_ticket = AsyncMock(return_value=None)
        adapter.create_ticket = AsyncMock()
        adapter.get_tickets_by_guild = AsyncMock(return_value=[])
        return adapter
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock configuration manager."""
        config_manager = MagicMock()
        guild_config = GuildConfig(
            guild_id=12345,
            staff_roles=[67890],
            ticket_category=11111,
            log_channel=22222,
            embed_settings={
                'title': '🎫 Support Tickets',
                'description': 'Click the button below to create a new support ticket.',
                'color': 0x00ff00,
                'footer': 'Ticket System'
            }
        )
        config_manager.get_guild_config.return_value = guild_config
        return config_manager
    
    @pytest.fixture
    def ticket_manager(self, mock_database_adapter, mock_config_manager):
        """Create a ticket manager instance."""
        bot = MagicMock()
        bot.get_channel = MagicMock()
        return TicketManager(bot, mock_database_adapter, mock_config_manager)
    
    @pytest.mark.asyncio
    async def test_complete_ticket_creation_workflow_success(
        self, mock_interaction, mock_channel, mock_database_adapter, 
        mock_config_manager, ticket_manager
    ):
        """Test the complete successful ticket creation workflow."""
        # Setup mocks
        mock_interaction.client.ticket_manager = ticket_manager
        mock_interaction.client.get_channel.return_value = mock_channel
        mock_interaction.guild.create_text_channel.return_value = mock_channel
        
        # Mock ticket creation
        expected_ticket = Ticket(
            ticket_id="ABC12345",
            guild_id=12345,
            channel_id=77777,
            creator_id=54321,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow(),
            participants=[54321]
        )
        
        with patch.object(ticket_manager, '_generate_ticket_id', return_value="ABC12345"):
            with patch.object(ticket_manager, 'database') as mock_db:
                mock_db.get_active_ticket_for_user.return_value = None
                mock_db.get_ticket.return_value = None
                mock_db.create_ticket = AsyncMock()
                
                # Create view and simulate button click
                view = TicketCreateView()
                button = view.children[0]
                
                await button.callback(mock_interaction)
                
                # Verify interaction flow
                mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
                
                # Verify channel creation was attempted
                mock_interaction.guild.create_text_channel.assert_called_once()
                
                # Verify channel permissions were set
                mock_channel.set_permissions.assert_called()
                
                # Verify welcome message was sent to channel
                mock_channel.send.assert_called_once()
                
                # Verify database ticket creation
                mock_db.create_ticket.assert_called_once()
                
                # Verify success response to user
                mock_interaction.followup.send.assert_called_once()
                args, kwargs = mock_interaction.followup.send.call_args
                embed = kwargs['embed']
                assert "Ticket Created" in embed.title
                assert "ABC12345" in embed.description
                assert kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_ticket_creation_workflow_duplicate_prevention(
        self, mock_interaction, mock_database_adapter, ticket_manager
    ):
        """Test that duplicate ticket creation is prevented."""
        # Setup existing ticket
        existing_ticket = Ticket(
            ticket_id="EXISTING1",
            guild_id=12345,
            channel_id=88888,
            creator_id=54321,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow(),
            participants=[54321]
        )
        
        mock_interaction.client.ticket_manager = ticket_manager
        
        with patch.object(ticket_manager, 'database') as mock_db:
            mock_db.get_active_ticket_for_user.return_value = existing_ticket
            
            # Create view and simulate button click
            view = TicketCreateView()
            button = view.children[0]
            
            await button.callback(mock_interaction)
            
            # Verify appropriate error response
            mock_interaction.followup.send.assert_called_once()
            args, kwargs = mock_interaction.followup.send.call_args
            embed = kwargs['embed']
            assert "Ticket Already Exists" in embed.title
            assert kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_ticket_creation_workflow_channel_creation_failure(
        self, mock_interaction, mock_database_adapter, ticket_manager
    ):
        """Test handling of channel creation failure."""
        mock_interaction.client.ticket_manager = ticket_manager
        mock_interaction.guild.create_text_channel.side_effect = discord.Forbidden(
            MagicMock(), "Insufficient permissions"
        )
        
        with patch.object(ticket_manager, 'database') as mock_db:
            mock_db.get_active_ticket_for_user.return_value = None
            mock_db.get_ticket.return_value = None
            
            # Create view and simulate button click
            view = TicketCreateView()
            button = view.children[0]
            
            await button.callback(mock_interaction)
            
            # Verify error response
            mock_interaction.followup.send.assert_called_once()
            args, kwargs = mock_interaction.followup.send.call_args
            embed = kwargs['embed']
            assert "Ticket Creation Failed" in embed.title
            assert kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_ticket_creation_workflow_database_failure(
        self, mock_interaction, mock_channel, mock_database_adapter, ticket_manager
    ):
        """Test handling of database failure during ticket creation."""
        mock_interaction.client.ticket_manager = ticket_manager
        mock_interaction.client.get_channel.return_value = mock_channel
        mock_interaction.guild.create_text_channel.return_value = mock_channel
        
        with patch.object(ticket_manager, '_generate_ticket_id', return_value="ABC12345"):
            with patch.object(ticket_manager, 'database') as mock_db:
                mock_db.get_active_ticket_for_user.return_value = None
                mock_db.get_ticket.return_value = None
                mock_db.create_ticket.side_effect = Exception("Database connection failed")
                
                # Create view and simulate button click
                view = TicketCreateView()
                button = view.children[0]
                
                await button.callback(mock_interaction)
                
                # Verify error response
                mock_interaction.followup.send.assert_called_once()
                args, kwargs = mock_interaction.followup.send.call_args
                embed = kwargs['embed']
                assert "Ticket Creation Failed" in embed.title
                assert kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_ticket_creation_workflow_proper_permissions(
        self, mock_interaction, mock_channel, mock_database_adapter, 
        mock_config_manager, ticket_manager
    ):
        """Test that proper permissions are set on created ticket channels."""
        # Setup staff role
        staff_role = MagicMock()
        staff_role.id = 67890
        mock_interaction.guild.get_role.return_value = staff_role
        
        mock_interaction.client.ticket_manager = ticket_manager
        mock_interaction.client.get_channel.return_value = mock_channel
        mock_interaction.guild.create_text_channel.return_value = mock_channel
        
        with patch.object(ticket_manager, '_generate_ticket_id', return_value="ABC12345"):
            with patch.object(ticket_manager, 'database') as mock_db:
                mock_db.get_active_ticket_for_user.return_value = None
                mock_db.get_ticket.return_value = None
                mock_db.create_ticket = AsyncMock()
                
                # Create view and simulate button click
                view = TicketCreateView()
                button = view.children[0]
                
                await button.callback(mock_interaction)
                
                # Verify channel creation with proper overwrites
                create_call = mock_interaction.guild.create_text_channel.call_args
                overwrites = create_call[1]['overwrites']
                
                # Check that default role is denied access
                assert mock_interaction.guild.default_role in overwrites
                default_perms = overwrites[mock_interaction.guild.default_role]
                assert default_perms.read_messages is False
                
                # Check that creator has access
                assert mock_interaction.user in overwrites
                creator_perms = overwrites[mock_interaction.user]
                assert creator_perms.read_messages is True
                assert creator_perms.send_messages is True
                
                # Check that bot has management permissions
                assert mock_interaction.guild.me in overwrites
                bot_perms = overwrites[mock_interaction.guild.me]
                assert bot_perms.read_messages is True
                assert bot_perms.manage_messages is True
    
    @pytest.mark.asyncio
    async def test_ticket_creation_workflow_welcome_message(
        self, mock_interaction, mock_channel, mock_database_adapter, ticket_manager
    ):
        """Test that a proper welcome message is sent to the created ticket channel."""
        mock_interaction.client.ticket_manager = ticket_manager
        mock_interaction.client.get_channel.return_value = mock_channel
        mock_interaction.guild.create_text_channel.return_value = mock_channel
        
        with patch.object(ticket_manager, '_generate_ticket_id', return_value="ABC12345"):
            with patch.object(ticket_manager, 'database') as mock_db:
                mock_db.get_active_ticket_for_user.return_value = None
                mock_db.get_ticket.return_value = None
                mock_db.create_ticket = AsyncMock()
                
                # Create view and simulate button click
                view = TicketCreateView()
                button = view.children[0]
                
                await button.callback(mock_interaction)
                
                # Verify welcome message was sent
                mock_channel.send.assert_called_once()
                args, kwargs = mock_channel.send.call_args
                embed = args[0]
                
                # Check welcome message content
                assert "Ticket ABC12345" in embed.title
                assert mock_interaction.user.mention in embed.description
                assert "support ticket has been created" in embed.description
                assert embed.color == discord.Color.green()
                
                # Check embed fields
                fields = {field.name: field.value for field in embed.fields}
                assert "Ticket ID" in fields
                assert fields["Ticket ID"] == "ABC12345"
                assert "Created by" in fields
                assert fields["Created by"] == mock_interaction.user.mention
    
    @pytest.mark.asyncio
    async def test_ticket_creation_workflow_no_ticket_manager(self, mock_interaction):
        """Test handling when ticket manager is not available."""
        mock_interaction.client.ticket_manager = None
        
        # Create view and simulate button click
        view = TicketCreateView()
        button = view.children[0]
        
        await button.callback(mock_interaction)
        
        # Verify service unavailable response
        mock_interaction.response.send_message.assert_called_once()
        args, kwargs = mock_interaction.response.send_message.call_args
        embed = kwargs['embed']
        assert "Service Unavailable" in embed.title
        assert kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_ticket_creation_workflow_unique_id_generation(
        self, mock_interaction, mock_channel, mock_database_adapter, ticket_manager
    ):
        """Test that unique ticket IDs are generated even with collisions."""
        mock_interaction.client.ticket_manager = ticket_manager
        mock_interaction.client.get_channel.return_value = mock_channel
        mock_interaction.guild.create_text_channel.return_value = mock_channel
        
        # Mock ID generation with collision on first attempt
        with patch.object(ticket_manager, '_generate_ticket_id', side_effect=["COLLISION", "UNIQUE123"]):
            with patch.object(ticket_manager, 'database') as mock_db:
                mock_db.get_active_ticket_for_user.return_value = None
                # First call returns existing ticket (collision), second returns None
                mock_db.get_ticket.side_effect = [MagicMock(), None]
                mock_db.create_ticket = AsyncMock()
                
                # Create view and simulate button click
                view = TicketCreateView()
                button = view.children[0]
                
                await button.callback(mock_interaction)
                
                # Verify that get_ticket was called twice (collision handling)
                assert mock_db.get_ticket.call_count == 2
                
                # Verify success response with unique ID
                mock_interaction.followup.send.assert_called_once()
                args, kwargs = mock_interaction.followup.send.call_args
                embed = kwargs['embed']
                assert "UNIQUE123" in embed.description