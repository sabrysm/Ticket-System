"""
Custom log formatters for Discord Ticket Bot.

This module provides specialized log formatters for different types of logs
including standard bot logs and audit logs.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional


class TicketBotFormatter(logging.Formatter):
    """
    Custom formatter for Discord Ticket Bot logs.
    
    Provides colored output for console and structured formatting for files.
    """
    
    # Color codes for different log levels
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def __init__(self, use_colors: bool = True, include_extra: bool = False):
        """
        Initialize the formatter.
        
        Args:
            use_colors: Whether to use colors in output (for console)
            include_extra: Whether to include extra fields in output
        """
        self.use_colors = use_colors
        self.include_extra = include_extra
        
        # Base format string
        base_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        super().__init__(base_format, datefmt='%Y-%m-%d %H:%M:%S')
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record.
        
        Args:
            record: Log record to format
            
        Returns:
            str: Formatted log message
        """
        # Create a copy of the record to avoid modifying the original
        record_copy = logging.makeLogRecord(record.__dict__)
        
        # Add color to level name if colors are enabled
        if self.use_colors and hasattr(record_copy, 'levelname'):
            color = self.COLORS.get(record_copy.levelname, '')
            reset = self.COLORS['RESET']
            record_copy.levelname = f"{color}{record_copy.levelname}{reset}"
        
        # Format the base message
        formatted = super().format(record_copy)
        
        # Add extra information if requested
        if self.include_extra:
            extra_info = self._extract_extra_info(record)
            if extra_info:
                extra_str = " | " + " | ".join(f"{k}={v}" for k, v in extra_info.items())
                formatted += extra_str
        
        return formatted
    
    def _extract_extra_info(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        Extract extra information from log record.
        
        Args:
            record: Log record to extract from
            
        Returns:
            Dict[str, Any]: Extra information
        """
        # Standard fields that shouldn't be included as extra
        standard_fields = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
            'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
            'thread', 'threadName', 'processName', 'process', 'getMessage', 'exc_info',
            'exc_text', 'stack_info', 'asctime', 'message'
        }
        
        extra = {}
        for key, value in record.__dict__.items():
            if key not in standard_fields and not key.startswith('_'):
                # Convert complex objects to strings
                if isinstance(value, (dict, list, tuple)):
                    try:
                        extra[key] = json.dumps(value, default=str)
                    except (TypeError, ValueError):
                        extra[key] = str(value)
                else:
                    extra[key] = value
        
        return extra


class AuditFormatter(logging.Formatter):
    """
    Specialized formatter for audit logs.
    
    Formats audit events as structured JSON for easy parsing and analysis.
    """
    
    def __init__(self):
        """Initialize the audit formatter."""
        # We don't use the parent formatter for audit logs
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format an audit log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            str: JSON-formatted audit log entry
        """
        # Base audit entry
        audit_entry = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage()
        }
        
        # Add audit-specific data if present
        if hasattr(record, 'audit_data') and record.audit_data:
            audit_entry.update(record.audit_data)
        
        # Add exception information if present
        if record.exc_info:
            audit_entry['exception'] = self.formatException(record.exc_info)
        
        # Add any other extra fields
        extra_fields = self._extract_extra_fields(record)
        if extra_fields:
            audit_entry['extra'] = extra_fields
        
        try:
            return json.dumps(audit_entry, default=self._json_serializer, separators=(',', ':'))
        except (TypeError, ValueError) as e:
            # Fallback to string representation if JSON serialization fails
            return f"AUDIT_LOG_ERROR: Failed to serialize audit entry: {e} | Original: {audit_entry}"
    
    def _extract_extra_fields(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        Extract extra fields from log record.
        
        Args:
            record: Log record to extract from
            
        Returns:
            Dict[str, Any]: Extra fields
        """
        # Standard fields that shouldn't be included as extra
        standard_fields = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
            'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
            'thread', 'threadName', 'processName', 'process', 'getMessage', 'exc_info',
            'exc_text', 'stack_info', 'message', 'audit_data'
        }
        
        extra = {}
        for key, value in record.__dict__.items():
            if key not in standard_fields and not key.startswith('_'):
                extra[key] = value
        
        return extra
    
    def _json_serializer(self, obj: Any) -> str:
        """
        Custom JSON serializer for objects that aren't JSON serializable.
        
        Args:
            obj: Object to serialize
            
        Returns:
            str: String representation of the object
        """
        if isinstance(obj, datetime):
            return obj.isoformat() + 'Z'
        elif hasattr(obj, '__dict__'):
            return str(obj)
        else:
            return str(obj)


class PerformanceFormatter(logging.Formatter):
    """
    Specialized formatter for performance monitoring logs.
    
    Formats performance metrics and timing information.
    """
    
    def __init__(self):
        """Initialize the performance formatter."""
        format_string = "%(asctime)s - PERF - %(message)s"
        super().__init__(format_string, datefmt='%Y-%m-%d %H:%M:%S')
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format a performance log record.
        
        Args:
            record: Log record to format
            
        Returns:
            str: Formatted performance log entry
        """
        formatted = super().format(record)
        
        # Add performance metrics if present
        if hasattr(record, 'duration'):
            formatted += f" | Duration: {record.duration:.3f}s"
        
        if hasattr(record, 'memory_usage'):
            formatted += f" | Memory: {record.memory_usage}MB"
        
        if hasattr(record, 'operation'):
            formatted += f" | Operation: {record.operation}"
        
        return formatted