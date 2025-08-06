"""
Unit tests for base cog functionality and command infrastructure.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import discord
from discord.ext import commands

# Import the modules to test
from commands.base_cog import (
    BaseCog, 
    TicketBotError, 
    PermissionError, 
    ConfigurationError,
    require_staff_role,
    require_admin_role,
    handle_errors
)


class TestBaseCog:
    """Test cases for BaseCog class."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        bot = Mock(spec=commands.Bot)
        bot.config_manager = None
        return bot
    
    @pytest.fixture
    def base_cog(self, mock_bot):
        """Create a BaseCog instance for testing."""
        return BaseCog(mock_bot)
    
    @pytest.fixture
    def mock_guild(self):
        """Create a mock guild."""
        guild = Mock(spec=discord.Guild)
        guild.id = 12345
        return guild
    
    @pytest.fixture
    def mock_user_admin(self):
        """Create a mock user with admin permissions."""
        user = Mock(spec=discord.Member)
        user.id = 67890
        user.guild_permissions.administrator = True
        user.guild_permissions.manage_channels = False
        user.roles = []
        return user
    
    @pytest.fixture
    def mock_user_staff(self):
        """Create a mock user with staff role."""
        user = Mock(spec=discord.Member)
        user.id = 11111
        user.guild_permissions.administrator = False
        user.guild_permissions.manage_channels = True
        
        # Mock staff role
        staff_role = Mock()
        staff_role.name = "Staff"
        staff_role.id = 22222
        user.roles = [staff_role]
        return user
    
    @pytest.fixture
    def mock_user_regular(self):
        """Create a mock regular user."""
        user = Mock(spec=discord.Member)
        user.id = 33333
        user.guild_permissions.administrator = False
        user.guild_permissions.manage_channels = False
        user.roles = []
        return user
    
    @pytest.fixture
    def mock_interaction(self, mock_user_regular, mock_guild):
        """Create a mock interaction."""
        interaction = Mock(spec=discord.Interaction)
        interaction.user = mock_user_regular
        interaction.guild = mock_guild
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.followup = Mock()
        interaction.followup.send = AsyncMock()
        return interaction
    
    def test_base_cog_initialization(self, mock_bot):
        """Test BaseCog initialization."""
        cog = BaseCog(mock_bot)
        assert cog.bot == mock_bot
        assert cog.logger is not None
    
    @pytest.mark.asyncio
    async def test_check_staff_permissions_admin_user(self, base_cog, mock_user_admin, mock_guild):
        """Test staff permission check for admin user."""
        result = await base_cog.check_staff_permissions(mock_user_admin, mock_guild)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_check_staff_permissions_staff_role(self, base_cog, mock_user_staff, mock_guild):
        """Test staff permission check for user with staff role."""
        result = await base_cog.check_staff_permissions(mock_user_staff, mock_guild)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_check_staff_permissions_regular_user(self, base_cog, mock_user_regular, mock_guild):
        """Test staff permission check for regular user."""
        result = await base_cog.check_staff_permissions(mock_user_regular, mock_guild)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_check_admin_permissions_admin_user(self, base_cog, mock_user_admin, mock_guild):
        """Test admin permission check for admin user."""
        result = await base_cog.check_admin_permissions(mock_user_admin, mock_guild)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_check_admin_permissions_regular_user(self, base_cog, mock_user_regular, mock_guild):
        """Test admin permission check for regular user."""
        result = await base_cog.check_admin_permissions(mock_user_regular, mock_guild)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_error_embed(self, base_cog, mock_interaction):
        """Test sending error embed."""
        await base_cog.send_error_embed(
            mock_interaction, 
            "Test Error", 
            "Test description"
        )
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert call_args[1]['ephemeral'] is True
        assert call_args[1]['embed'].title == "Test Error"
    
    @pytest.mark.asyncio
    async def test_send_success_embed(self, base_cog, mock_interaction):
        """Test sending success embed."""
        await base_cog.send_success_embed(
            mock_interaction, 
            "Test Success", 
            "Test description"
        )
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert call_args[1]['ephemeral'] is False
        assert call_args[1]['embed'].title == "Test Success"
    
    @pytest.mark.asyncio
    async def test_cog_load(self, base_cog):
        """Test cog loading."""
        # Should not raise any exceptions
        await base_cog.cog_load()
    
    @pytest.mark.asyncio
    async def test_cog_unload(self, base_cog):
        """Test cog unloading."""
        # Should not raise any exceptions
        await base_cog.cog_unload()


