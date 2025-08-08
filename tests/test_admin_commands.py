"""
Unit tests for AdminCommands cog.

Tests administrative commands including setup, configuration management,
and ticket embed creation functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

import discord
from discord.ext import commands

from commands.admin_commands import AdminCommands, TicketCreateView
from config.config_manager import ConfigManager, GuildConfig, ConfigurationError
from commands.base_cog import PermissionError


class TestAdminCommands:
    """Test cases for AdminCommands cog."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        bot = MagicMock(spec=commands.Bot)
        bot.add_view = MagicMock()
        return bot
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        config_manager = MagicMock(spec=ConfigManager)
        return config_manager
    
    @pytest.fixture
    def mock_guild_config(self):
        """Create a mock guild configuration."""
        return GuildConfig(
            guild_id=12345,
            staff_roles=[67890],
            ticket_category=11111,
            log_channel=22222,
            embed_settings={
                'title': 'Test Tickets',
                'description': 'Test description',
                'color': 0x00ff00,
                'footer': 'Test Footer'
            }
        )
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.response.is_done.return_value = False
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.guild = MagicMock()
        interaction.guild.id = 12345
        interaction.guild.name = "Test Guild"
        interaction.guild.icon = None
        interaction.channel = MagicMock()
        interaction.user = MagicMock()
        interaction.user.guild_permissions.administrator = True
        return interaction
    
    @pytest.fixture
    def admin_cog(self, mock_bot, mock_config_manager):
        """Create AdminCommands cog instance."""
        cog = AdminCommands(mock_bot)
        cog.config_manager = mock_config_manager
        return cog
    
    def test_init(self, mock_bot):
        """Test AdminCommands initialization."""
        cog = AdminCommands(mock_bot)
        assert cog.bot == mock_bot
        assert cog.config_manager is None
    
    @pytest.mark.asyncio
    async def test_cog_load_with_config_manager(self, mock_bot):
        """Test cog loading when config manager is available."""
        mock_config_manager = MagicMock()
        mock_bot.config_manager = mock_config_manager
        
        cog = AdminCommands(mock_bot)
        await cog.cog_load()
        
        assert cog.config_manager == mock_config_manager
        mock_bot.add_view.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cog_load_without_config_manager(self, mock_bot):
        """Test cog loading when config manager is not available."""
        mock_bot.config_manager = None
        
        with patch('commands.admin_commands.ConfigManager') as mock_config_class:
            mock_config_instance = MagicMock()
            mock_config_class.return_value = mock_config_instance
            
            cog = AdminCommands(mock_bot)
            await cog.cog_load()
            
            assert cog.config_manager == mock_config_instance
            mock_bot.add_view.assert_called_once()
    
    def test_validate_config_manager_true(self, admin_cog):
        """Test config manager validation when available."""
        assert admin_cog._validate_config_manager() is True
    
    def test_validate_config_manager_false(self, mock_bot):
        """Test config manager validation when not available."""
        cog = AdminCommands(mock_bot)
        cog.config_manager = None
        assert cog._validate_config_manager() is False


