"""
Unit tests for error handling system.

Tests custom exception classes, error handlers, and decorators
to ensure proper error management throughout the bot.
"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

import discord
from discord.ext import commands

from errors.exceptions import (
    TicketBotError, DatabaseError, PermissionError, ConfigurationError,
    TicketCreationError, UserManagementError, TicketClosingError,
    TranscriptError, ValidationError, RateLimitError, TicketNotFoundError
)
from errors.handlers import (
    handle_errors, handle_database_errors, require_staff_role,
    retry_on_failure, log_error, format_error_message, send_error_embed
)


class TestCustomExceptions:
    """Test custom exception classes."""
    
    def test_ticket_bot_error_base(self):
        """Test TicketBotError base exception."""
        error = TicketBotError(
            "Technical message",
            user_message="User friendly message",
            error_code="TEST_ERROR",
            details={"key": "value"}
        )
        
        assert str(error) == "Technical message"
        assert error.user_message == "User friendly message"
        assert error.error_code == "TEST_ERROR"
        assert error.details == {"key": "value"}
    
    def test_ticket_bot_error_defaults(self):
        """Test TicketBotError with default values."""
        error = TicketBotError("Technical message")
        
        assert str(error) == "Technical message"
        assert error.user_message == "Technical message"
        assert error.error_code is None
        assert error.details == {}
    
    def test_database_error(self):
        """Test DatabaseError exception."""
        error = DatabaseError(
            "Connection failed",
            operation="create_ticket",
            user_message="Database unavailable"
        )
        
        assert str(error) == "Connection failed"
        assert error.user_message == "Database unavailable"
        assert error.error_code == "DB_ERROR"
        assert error.operation == "create_ticket"
    
    def test_database_error_default_message(self):
        """Test DatabaseError with default user message."""
        error = DatabaseError("Connection failed", operation="get_user")
        
        assert error.user_message == "A database error occurred. Please try again later."
        assert error.operation == "get_user"
    
    def test_permission_error(self):
        """Test PermissionError exception."""
        error = PermissionError(
            "User lacks role",
            required_permission="staff_role",
            user_message="Staff only command"
        )
        
        assert str(error) == "User lacks role"
        assert error.user_message == "Staff only command"
        assert error.error_code == "PERMISSION_ERROR"
        assert error.required_permission == "staff_role"
    
    def test_permission_error_default_message(self):
        """Test PermissionError with default user message."""
        error = PermissionError("Access denied")
        
        assert error.user_message == "You don't have permission to perform this action."
    
    def test_configuration_error(self):
        """Test ConfigurationError exception."""
        error = ConfigurationError(
            "Missing config key",
            config_key="staff_roles",
            user_message="Setup required"
        )
        
        assert str(error) == "Missing config key"
        assert error.user_message == "Setup required"
        assert error.error_code == "CONFIG_ERROR"
        assert error.config_key == "staff_roles"
    
    def test_ticket_creation_error(self):
        """Test TicketCreationError exception."""
        error = TicketCreationError(
            "Channel creation failed",
            reason="No permissions",
            user_message="Cannot create ticket"
        )
        
        assert str(error) == "Channel creation failed"
        assert error.user_message == "Cannot create ticket"
        assert error.error_code == "TICKET_CREATE_ERROR"
        assert error.reason == "No permissions"
    
    def test_user_management_error(self):
        """Test UserManagementError exception."""
        error = UserManagementError(
            "Add user failed",
            operation="add",
            user_id=12345,
            user_message="Cannot add user"
        )
        
        assert str(error) == "Add user failed"
        assert error.user_message == "Cannot add user"
        assert error.error_code == "USER_MGMT_ERROR"
        assert error.operation == "add"
        assert error.user_id == 12345
    
    def test_ticket_closing_error(self):
        """Test TicketClosingError exception."""
        error = TicketClosingError(
            "Transcript failed",
            ticket_id="ABC123",
            stage="transcript",
            user_message="Close failed"
        )
        
        assert str(error) == "Transcript failed"
        assert error.user_message == "Close failed"
        assert error.error_code == "TICKET_CLOSE_ERROR"
        assert error.ticket_id == "ABC123"
        assert error.stage == "transcript"
    
    def test_transcript_error(self):
        """Test TranscriptError exception."""
        error = TranscriptError(
            "File write failed",
            ticket_id="ABC123",
            user_message="Transcript unavailable"
        )
        
        assert str(error) == "File write failed"
        assert error.user_message == "Transcript unavailable"
        assert error.error_code == "TRANSCRIPT_ERROR"
        assert error.ticket_id == "ABC123"
    
    def test_validation_error(self):
        """Test ValidationError exception."""
        error = ValidationError(
            "Invalid input",
            field="user_id",
            value="invalid",
            user_message="Bad input"
        )
        
        assert str(error) == "Invalid input"
        assert error.user_message == "Bad input"
        assert error.error_code == "VALIDATION_ERROR"
        assert error.field == "user_id"
        assert error.value == "invalid"
    
    def test_rate_limit_error(self):
        """Test RateLimitError exception."""
        error = RateLimitError(
            "Too many requests",
            retry_after=30.5,
            user_message="Slow down"
        )
        
        assert str(error) == "Too many requests"
        assert error.user_message == "Slow down"
        assert error.error_code == "RATE_LIMIT_ERROR"
        assert error.retry_after == 30.5
    
    def test_rate_limit_error_default_message(self):
        """Test RateLimitError with default user message."""
        error = RateLimitError("Rate limited", retry_after=15.0)
        
        assert "15.0 seconds" in error.user_message
    
    def test_ticket_not_found_error(self):
        """Test TicketNotFoundError exception."""
        error = TicketNotFoundError(
            "Ticket missing",
            ticket_id="ABC123",
            user_message="Not found"
        )
        
        assert str(error) == "Ticket missing"
        assert error.user_message == "Not found"
        assert error.error_code == "TICKET_NOT_FOUND"
        assert error.ticket_id == "ABC123"


class TestErrorHandlers:
    """Test error handling utilities."""
    
    def test_log_error_basic(self, caplog):
        """Test basic error logging."""
        with caplog.at_level(logging.ERROR):
            error = TicketBotError("Test error")
            log_error(error, context="test_function")
        
        assert "Bot error" in caplog.text
        assert "test_function" in caplog.text
        assert "Test error" in caplog.text
    
    def test_log_error_with_details(self, caplog):
        """Test error logging with additional details."""
        with caplog.at_level(logging.ERROR):
            error = DatabaseError("DB error")
            log_error(
                error,
                context="database_operation",
                user_id=12345,
                guild_id=67890,
                additional_info={"query": "SELECT * FROM tickets"}
            )
        
        assert "database_operation" in caplog.text
        assert "12345" in caplog.text
        assert "67890" in caplog.text
        assert "SELECT * FROM tickets" in caplog.text
    
    def test_log_error_permission_warning(self, caplog):
        """Test that permission errors are logged as warnings."""
        with caplog.at_level(logging.WARNING):
            error = PermissionError("Access denied")
            log_error(error)
        
        assert caplog.records[0].levelname == "WARNING"
        assert "Access denied" in caplog.text
    
    def test_log_error_unexpected_with_traceback(self, caplog):
        """Test that unexpected errors include traceback."""
        with caplog.at_level(logging.ERROR):
            error = ValueError("Unexpected error")
            log_error(error, context="test")
        
        assert "Unexpected error" in caplog.text
        assert caplog.records[0].exc_info is not None
    
    def test_format_error_message_ticket_bot_error(self):
        """Test formatting TicketBotError messages."""
        error = TicketBotError(
            "Technical message",
            user_message="User message",
            details={"key": "value"}
        )
        
        message = format_error_message(error)
        assert message == "User message"
        
        message_with_details = format_error_message(error, include_details=True)
        assert "User message" in message_with_details
        assert "key: value" in message_with_details
    
    def test_format_error_message_generic_error(self):
        """Test formatting generic error messages."""
        error = ValueError("Some error")
        message = format_error_message(error)
        
        assert message == "An unexpected error occurred. Please try again later."
    
    @pytest.mark.asyncio
    async def test_send_error_embed_interaction(self):
        """Test sending error embed via interaction."""
        # Mock interaction
        interaction = Mock(spec=discord.Interaction)
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        
        await send_error_embed(interaction, "Test Error", "Test description")
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        
        assert embed.title == "Test Error"
        assert embed.description == "Test description"
        assert embed.color == discord.Color.red()
    
    @pytest.mark.asyncio
    async def test_send_error_embed_followup(self):
        """Test sending error embed via followup."""
        # Mock interaction with completed response
        interaction = Mock(spec=discord.Interaction)
        interaction.response.is_done.return_value = True
        interaction.followup.send = AsyncMock()
        
        await send_error_embed(interaction, "Test Error", "Test description")
        
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        embed = call_args[1]['embed']
        
        assert embed.title == "Test Error"
        assert embed.description == "Test description"
    
    @pytest.mark.asyncio
    async def test_send_error_embed_context(self):
        """Test sending error embed via context."""
        # Mock context
        context = Mock(spec=commands.Context)
        context.send = AsyncMock()
        
        await send_error_embed(context, "Test Error", "Test description")
        
        context.send.assert_called_once()
        call_args = context.send.call_args
        embed = call_args[1]['embed']
        
        assert embed.title == "Test Error"
        assert embed.description == "Test description"


class TestErrorDecorators:
    """Test error handling decorators."""
    
    @pytest.mark.asyncio
    async def test_handle_errors_ticket_bot_error(self):
        """Test handle_errors decorator with TicketBotError."""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.id = 12345
        interaction.guild.id = 67890
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        
        @handle_errors
        async def test_function(interaction):
            raise TicketBotError("Test error", user_message="User error")
        
        await test_function(interaction)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        
        assert "Error" in embed.title
        assert "User error" in embed.description
    
    @pytest.mark.asyncio
    async def test_handle_errors_permission_error(self):
        """Test handle_errors decorator with PermissionError."""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.id = 12345
        interaction.guild.id = 67890
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        
        @handle_errors
        async def test_function(interaction):
            raise PermissionError("Access denied", user_message="No permission")
        
        await test_function(interaction)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        
        assert "Permission Denied" in embed.title
        assert "No permission" in embed.description
        assert embed.color == discord.Color.orange()
    
    @pytest.mark.asyncio
    async def test_handle_errors_rate_limit_error(self):
        """Test handle_errors decorator with RateLimitError."""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.id = 12345
        interaction.guild.id = 67890
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        
        @handle_errors
        async def test_function(interaction):
            raise RateLimitError("Rate limited", user_message="Too fast")
        
        await test_function(interaction)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        
        assert "Rate Limited" in embed.title
        assert "Too fast" in embed.description
        assert embed.color == discord.Color.yellow()
    
    @pytest.mark.asyncio
    async def test_handle_errors_discord_forbidden(self):
        """Test handle_errors decorator with Discord Forbidden error."""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.id = 12345
        interaction.guild.id = 67890
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        
        @handle_errors
        async def test_function(interaction):
            raise discord.Forbidden(Mock(), "Forbidden")
        
        await test_function(interaction)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        
        assert "Permission Error" in embed.title
        assert "bot doesn't have permission" in embed.description
    
    @pytest.mark.asyncio
    async def test_handle_errors_discord_not_found(self):
        """Test handle_errors decorator with Discord NotFound error."""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.id = 12345
        interaction.guild.id = 67890
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        
        @handle_errors
        async def test_function(interaction):
            raise discord.NotFound(Mock(), "Not found")
        
        await test_function(interaction)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        
        assert "Not Found" in embed.title
        assert "not found" in embed.description
    
    @pytest.mark.asyncio
    async def test_handle_errors_unexpected_error(self):
        """Test handle_errors decorator with unexpected error."""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.id = 12345
        interaction.guild.id = 67890
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        
        @handle_errors
        async def test_function(interaction):
            raise ValueError("Unexpected error")
        
        await test_function(interaction)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        
        assert "Unexpected Error" in embed.title
        assert "unexpected error occurred" in embed.description
    
    @pytest.mark.asyncio
    async def test_handle_database_errors_success(self):
        """Test handle_database_errors decorator with successful operation."""
        @handle_database_errors
        async def test_function():
            return "success"
        
        result = await test_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_handle_database_errors_retry_success(self):
        """Test handle_database_errors decorator with retry success."""
        call_count = 0
        
        @handle_database_errors
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary error")
            return "success"
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await test_function()
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_handle_database_errors_max_retries(self):
        """Test handle_database_errors decorator with max retries exceeded."""
        @handle_database_errors
        async def test_function():
            raise Exception("Persistent error")
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(DatabaseError) as exc_info:
                await test_function()
        
        assert "failed after 3 attempts" in str(exc_info.value)
        assert exc_info.value.operation == "test_function"
    
    @pytest.mark.asyncio
    async def test_require_staff_role_admin_user(self):
        """Test require_staff_role decorator with admin user."""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.guild_permissions.administrator = True
        interaction.guild = Mock()
        
        @require_staff_role()
        async def test_function(interaction):
            return "success"
        
        result = await test_function(interaction)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_require_staff_role_non_admin_user(self):
        """Test require_staff_role decorator with non-admin user."""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.guild_permissions.administrator = False
        interaction.user.id = 12345
        interaction.guild = Mock()
        interaction.guild.id = 67890
        
        @require_staff_role()
        async def test_function(interaction):
            return "success"
        
        with pytest.raises(PermissionError) as exc_info:
            await test_function(interaction)
        
        assert "administrator permission" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_require_staff_role_no_guild(self):
        """Test require_staff_role decorator without guild context."""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = None
        
        @require_staff_role()
        async def test_function(interaction):
            return "success"
        
        with pytest.raises(PermissionError) as exc_info:
            await test_function(interaction)
        
        assert "must be used in a guild" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_retry_on_failure_success(self):
        """Test retry_on_failure decorator with successful operation."""
        @retry_on_failure(max_retries=2, delay=0.1)
        async def test_function():
            return "success"
        
        result = await test_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_on_failure_retry_success(self):
        """Test retry_on_failure decorator with retry success."""
        call_count = 0
        
        @retry_on_failure(max_retries=2, delay=0.1)
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary error")
            return "success"
        
        result = await test_function()
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_on_failure_max_retries(self):
        """Test retry_on_failure decorator with max retries exceeded."""
        @retry_on_failure(max_retries=2, delay=0.1)
        async def test_function():
            raise ValueError("Persistent error")
        
        with pytest.raises(ValueError) as exc_info:
            await test_function()
        
        assert "Persistent error" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__])