"""
Custom exception classes for Discord Ticket Bot.

This module defines all custom exceptions used throughout the bot
for consistent error handling and user feedback.
"""

from typing import Optional, Dict, Any
import discord


class TicketBotError(Exception):
    """
    Base exception for all ticket bot errors.
    
    All custom exceptions in the bot should inherit from this class
    to provide consistent error handling and logging.
    """
    
    def __init__(self, message: str, user_message: Optional[str] = None, 
                 error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize TicketBotError.
        
        Args:
            message: Technical error message for logging
            user_message: User-friendly error message for display
            error_code: Optional error code for categorization
            details: Optional additional error details
        """
        super().__init__(message)
        self.user_message = user_message or message
        self.error_code = error_code
        self.details = details or {}


class DatabaseError(TicketBotError):
    """
    Exception raised for database-related errors.
    
    This includes connection failures, query errors, data integrity issues,
    and other database operation problems.
    """
    
    def __init__(self, message: str, operation: Optional[str] = None, 
                 user_message: Optional[str] = None, **kwargs):
        """
        Initialize DatabaseError.
        
        Args:
            message: Technical error message
            operation: Database operation that failed (e.g., 'create_ticket', 'get_user')
            user_message: User-friendly error message
        """
        if not user_message:
            user_message = "A database error occurred. Please try again later."
        
        super().__init__(message, user_message, error_code="DB_ERROR", **kwargs)
        self.operation = operation


class PermissionError(TicketBotError):
    """
    Exception raised for permission-related errors.
    
    This includes insufficient user permissions, role validation failures,
    and authorization issues.
    """
    
    def __init__(self, message: str, required_permission: Optional[str] = None,
                 user_message: Optional[str] = None, **kwargs):
        """
        Initialize PermissionError.
        
        Args:
            message: Technical error message
            required_permission: The permission that was required
            user_message: User-friendly error message
        """
        if not user_message:
            user_message = "You don't have permission to perform this action."
        
        super().__init__(message, user_message, error_code="PERMISSION_ERROR", **kwargs)
        self.required_permission = required_permission


class ConfigurationError(TicketBotError):
    """
    Exception raised for configuration-related errors.
    
    This includes missing settings, invalid configuration values,
    and setup issues.
    """
    
    def __init__(self, message: str, config_key: Optional[str] = None,
                 user_message: Optional[str] = None, **kwargs):
        """
        Initialize ConfigurationError.
        
        Args:
            message: Technical error message
            config_key: The configuration key that caused the error
            user_message: User-friendly error message
        """
        if not user_message:
            user_message = "Bot configuration error. Please contact an administrator."
        
        super().__init__(message, user_message, error_code="CONFIG_ERROR", **kwargs)
        self.config_key = config_key


class TicketCreationError(TicketBotError):
    """
    Exception raised when ticket creation fails.
    
    This includes channel creation failures, database insertion errors,
    and validation issues during ticket creation.
    """
    
    def __init__(self, message: str, reason: Optional[str] = None,
                 user_message: Optional[str] = None, **kwargs):
        """
        Initialize TicketCreationError.
        
        Args:
            message: Technical error message
            reason: Specific reason for the failure
            user_message: User-friendly error message
        """
        if not user_message:
            user_message = "Failed to create your ticket. Please try again or contact support."
        
        super().__init__(message, user_message, error_code="TICKET_CREATE_ERROR", **kwargs)
        self.reason = reason


class UserManagementError(TicketBotError):
    """
    Exception raised for user management operations in tickets.
    
    This includes adding/removing users, permission updates,
    and user validation errors.
    """
    
    def __init__(self, message: str, operation: Optional[str] = None,
                 user_id: Optional[int] = None, user_message: Optional[str] = None, **kwargs):
        """
        Initialize UserManagementError.
        
        Args:
            message: Technical error message
            operation: The operation that failed ('add', 'remove', etc.)
            user_id: ID of the user involved in the operation
            user_message: User-friendly error message
        """
        if not user_message:
            user_message = "Failed to manage user in ticket. Please try again."
        
        super().__init__(message, user_message, error_code="USER_MGMT_ERROR", **kwargs)
        self.operation = operation
        self.user_id = user_id


class TicketClosingError(TicketBotError):
    """
    Exception raised when ticket closing fails.
    
    This includes transcript generation failures, channel archiving errors,
    and database update issues during ticket closure.
    """
    
    def __init__(self, message: str, ticket_id: Optional[str] = None,
                 stage: Optional[str] = None, user_message: Optional[str] = None, **kwargs):
        """
        Initialize TicketClosingError.
        
        Args:
            message: Technical error message
            ticket_id: ID of the ticket being closed
            stage: Stage where the error occurred ('transcript', 'archive', 'database')
            user_message: User-friendly error message
        """
        if not user_message:
            user_message = "Failed to close the ticket. Please try again or contact support."
        
        super().__init__(message, user_message, error_code="TICKET_CLOSE_ERROR", **kwargs)
        self.ticket_id = ticket_id
        self.stage = stage


class TranscriptError(TicketBotError):
    """
    Exception raised for transcript generation and management errors.
    
    This includes file I/O errors, message history access issues,
    and transcript formatting problems.
    """
    
    def __init__(self, message: str, ticket_id: Optional[str] = None,
                 user_message: Optional[str] = None, **kwargs):
        """
        Initialize TranscriptError.
        
        Args:
            message: Technical error message
            ticket_id: ID of the ticket for transcript generation
            user_message: User-friendly error message
        """
        if not user_message:
            user_message = "Failed to generate ticket transcript. The ticket will still be closed."
        
        super().__init__(message, user_message, error_code="TRANSCRIPT_ERROR", **kwargs)
        self.ticket_id = ticket_id


class ValidationError(TicketBotError):
    """
    Exception raised for input validation errors.
    
    This includes invalid user input, malformed data,
    and constraint violations.
    """
    
    def __init__(self, message: str, field: Optional[str] = None,
                 value: Optional[Any] = None, user_message: Optional[str] = None, **kwargs):
        """
        Initialize ValidationError.
        
        Args:
            message: Technical error message
            field: The field that failed validation
            value: The invalid value
            user_message: User-friendly error message
        """
        if not user_message:
            user_message = "Invalid input provided. Please check your input and try again."
        
        super().__init__(message, user_message, error_code="VALIDATION_ERROR", **kwargs)
        self.field = field
        self.value = value


class RateLimitError(TicketBotError):
    """
    Exception raised when rate limits are exceeded.
    
    This includes Discord API rate limits, custom bot rate limits,
    and spam prevention measures.
    """
    
    def __init__(self, message: str, retry_after: Optional[float] = None,
                 user_message: Optional[str] = None, **kwargs):
        """
        Initialize RateLimitError.
        
        Args:
            message: Technical error message
            retry_after: Seconds to wait before retrying
            user_message: User-friendly error message
        """
        if not user_message:
            if retry_after:
                user_message = f"Rate limit exceeded. Please wait {retry_after:.1f} seconds before trying again."
            else:
                user_message = "Rate limit exceeded. Please wait before trying again."
        
        super().__init__(message, user_message, error_code="RATE_LIMIT_ERROR", **kwargs)
        self.retry_after = retry_after


# Legacy exception compatibility
# These are kept for backward compatibility with existing code
class TicketManagerError(TicketBotError):
    """Legacy exception - use TicketBotError instead."""
    pass


class TicketNotFoundError(TicketBotError):
    """
    Exception raised when a ticket is not found.
    
    This is a specific case of ValidationError for ticket lookup failures.
    """
    
    def __init__(self, message: str, ticket_id: Optional[str] = None,
                 user_message: Optional[str] = None, **kwargs):
        """
        Initialize TicketNotFoundError.
        
        Args:
            message: Technical error message
            ticket_id: ID of the ticket that was not found
            user_message: User-friendly error message
        """
        if not user_message:
            user_message = "Ticket not found. Please check the ticket ID and try again."
        
        super().__init__(message, user_message, error_code="TICKET_NOT_FOUND", **kwargs)
        self.ticket_id = ticket_id