class TestSetupCommand:
    """Test cases for the setup command."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        bot = MagicMock(spec=commands.Bot)
        bot.add_view = MagicMock()
        return bot
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        config_manager = MagicMock(spec=ConfigManager)
        return config_manager
    
    @pytest.fixture
    def mock_guild_config(self):
        """Create a mock guild configuration."""
        return GuildConfig(
            guild_id=12345,
            staff_roles=[67890],
            ticket_category=11111,
            log_channel=22222,
            embed_settings={
                'title': 'Test Tickets',
                'description': 'Test description',
                'color': 0x00ff00,
                'footer': 'Test Footer'
            }
        )
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.response.is_done.return_value = False
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.guild = MagicMock()
        interaction.guild.id = 12345
        interaction.guild.name = "Test Guild"
        interaction.guild.icon = None
        interaction.channel = MagicMock()
        interaction.user = MagicMock()
        interaction.user.guild_permissions.administrator = True
        return interaction
    
    @pytest.fixture
    def admin_cog(self, mock_bot, mock_config_manager):
        """Create AdminCommands cog instance."""
        cog = AdminCommands(mock_bot)
        cog.config_manager = mock_config_manager
        return cog
    
    @pytest.fixture
    def mock_staff_role(self):
        """Create a mock staff role."""
        role = MagicMock(spec=discord.Role)
        role.id = 67890
        role.mention = "<@&67890>"
        return role
    
    @pytest.fixture
    def mock_ticket_category(self):
        """Create a mock ticket category."""
        category = MagicMock(spec=discord.CategoryChannel)
        category.id = 11111
        category.mention = "<#11111>"
        return category
    
    @pytest.fixture
    def mock_log_channel(self):
        """Create a mock log channel."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 22222
        channel.mention = "<#22222>"
        return channel
    
    @pytest.mark.asyncio
    async def test_setup_success_with_log_channel(
        self, admin_cog, mock_interaction, mock_guild_config,
        mock_staff_role, mock_ticket_category, mock_log_channel
    ):
        """Test successful setup with log channel."""
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.setup.callback(
            admin_cog, mock_interaction, mock_staff_role, mock_ticket_category, mock_log_channel
        )
        
        # Verify configuration was updated
        assert mock_guild_config.staff_roles == [67890]
        assert mock_guild_config.ticket_category == 11111
        assert mock_guild_config.log_channel == 22222
        assert 'title' in mock_guild_config.embed_settings
        
        # Verify config manager calls
        admin_cog.config_manager.set_guild_config.assert_called_once_with(mock_guild_config)
        admin_cog.config_manager.save_configuration.assert_called_once()
        
        # Verify response
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_setup_success_without_log_channel(
        self, admin_cog, mock_interaction, mock_guild_config,
        mock_staff_role, mock_ticket_category
    ):
        """Test successful setup without log channel."""
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.setup.callback(
            admin_cog, mock_interaction, mock_staff_role, mock_ticket_category, None
        )
        
        # Verify configuration was updated
        assert mock_guild_config.staff_roles == [67890]
        assert mock_guild_config.ticket_category == 11111
        # log_channel should remain unchanged (22222 from fixture)
        
        # Verify config manager calls
        admin_cog.config_manager.set_guild_config.assert_called_once_with(mock_guild_config)
        admin_cog.config_manager.save_configuration.assert_called_once()
        
        # Verify response
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_setup_config_manager_unavailable(
        self, mock_bot, mock_interaction, mock_staff_role, mock_ticket_category
    ):
        """Test setup when config manager is unavailable."""
        cog = AdminCommands(mock_bot)
        cog.config_manager = None
        
        await cog.setup.callback(cog, mock_interaction, mock_staff_role, mock_ticket_category, None)
        
        # Should send error message
        mock_interaction.response.send_message.assert_called_once()
        args, kwargs = mock_interaction.response.send_message.call_args
        assert kwargs['ephemeral'] is True
        assert "Configuration Unavailable" in str(args[0])
    
    @pytest.mark.asyncio
    async def test_setup_configuration_error(
        self, admin_cog, mock_interaction, mock_guild_config,
        mock_staff_role, mock_ticket_category
    ):
        """Test setup with configuration error."""
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        admin_cog.config_manager.save_configuration.side_effect = ConfigurationError("Save failed")
        
        await admin_cog.setup.callback(
            admin_cog, mock_interaction, mock_staff_role, mock_ticket_category, None
        )
        
        # Should send error message
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        assert kwargs['ephemeral'] is True
        assert "Configuration Error" in str(args[0])