class TestPermissionDecorators:
    """Test cases for permission decorators."""
    
    @pytest.fixture
    def mock_cog(self):
        """Create a mock cog with permission checking methods."""
        cog = Mock()
        cog.check_staff_permissions = AsyncMock()
        cog.check_admin_permissions = AsyncMock()
        return cog
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock interaction."""
        interaction = Mock(spec=discord.Interaction)
        interaction.user = Mock()
        interaction.guild = Mock()
        interaction.response = Mock()
        interaction.response.send_message = AsyncMock()
        return interaction
    
    @pytest.mark.asyncio
    async def test_require_staff_role_success(self, mock_cog, mock_interaction):
        """Test staff role requirement with authorized user."""
        mock_cog.check_staff_permissions.return_value = True
        
        @require_staff_role()
        async def test_command(self, interaction):
            return "success"
        
        result = await test_command(mock_cog, mock_interaction)
        assert result == "success"
        mock_cog.check_staff_permissions.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_require_staff_role_failure(self, mock_cog, mock_interaction):
        """Test staff role requirement with unauthorized user."""
        mock_cog.check_staff_permissions.return_value = False
        
        @require_staff_role()
        async def test_command(self, interaction):
            return "success"
        
        result = await test_command(mock_cog, mock_interaction)
        assert result is None  # Should return None when permission denied
        mock_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_require_admin_role_success(self, mock_cog, mock_interaction):
        """Test admin role requirement with authorized user."""
        mock_interaction.user.guild_permissions.administrator = True
        
        @require_admin_role()
        async def test_command(self, interaction):
            return "success"
        
        result = await test_command(mock_cog, mock_interaction)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_require_admin_role_failure(self, mock_cog, mock_interaction):
        """Test admin role requirement with unauthorized user."""
        mock_interaction.user.guild_permissions.administrator = False
        mock_cog.check_admin_permissions.return_value = False
        
        @require_admin_role()
        async def test_command(self, interaction):
            return "success"
        
        result = await test_command(mock_cog, mock_interaction)
        assert result is None  # Should return None when permission denied
        mock_interaction.response.send_message.assert_called_once()


class TestErrorHandling:
    """Test cases for error handling decorator."""
    
    @pytest.fixture
    def mock_cog(self):
        """Create a mock cog."""
        return Mock()
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock interaction."""
        interaction = Mock(spec=discord.Interaction)
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.followup = Mock()
        interaction.followup.send = AsyncMock()
        return interaction
    
    @pytest.mark.asyncio
    async def test_handle_errors_success(self, mock_cog, mock_interaction):
        """Test error handler with successful command."""
        @handle_errors
        async def test_command(self, interaction):
            return "success"
        
        result = await test_command(mock_cog, mock_interaction)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_handle_errors_permission_error(self, mock_cog, mock_interaction):
        """Test error handler with PermissionError."""
        @handle_errors
        async def test_command(self, interaction):
            raise PermissionError("Test permission error")
        
        await test_command(mock_cog, mock_interaction)
        mock_interaction.response.send_message.assert_called_once()
        
        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        assert "Permission Error" in embed.title
    
    @pytest.mark.asyncio
    async def test_handle_errors_configuration_error(self, mock_cog, mock_interaction):
        """Test error handler with ConfigurationError."""
        @handle_errors
        async def test_command(self, interaction):
            raise ConfigurationError("Test config error")
        
        await test_command(mock_cog, mock_interaction)
        mock_interaction.response.send_message.assert_called_once()
        
        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        assert "Configuration Error" in embed.title
    
    @pytest.mark.asyncio
    async def test_handle_errors_generic_ticket_bot_error(self, mock_cog, mock_interaction):
        """Test error handler with generic TicketBotError."""
        @handle_errors
        async def test_command(self, interaction):
            raise TicketBotError("Test generic error")
        
        await test_command(mock_cog, mock_interaction)
        mock_interaction.response.send_message.assert_called_once()
        
        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        assert "Error" in embed.title
    
    @pytest.mark.asyncio
    async def test_handle_errors_unexpected_error(self, mock_cog, mock_interaction):
        """Test error handler with unexpected exception."""
        @handle_errors
        async def test_command(self, interaction):
            raise ValueError("Unexpected error")
        
        await test_command(mock_cog, mock_interaction)
        mock_interaction.response.send_message.assert_called_once()
        
        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        assert "Unexpected Error" in embed.title
    
    @pytest.mark.asyncio
    async def test_handle_errors_response_already_done(self, mock_cog, mock_interaction):
        """Test error handler when interaction response is already done."""
        mock_interaction.response.is_done.return_value = True
        
        @handle_errors
        async def test_command(self, interaction):
            raise PermissionError("Test error")
        
        await test_command(mock_cog, mock_interaction)
        mock_interaction.followup.send.assert_called_once()


class TestBotExtensionLoading:
    """Test cases for bot extension loading system."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot for testing extension loading."""
        from bot import TicketBot
        
        bot = Mock(spec=TicketBot)
        bot.load_extension = AsyncMock()
        bot.reload_extension = AsyncMock()
        return bot
    
    @pytest.mark.asyncio
    async def test_reload_extension_safe_success(self, mock_bot):
        """Test successful extension reload."""
        from bot import TicketBot
        
        # Create a real instance to test the method
        with patch('bot.os.getenv', return_value='test_token'):
            real_bot = TicketBot()
            real_bot.load_extension = AsyncMock()
            real_bot.reload_extension = AsyncMock()
            
            result = await real_bot.reload_extension_safe("test_extension")
            assert result is True
            real_bot.reload_extension.assert_called_once_with("test_extension")
    
    @pytest.mark.asyncio
    async def test_reload_extension_safe_not_loaded(self, mock_bot):
        """Test extension reload when extension is not loaded."""
        from bot import TicketBot
        
        with patch('bot.os.getenv', return_value='test_token'):
            real_bot = TicketBot()
            real_bot.load_extension = AsyncMock()
            real_bot.reload_extension = AsyncMock(side_effect=commands.ExtensionNotLoaded("test"))
            
            result = await real_bot.reload_extension_safe("test_extension")
            assert result is True
            real_bot.load_extension.assert_called_once_with("test_extension")
    
    @pytest.mark.asyncio
    async def test_reload_extension_safe_failure(self, mock_bot):
        """Test extension reload failure."""
        from bot import TicketBot
        
        with patch('bot.os.getenv', return_value='test_token'):
            real_bot = TicketBot()
            real_bot.reload_extension = AsyncMock(side_effect=Exception("Test error"))
            
            result = await real_bot.reload_extension_safe("test_extension")
            assert result is False


if __name__ == "__main__":
    pytest.main([__file__])