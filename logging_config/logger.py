"""
Main logging configuration and setup for Discord Ticket Bot.

This module provides centralized logging configuration with support for
file rotation, audit logging, and structured log formatting.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from .formatters import TicketBotFormatter, AuditFormatter
from .handlers import RotatingFileHandler, AuditFileHandler


class TicketBotLogger:
    """
    Main logger class for the Discord Ticket Bot.
    
    Provides centralized logging configuration with support for multiple
    log levels, file rotation, and audit logging.
    """
    
    def __init__(self, log_dir: str = "logs", log_level: str = "INFO"):
        """
        Initialize the logger.
        
        Args:
            log_dir: Directory to store log files
            log_level: Default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.loggers: Dict[str, logging.Logger] = {}
        
        # Create log directory if it doesn't exist
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup root logger
        self._setup_root_logger()
    
    def _setup_root_logger(self):
        """Setup the root logger with basic configuration."""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Clear any existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(TicketBotFormatter())
        root_logger.addHandler(console_handler)
        
        # Main log file handler with rotation
        main_log_file = self.log_dir / "bot.log"
        file_handler = RotatingFileHandler(
            filename=str(main_log_file),
            max_bytes=10 * 1024 * 1024,  # 10MB
            backup_count=5,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(TicketBotFormatter(include_extra=True))
        root_logger.addHandler(file_handler)
        
        # Error log file handler
        error_log_file = self.log_dir / "error.log"
        error_handler = RotatingFileHandler(
            filename=str(error_log_file),
            max_bytes=5 * 1024 * 1024,  # 5MB
            backup_count=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(TicketBotFormatter(include_extra=True))
        root_logger.addHandler(error_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance for a specific module.
        
        Args:
            name: Logger name (usually __name__)
            
        Returns:
            logging.Logger: Configured logger instance
        """
        if name not in self.loggers:
            logger = logging.getLogger(name)
            self.loggers[name] = logger
        
        return self.loggers[name]
    
    def setup_audit_logging(self) -> 'AuditLogger':
        """
        Setup audit logging for ticket operations.
        
        Returns:
            AuditLogger: Configured audit logger instance
        """
        return AuditLogger(self.log_dir)


class AuditLogger:
    """
    Specialized logger for audit events and ticket operations.
    
    Provides structured logging for user actions, ticket operations,
    and administrative activities.
    """
    
    def __init__(self, log_dir: Path):
        """
        Initialize the audit logger.
        
        Args:
            log_dir: Directory to store audit log files
        """
        self.log_dir = log_dir
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Audit log file handler
        audit_log_file = self.log_dir / "audit.log"
        audit_handler = AuditFileHandler(
            filename=str(audit_log_file),
            max_bytes=20 * 1024 * 1024,  # 20MB
            backup_count=10,
            encoding='utf-8'
        )
        audit_handler.setLevel(logging.INFO)
        audit_handler.setFormatter(AuditFormatter())
        self.logger.addHandler(audit_handler)
        
        # Prevent audit logs from propagating to root logger
        self.logger.propagate = False
    
    def log_ticket_created(self, ticket_id: str, user_id: int, guild_id: int, 
                          channel_id: int, additional_info: Optional[Dict[str, Any]] = None):
        """
        Log ticket creation event.
        
        Args:
            ticket_id: Unique ticket identifier
            user_id: ID of user who created the ticket
            guild_id: ID of the guild where ticket was created
            channel_id: ID of the created ticket channel
            additional_info: Additional information to log
        """
        self._log_audit_event(
            event_type="TICKET_CREATED",
            ticket_id=ticket_id,
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            additional_info=additional_info
        )
    
    def log_ticket_closed(self, ticket_id: str, user_id: int, guild_id: int,
                         channel_id: int, reason: Optional[str] = None,
                         additional_info: Optional[Dict[str, Any]] = None):
        """
        Log ticket closure event.
        
        Args:
            ticket_id: Unique ticket identifier
            user_id: ID of user who closed the ticket
            guild_id: ID of the guild
            channel_id: ID of the ticket channel
            reason: Reason for closing the ticket
            additional_info: Additional information to log
        """
        info = additional_info or {}
        if reason:
            info['reason'] = reason
        
        self._log_audit_event(
            event_type="TICKET_CLOSED",
            ticket_id=ticket_id,
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            additional_info=info
        )
    
    def log_user_added(self, ticket_id: str, added_user_id: int, staff_user_id: int,
                      guild_id: int, channel_id: int, 
                      additional_info: Optional[Dict[str, Any]] = None):
        """
        Log user addition to ticket event.
        
        Args:
            ticket_id: Unique ticket identifier
            added_user_id: ID of user who was added
            staff_user_id: ID of staff member who added the user
            guild_id: ID of the guild
            channel_id: ID of the ticket channel
            additional_info: Additional information to log
        """
        info = additional_info or {}
        info['added_user_id'] = added_user_id
        
        self._log_audit_event(
            event_type="USER_ADDED",
            ticket_id=ticket_id,
            user_id=staff_user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            additional_info=info
        )
    
    def log_user_removed(self, ticket_id: str, removed_user_id: int, staff_user_id: int,
                        guild_id: int, channel_id: int,
                        additional_info: Optional[Dict[str, Any]] = None):
        """
        Log user removal from ticket event.
        
        Args:
            ticket_id: Unique ticket identifier
            removed_user_id: ID of user who was removed
            staff_user_id: ID of staff member who removed the user
            guild_id: ID of the guild
            channel_id: ID of the ticket channel
            additional_info: Additional information to log
        """
        info = additional_info or {}
        info['removed_user_id'] = removed_user_id
        
        self._log_audit_event(
            event_type="USER_REMOVED",
            ticket_id=ticket_id,
            user_id=staff_user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            additional_info=info
        )
    
    def log_command_used(self, command_name: str, user_id: int, guild_id: int,
                        channel_id: int, success: bool = True,
                        additional_info: Optional[Dict[str, Any]] = None):
        """
        Log command usage event.
        
        Args:
            command_name: Name of the command used
            user_id: ID of user who used the command
            guild_id: ID of the guild
            channel_id: ID of the channel where command was used
            success: Whether the command executed successfully
            additional_info: Additional information to log
        """
        info = additional_info or {}
        info['command_name'] = command_name
        info['success'] = success
        
        self._log_audit_event(
            event_type="COMMAND_USED",
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            additional_info=info
        )
    
    def log_permission_denied(self, command_name: str, user_id: int, guild_id: int,
                             channel_id: int, required_permission: str,
                             additional_info: Optional[Dict[str, Any]] = None):
        """
        Log permission denied event.
        
        Args:
            command_name: Name of the command that was denied
            user_id: ID of user who was denied
            guild_id: ID of the guild
            channel_id: ID of the channel
            required_permission: The permission that was required
            additional_info: Additional information to log
        """
        info = additional_info or {}
        info['command_name'] = command_name
        info['required_permission'] = required_permission
        
        self._log_audit_event(
            event_type="PERMISSION_DENIED",
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            additional_info=info
        )
    
    def log_configuration_changed(self, user_id: int, guild_id: int, 
                                 setting_name: str, old_value: Any, new_value: Any,
                                 additional_info: Optional[Dict[str, Any]] = None):
        """
        Log configuration change event.
        
        Args:
            user_id: ID of user who made the change
            guild_id: ID of the guild
            setting_name: Name of the setting that was changed
            old_value: Previous value
            new_value: New value
            additional_info: Additional information to log
        """
        info = additional_info or {}
        info['setting_name'] = setting_name
        info['old_value'] = str(old_value)
        info['new_value'] = str(new_value)
        
        self._log_audit_event(
            event_type="CONFIG_CHANGED",
            user_id=user_id,
            guild_id=guild_id,
            additional_info=info
        )
    
    def log_error_occurred(self, error_type: str, error_message: str,
                          user_id: Optional[int] = None, guild_id: Optional[int] = None,
                          channel_id: Optional[int] = None, ticket_id: Optional[str] = None,
                          additional_info: Optional[Dict[str, Any]] = None):
        """
        Log error occurrence event.
        
        Args:
            error_type: Type of error that occurred
            error_message: Error message
            user_id: ID of user involved (if applicable)
            guild_id: ID of guild involved (if applicable)
            channel_id: ID of channel involved (if applicable)
            ticket_id: ID of ticket involved (if applicable)
            additional_info: Additional information to log
        """
        info = additional_info or {}
        info['error_type'] = error_type
        info['error_message'] = error_message
        
        self._log_audit_event(
            event_type="ERROR_OCCURRED",
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            ticket_id=ticket_id,
            additional_info=info
        )
    
    def _log_audit_event(self, event_type: str, user_id: Optional[int] = None,
                        guild_id: Optional[int] = None, channel_id: Optional[int] = None,
                        ticket_id: Optional[str] = None, 
                        additional_info: Optional[Dict[str, Any]] = None):
        """
        Log a structured audit event.
        
        Args:
            event_type: Type of event being logged
            user_id: ID of user involved
            guild_id: ID of guild involved
            channel_id: ID of channel involved
            ticket_id: ID of ticket involved
            additional_info: Additional information to include
        """
        event_data = {
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'guild_id': guild_id,
            'channel_id': channel_id,
            'ticket_id': ticket_id
        }
        
        if additional_info:
            event_data.update(additional_info)
        
        # Remove None values
        event_data = {k: v for k, v in event_data.items() if v is not None}
        
        self.logger.info("Audit event", extra={'audit_data': event_data})


# Global logger instance
_logger_instance: Optional[TicketBotLogger] = None
_audit_logger_instance: Optional[AuditLogger] = None


def setup_logging(log_dir: str = "logs", log_level: str = "INFO") -> TicketBotLogger:
    """
    Setup global logging configuration.
    
    Args:
        log_dir: Directory to store log files
        log_level: Default log level
        
    Returns:
        TicketBotLogger: Configured logger instance
    """
    global _logger_instance, _audit_logger_instance
    
    _logger_instance = TicketBotLogger(log_dir, log_level)
    _audit_logger_instance = _logger_instance.setup_audit_logging()
    
    return _logger_instance


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    if _logger_instance is None:
        setup_logging()
    
    return _logger_instance.get_logger(name)


def get_audit_logger() -> AuditLogger:
    """
    Get the global audit logger instance.
    
    Returns:
        AuditLogger: Configured audit logger instance
    """
    if _audit_logger_instance is None:
        setup_logging()
    
    return _audit_logger_instance