class TestTicketEmbedCommand:
    """Test cases for the ticket embed command."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        bot = MagicMock(spec=commands.Bot)
        bot.add_view = MagicMock()
        return bot
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        config_manager = MagicMock(spec=ConfigManager)
        return config_manager
    
    @pytest.fixture
    def mock_guild_config(self):
        """Create a mock guild configuration."""
        return GuildConfig(
            guild_id=12345,
            staff_roles=[67890],
            ticket_category=11111,
            log_channel=22222,
            embed_settings={
                'title': 'Test Tickets',
                'description': 'Test description',
                'color': 0x00ff00,
                'footer': 'Test Footer'
            }
        )
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.response.is_done.return_value = False
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.guild = MagicMock()
        interaction.guild.id = 12345
        interaction.guild.name = "Test Guild"
        interaction.guild.icon = None
        interaction.channel = MagicMock()
        interaction.user = MagicMock()
        interaction.user.guild_permissions.administrator = True
        return interaction
    
    @pytest.fixture
    def admin_cog(self, mock_bot, mock_config_manager):
        """Create AdminCommands cog instance."""
        cog = AdminCommands(mock_bot)
        cog.config_manager = mock_config_manager
        return cog
    
    @pytest.fixture
    def mock_text_channel(self):
        """Create a mock text channel."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.mention = "<#33333>"
        channel.send = AsyncMock()
        return channel
    
    @pytest.fixture
    def mock_message(self):
        """Create a mock message."""
        message = MagicMock()
        message.jump_url = "https://discord.com/channels/123/456/789"
        return message
    
    @pytest.mark.asyncio
    async def test_send_ticket_embed_success_default_channel(
        self, admin_cog, mock_interaction, mock_guild_config, mock_text_channel, mock_message
    ):
        """Test successful embed sending to default channel."""
        mock_interaction.channel = mock_text_channel
        mock_text_channel.send.return_value = mock_message
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.send_ticket_embed.callback(admin_cog, mock_interaction)
        
        # Verify embed was sent
        mock_text_channel.send.assert_called_once()
        args, kwargs = mock_text_channel.send.call_args
        assert 'embed' in kwargs
        assert 'view' in kwargs
        
        # Verify response
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_ticket_embed_success_custom_channel(
        self, admin_cog, mock_interaction, mock_guild_config, mock_text_channel, mock_message
    ):
        """Test successful embed sending to custom channel."""
        mock_text_channel.send.return_value = mock_message
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.send_ticket_embed.callback(admin_cog, mock_interaction, channel=mock_text_channel)
        
        # Verify embed was sent to specified channel
        mock_text_channel.send.assert_called_once()
        
        # Verify response
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_ticket_embed_custom_title_description(
        self, admin_cog, mock_interaction, mock_guild_config, mock_text_channel, mock_message
    ):
        """Test embed sending with custom title and description."""
        mock_interaction.channel = mock_text_channel
        mock_text_channel.send.return_value = mock_message
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        custom_title = "Custom Support"
        custom_description = "Custom description text"
        
        await admin_cog.send_ticket_embed.callback(
            admin_cog, mock_interaction, title=custom_title, description=custom_description
        )
        
        # Verify embed was sent with custom content
        mock_text_channel.send.assert_called_once()
        args, kwargs = mock_text_channel.send.call_args
        embed = kwargs['embed']
        assert embed.title == custom_title
        assert embed.description == custom_description
    
    @pytest.mark.asyncio
    async def test_send_ticket_embed_invalid_channel(
        self, admin_cog, mock_interaction, mock_guild_config
    ):
        """Test embed sending to invalid channel type."""
        mock_voice_channel = MagicMock(spec=discord.VoiceChannel)
        mock_interaction.channel = mock_voice_channel
        
        await admin_cog.send_ticket_embed.callback(admin_cog, mock_interaction)
        
        # Should send error message
        mock_interaction.response.send_message.assert_called_once()
        args, kwargs = mock_interaction.response.send_message.call_args
        assert kwargs['ephemeral'] is True
        assert "Invalid Channel" in str(args[0])
    
    @pytest.mark.asyncio
    async def test_send_ticket_embed_permission_denied(
        self, admin_cog, mock_interaction, mock_guild_config, mock_text_channel
    ):
        """Test embed sending with permission error."""
        mock_interaction.channel = mock_text_channel
        mock_text_channel.send.side_effect = discord.Forbidden(MagicMock(), "Forbidden")
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.send_ticket_embed.callback(admin_cog, mock_interaction)
        
        # Should send error message
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        assert kwargs['ephemeral'] is True
        assert "Permission Denied" in str(args[0])


