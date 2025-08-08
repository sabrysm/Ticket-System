"""
Logging configuration module for Discord Ticket Bot.

This module provides comprehensive logging setup including file rotation,
audit logging, and structured logging for all bot operations.
"""

from .logger import setup_logging, get_logger, get_audit_logger, AuditLogger
from .formatters import TicketBotFormatter, AuditFormatter
from .handlers import RotatingFileHandler, AuditFileHandler

__all__ = [
    'setup_logging',
    'get_logger',
    'get_audit_logger',
    'AuditLogger',
    'TicketBotFormatter',
    'AuditFormatter',
    'RotatingFileHandler',
    'AuditFileHandler'
]