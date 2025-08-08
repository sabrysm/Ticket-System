"""
Error handling module for Discord Ticket Bot.

This module provides custom exception classes and error handling utilities
for consistent error management across the bot.
"""

from .exceptions import (
    TicketBotError,
    DatabaseError,
    PermissionError,
    ConfigurationError,
    TicketCreationError,
    UserManagementError,
    TicketClosingError,
    TranscriptError,
    ValidationError,
    RateLimitError
)

from .handlers import (
    handle_errors,
    send_error_embed,
    format_error_message,
    log_error
)

__all__ = [
    # Exception classes
    'TicketBotError',
    'DatabaseError', 
    'PermissionError',
    'ConfigurationError',
    'TicketCreationError',
    'UserManagementError',
    'TicketClosingError',
    'TranscriptError',
    'ValidationError',
    'RateLimitError',
    
    # Handler functions
    'handle_errors',
    'send_error_embed',
    'format_error_message',
    'log_error'
]