class TestConfigCommand:
    """Test cases for the config command."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        bot = MagicMock(spec=commands.Bot)
        bot.add_view = MagicMock()
        return bot
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        config_manager = MagicMock(spec=ConfigManager)
        return config_manager
    
    @pytest.fixture
    def mock_guild_config(self):
        """Create a mock guild configuration."""
        return GuildConfig(
            guild_id=12345,
            staff_roles=[67890],
            ticket_category=11111,
            log_channel=22222,
            embed_settings={
                'title': 'Test Tickets',
                'description': 'Test description',
                'color': 0x00ff00,
                'footer': 'Test Footer'
            }
        )
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.response.is_done.return_value = False
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.guild = MagicMock()
        interaction.guild.id = 12345
        interaction.guild.name = "Test Guild"
        interaction.guild.icon = None
        interaction.channel = MagicMock()
        interaction.user = MagicMock()
        interaction.user.guild_permissions.administrator = True
        return interaction
    
    @pytest.fixture
    def admin_cog(self, mock_bot, mock_config_manager):
        """Create AdminCommands cog instance."""
        cog = AdminCommands(mock_bot)
        cog.config_manager = mock_config_manager
        return cog
    
    @pytest.mark.asyncio
    async def test_config_view(self, admin_cog, mock_interaction, mock_guild_config):
        """Test viewing configuration."""
        # Setup mock role and channels
        mock_role = MagicMock()
        mock_role.mention = "<@&67890>"
        mock_category = MagicMock()
        mock_category.mention = "<#11111>"
        mock_log_channel = MagicMock()
        mock_log_channel.mention = "<#22222>"
        
        mock_interaction.guild.get_role.return_value = mock_role
        mock_interaction.guild.get_channel.side_effect = lambda x: {
            11111: mock_category,
            22222: mock_log_channel
        }.get(x)
        
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.config.callback(admin_cog, mock_interaction, "view")
        
        # Verify response
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
        
        # Check embed content
        args, kwargs = mock_interaction.followup.send.call_args
        embed = args[0]
        assert "Server Configuration" in embed.title
    
    @pytest.mark.asyncio
    async def test_config_add_staff_role_success(
        self, admin_cog, mock_interaction, mock_guild_config
    ):
        """Test adding staff role successfully."""
        mock_role = MagicMock()
        mock_role.id = 99999
        mock_role.mention = "<@&99999>"
        mock_interaction.guild.get_role.return_value = mock_role
        
        # Remove existing role from config for this test
        mock_guild_config.staff_roles = []
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.config(mock_interaction, "add-staff-role", "99999")
        
        # Verify role was added
        assert 99999 in mock_guild_config.staff_roles
        admin_cog.config_manager.set_guild_config.assert_called_once()
        admin_cog.config_manager.save_configuration.assert_called_once()
        
        # Verify success response
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        assert "Staff Role Added" in str(args[0])
    
    @pytest.mark.asyncio
    async def test_config_add_staff_role_already_exists(
        self, admin_cog, mock_interaction, mock_guild_config
    ):
        """Test adding staff role that already exists."""
        mock_role = MagicMock()
        mock_role.id = 67890  # Already in mock_guild_config
        mock_role.mention = "<@&67890>"
        mock_interaction.guild.get_role.return_value = mock_role
        
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.config(mock_interaction, "add-staff-role", "67890")
        
        # Should send error message
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        assert kwargs['ephemeral'] is True
        assert "Role Already Added" in str(args[0])
    
    @pytest.mark.asyncio
    async def test_config_add_staff_role_not_found(
        self, admin_cog, mock_interaction, mock_guild_config
    ):
        """Test adding staff role that doesn't exist."""
        mock_interaction.guild.get_role.return_value = None
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.config(mock_interaction, "add-staff-role", "99999")
        
        # Should send error message
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        assert kwargs['ephemeral'] is True
        assert "Role Not Found" in str(args[0])
    
    @pytest.mark.asyncio
    async def test_config_remove_staff_role_success(
        self, admin_cog, mock_interaction, mock_guild_config
    ):
        """Test removing staff role successfully."""
        mock_role = MagicMock()
        mock_role.mention = "<@&67890>"
        mock_interaction.guild.get_role.return_value = mock_role
        
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.config(mock_interaction, "remove-staff-role", "67890")
        
        # Verify role was removed
        assert 67890 not in mock_guild_config.staff_roles
        admin_cog.config_manager.set_guild_config.assert_called_once()
        admin_cog.config_manager.save_configuration.assert_called_once()
        
        # Verify success response
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        assert "Staff Role Removed" in str(args[0])
    
    @pytest.mark.asyncio
    async def test_config_set_category_success(
        self, admin_cog, mock_interaction, mock_guild_config
    ):
        """Test setting ticket category successfully."""
        mock_category = MagicMock(spec=discord.CategoryChannel)
        mock_category.id = 55555
        mock_category.mention = "<#55555>"
        mock_interaction.guild.get_channel.return_value = mock_category
        
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.config(mock_interaction, "set-category", "55555")
        
        # Verify category was set
        assert mock_guild_config.ticket_category == 55555
        admin_cog.config_manager.set_guild_config.assert_called_once()
        admin_cog.config_manager.save_configuration.assert_called_once()
        
        # Verify success response
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        assert "Ticket Category Set" in str(args[0])
    
    @pytest.mark.asyncio
    async def test_config_set_log_channel_success(
        self, admin_cog, mock_interaction, mock_guild_config
    ):
        """Test setting log channel successfully."""
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.id = 66666
        mock_channel.mention = "<#66666>"
        mock_interaction.guild.get_channel.return_value = mock_channel
        
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.config(mock_interaction, "set-log-channel", "66666")
        
        # Verify log channel was set
        assert mock_guild_config.log_channel == 66666
        admin_cog.config_manager.set_guild_config.assert_called_once()
        admin_cog.config_manager.save_configuration.assert_called_once()
        
        # Verify success response
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        assert "Log Channel Set" in str(args[0])
    
    @pytest.mark.asyncio
    async def test_config_clear_log_channel(
        self, admin_cog, mock_interaction, mock_guild_config
    ):
        """Test clearing log channel."""
        admin_cog.config_manager.get_guild_config.return_value = mock_guild_config
        
        await admin_cog.config(mock_interaction, "clear-log-channel")
        
        # Verify log channel was cleared
        assert mock_guild_config.log_channel is None
        admin_cog.config_manager.set_guild_config.assert_called_once()
        admin_cog.config_manager.save_configuration.assert_called_once()
        
        # Verify success response
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        assert "Log Channel Cleared" in str(args[0])


class TestTicketCreateView:
    """Test cases for TicketCreateView."""
    
    @pytest.fixture
    def mock_ticket_manager(self):
        """Create a mock ticket manager."""
        manager = MagicMock()
        manager.create_ticket = AsyncMock()
        return manager
    
    @pytest.fixture
    def mock_ticket(self):
        """Create a mock ticket."""
        ticket = MagicMock()
        ticket.ticket_id = "TICKET-001"
        ticket.channel_id = 77777
        return ticket
    
    @pytest.fixture
    def mock_interaction_button(self):
        """Create a mock interaction for button clicks."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.client = MagicMock()
        interaction.user = MagicMock()
        interaction.guild = MagicMock()
        return interaction
    
    @pytest.mark.asyncio
    async def test_create_ticket_button_success(
        self, mock_interaction_button, mock_ticket_manager, mock_ticket
    ):
        """Test successful ticket creation from button."""
        # Setup mocks
        mock_channel = MagicMock()
        mock_channel.mention = "<#77777>"
        
        mock_interaction_button.client.ticket_manager = mock_ticket_manager
        mock_interaction_button.client.get_channel.return_value = mock_channel
        mock_ticket_manager.create_ticket.return_value = mock_ticket
        
        # Create view and simulate button click
        view = TicketCreateView()
        button = view.children[0]  # Get the create ticket button
        
        await button.callback(mock_interaction_button)
        
        # Verify ticket creation was called
        mock_ticket_manager.create_ticket.assert_called_once_with(
            mock_interaction_button.user, mock_interaction_button.guild
        )
        
        # Verify response
        mock_interaction_button.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_button.followup.send.assert_called_once()
        
        # Check success message
        args, kwargs = mock_interaction_button.followup.send.call_args
        embed = args[0]
        assert "Ticket Created" in embed.title
        assert "TICKET-001" in embed.description
    
    @pytest.mark.asyncio
    async def test_create_ticket_button_no_ticket_manager(self, mock_interaction_button):
        """Test button click when ticket manager is unavailable."""
        mock_interaction_button.client.ticket_manager = None
        
        view = TicketCreateView()
        button = view.children[0]
        
        await button.callback(mock_interaction_button)
        
        # Should send error message
        mock_interaction_button.response.send_message.assert_called_once()
        args, kwargs = mock_interaction_button.response.send_message.call_args
        assert kwargs['ephemeral'] is True
        assert "Service Unavailable" in str(args[0])
    
    @pytest.mark.asyncio
    async def test_create_ticket_button_already_has_ticket(
        self, mock_interaction_button, mock_ticket_manager
    ):
        """Test button click when user already has a ticket."""
        mock_interaction_button.client.ticket_manager = mock_ticket_manager
        mock_ticket_manager.create_ticket.side_effect = Exception("User already has an active ticket")
        
        view = TicketCreateView()
        button = view.children[0]
        
        await button.callback(mock_interaction_button)
        
        # Should send appropriate error message
        mock_interaction_button.followup.send.assert_called_once()
        args, kwargs = mock_interaction_button.followup.send.call_args
        embed = args[0]
        assert "Ticket Already Exists" in embed.title
    
    @pytest.mark.asyncio
    async def test_create_ticket_button_creation_failed(
        self, mock_interaction_button, mock_ticket_manager
    ):
        """Test button click when ticket creation fails."""
        mock_interaction_button.client.ticket_manager = mock_ticket_manager
        mock_ticket_manager.create_ticket.side_effect = Exception("Database error")
        
        view = TicketCreateView()
        button = view.children[0]
        
        await button.callback(mock_interaction_button)
        
        # Should send generic error message
        mock_interaction_button.followup.send.assert_called_once()
        args, kwargs = mock_interaction_button.followup.send.call_args
        embed = args[0]
        assert "Ticket Creation Failed" in embed.title


class TestPermissionValidation:
    """Test cases for permission validation in admin commands."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        bot = MagicMock(spec=commands.Bot)
        bot.add_view = MagicMock()
        return bot
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        config_manager = MagicMock(spec=ConfigManager)
        return config_manager
    
    @pytest.fixture
    def admin_cog(self, mock_bot, mock_config_manager):
        """Create AdminCommands cog instance."""
        cog = AdminCommands(mock_bot)
        cog.config_manager = mock_config_manager
        return cog
    
    @pytest.fixture
    def mock_non_admin_interaction(self):
        """Create a mock interaction for non-admin user."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.guild_permissions.administrator = False
        interaction.guild = MagicMock()
        return interaction
    
    @pytest.mark.asyncio
    async def test_setup_permission_denied(self, admin_cog, mock_non_admin_interaction):
        """Test setup command with insufficient permissions."""
        # Mock the permission check to return False
        with patch.object(admin_cog, 'check_admin_permissions', return_value=False):
            mock_role = MagicMock()
            mock_category = MagicMock()
            
            await admin_cog.setup(mock_non_admin_interaction, mock_role, mock_category)
            
            # Should send permission denied message
            mock_non_admin_interaction.response.send_message.assert_called_once()
            args, kwargs = mock_non_admin_interaction.response.send_message.call_args
            assert kwargs['ephemeral'] is True
            assert "Permission Denied" in str(args[0])
    
    @pytest.mark.asyncio
    async def test_ticket_embed_permission_denied(self, admin_cog, mock_non_admin_interaction):
        """Test ticket embed command with insufficient permissions."""
        with patch.object(admin_cog, 'check_admin_permissions', return_value=False):
            await admin_cog.send_ticket_embed(mock_non_admin_interaction)
            
            # Should send permission denied message
            mock_non_admin_interaction.response.send_message.assert_called_once()
            args, kwargs = mock_non_admin_interaction.response.send_message.call_args
            assert kwargs['ephemeral'] is True
            assert "Permission Denied" in str(args[0])
    
    @pytest.mark.asyncio
    async def test_config_permission_denied(self, admin_cog, mock_non_admin_interaction):
        """Test config command with insufficient permissions."""
        with patch.object(admin_cog, 'check_admin_permissions', return_value=False):
            await admin_cog.config(mock_non_admin_interaction, "view")
            
            # Should send permission denied message
            mock_non_admin_interaction.response.send_message.assert_called_once()
            args, kwargs = mock_non_admin_interaction.response.send_message.call_args
            assert kwargs['ephemeral'] is True
            assert "Permission Denied" in str(args[0])


if __name__ == "__main__":
    pytest.main([__file__])