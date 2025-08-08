"""
Unit tests for logging system.

Tests logging configuration, formatters, handlers, and audit logging
to ensure proper log management throughout the bot.
"""

import pytest
import logging
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from datetime import datetime

from logging_config.logger import TicketBotLogger, AuditLogger, setup_logging, get_logger, get_audit_logger
from logging_config.formatters import TicketBotFormatter, AuditFormatter, PerformanceFormatter
from logging_config.handlers import RotatingFileHandler, AuditFileHandler, AsyncFileHandler


class TestTicketBotLogger:
    """Test the main TicketBotLogger class."""
    
    def test_logger_initialization(self):
        """Test logger initialization with default settings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = TicketBotLogger(log_dir=temp_dir, log_level="INFO")
            
            assert logger.log_dir == Path(temp_dir)
            assert logger.log_level == logging.INFO
            assert logger.log_dir.exists()
    
    def test_logger_initialization_custom_level(self):
        """Test logger initialization with custom log level."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = TicketBotLogger(log_dir=temp_dir, log_level="DEBUG")
            
            assert logger.log_level == logging.DEBUG
    
    def test_get_logger(self):
        """Test getting a logger instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = TicketBotLogger(log_dir=temp_dir)
            
            test_logger = logger.get_logger("test.module")
            assert isinstance(test_logger, logging.Logger)
            assert test_logger.name == "test.module"
            
            # Should return the same instance for the same name
            same_logger = logger.get_logger("test.module")
            assert test_logger is same_logger
    
    def test_setup_audit_logging(self):
        """Test audit logging setup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = TicketBotLogger(log_dir=temp_dir)
            audit_logger = logger.setup_audit_logging()
            
            assert isinstance(audit_logger, AuditLogger)
            assert audit_logger.log_dir == Path(temp_dir)


class TestAuditLogger:
    """Test the AuditLogger class."""
    
    def setup_method(self):
        """Setup for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.audit_logger = AuditLogger(Path(self.temp_dir))
    
    def teardown_method(self):
        """Cleanup after each test method."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_audit_logger_initialization(self):
        """Test audit logger initialization."""
        assert self.audit_logger.log_dir == Path(self.temp_dir)
        assert self.audit_logger.logger.name == "audit"
        assert not self.audit_logger.logger.propagate
    
    def test_log_ticket_created(self):
        """Test logging ticket creation event."""
        with patch.object(self.audit_logger.logger, 'info') as mock_info:
            self.audit_logger.log_ticket_created(
                ticket_id="ABC123",
                user_id=12345,
                guild_id=67890,
                channel_id=11111
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            
            assert call_args[0][0] == "Audit event"
            audit_data = call_args[1]['extra']['audit_data']
            assert audit_data['event_type'] == "TICKET_CREATED"
            assert audit_data['ticket_id'] == "ABC123"
            assert audit_data['user_id'] == 12345
            assert audit_data['guild_id'] == 67890
            assert audit_data['channel_id'] == 11111
    
    def test_log_ticket_closed(self):
        """Test logging ticket closure event."""
        with patch.object(self.audit_logger.logger, 'info') as mock_info:
            self.audit_logger.log_ticket_closed(
                ticket_id="ABC123",
                user_id=12345,
                guild_id=67890,
                channel_id=11111,
                reason="Issue resolved"
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            
            audit_data = call_args[1]['extra']['audit_data']
            assert audit_data['event_type'] == "TICKET_CLOSED"
            assert audit_data['reason'] == "Issue resolved"
    
    def test_log_user_added(self):
        """Test logging user addition event."""
        with patch.object(self.audit_logger.logger, 'info') as mock_info:
            self.audit_logger.log_user_added(
                ticket_id="ABC123",
                added_user_id=54321,
                staff_user_id=12345,
                guild_id=67890,
                channel_id=11111
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            
            audit_data = call_args[1]['extra']['audit_data']
            assert audit_data['event_type'] == "USER_ADDED"
            assert audit_data['added_user_id'] == 54321
            assert audit_data['user_id'] == 12345
    
    def test_log_user_removed(self):
        """Test logging user removal event."""
        with patch.object(self.audit_logger.logger, 'info') as mock_info:
            self.audit_logger.log_user_removed(
                ticket_id="ABC123",
                removed_user_id=54321,
                staff_user_id=12345,
                guild_id=67890,
                channel_id=11111
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            
            audit_data = call_args[1]['extra']['audit_data']
            assert audit_data['event_type'] == "USER_REMOVED"
            assert audit_data['removed_user_id'] == 54321
    
    def test_log_command_used(self):
        """Test logging command usage event."""
        with patch.object(self.audit_logger.logger, 'info') as mock_info:
            self.audit_logger.log_command_used(
                command_name="new_ticket",
                user_id=12345,
                guild_id=67890,
                channel_id=11111,
                success=True
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            
            audit_data = call_args[1]['extra']['audit_data']
            assert audit_data['event_type'] == "COMMAND_USED"
            assert audit_data['command_name'] == "new_ticket"
            assert audit_data['success'] is True
    
    def test_log_permission_denied(self):
        """Test logging permission denied event."""
        with patch.object(self.audit_logger.logger, 'info') as mock_info:
            self.audit_logger.log_permission_denied(
                command_name="close_ticket",
                user_id=12345,
                guild_id=67890,
                channel_id=11111,
                required_permission="staff_role"
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            
            audit_data = call_args[1]['extra']['audit_data']
            assert audit_data['event_type'] == "PERMISSION_DENIED"
            assert audit_data['command_name'] == "close_ticket"
            assert audit_data['required_permission'] == "staff_role"
    
    def test_log_configuration_changed(self):
        """Test logging configuration change event."""
        with patch.object(self.audit_logger.logger, 'info') as mock_info:
            self.audit_logger.log_configuration_changed(
                user_id=12345,
                guild_id=67890,
                setting_name="staff_roles",
                old_value=[111, 222],
                new_value=[111, 222, 333]
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            
            audit_data = call_args[1]['extra']['audit_data']
            assert audit_data['event_type'] == "CONFIG_CHANGED"
            assert audit_data['setting_name'] == "staff_roles"
            assert audit_data['old_value'] == "[111, 222]"
            assert audit_data['new_value'] == "[111, 222, 333]"
    
    def test_log_error_occurred(self):
        """Test logging error occurrence event."""
        with patch.object(self.audit_logger.logger, 'info') as mock_info:
            self.audit_logger.log_error_occurred(
                error_type="DatabaseError",
                error_message="Connection failed",
                user_id=12345,
                guild_id=67890,
                ticket_id="ABC123"
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            
            audit_data = call_args[1]['extra']['audit_data']
            assert audit_data['event_type'] == "ERROR_OCCURRED"
            assert audit_data['error_type'] == "DatabaseError"
            assert audit_data['error_message'] == "Connection failed"


class TestFormatters:
    """Test log formatters."""
    
    def test_ticket_bot_formatter_basic(self):
        """Test basic TicketBotFormatter functionality."""
        formatter = TicketBotFormatter(use_colors=False)
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        assert "test.logger" in formatted
        assert "INFO" in formatted
        assert "Test message" in formatted
    
    def test_ticket_bot_formatter_with_colors(self):
        """Test TicketBotFormatter with colors enabled."""
        formatter = TicketBotFormatter(use_colors=True)
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        assert "\033[31m" in formatted  # Red color for ERROR
        assert "\033[0m" in formatted   # Reset color
    
    def test_ticket_bot_formatter_with_extra(self):
        """Test TicketBotFormatter with extra information."""
        formatter = TicketBotFormatter(use_colors=False, include_extra=True)
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.user_id = 12345
        record.ticket_id = "ABC123"
        
        formatted = formatter.format(record)
        assert "user_id=12345" in formatted
        assert "ticket_id=ABC123" in formatted
    
    def test_audit_formatter(self):
        """Test AuditFormatter functionality."""
        formatter = AuditFormatter()
        
        record = logging.LogRecord(
            name="audit",
            level=logging.INFO,
            pathname="audit.py",
            lineno=20,
            msg="Audit event",
            args=(),
            exc_info=None
        )
        record.audit_data = {
            'event_type': 'TICKET_CREATED',
            'ticket_id': 'ABC123',
            'user_id': 12345
        }
        
        formatted = formatter.format(record)
        audit_entry = json.loads(formatted)
        
        assert audit_entry['message'] == "Audit event"
        assert audit_entry['event_type'] == "TICKET_CREATED"
        assert audit_entry['ticket_id'] == "ABC123"
        assert audit_entry['user_id'] == 12345
        assert 'timestamp' in audit_entry
    
    def test_audit_formatter_with_exception(self):
        """Test AuditFormatter with exception information."""
        formatter = AuditFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="audit",
            level=logging.ERROR,
            pathname="audit.py",
            lineno=20,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        
        formatted = formatter.format(record)
        audit_entry = json.loads(formatted)
        
        assert 'exception' in audit_entry
        assert "ValueError: Test exception" in audit_entry['exception']
    
    def test_performance_formatter(self):
        """Test PerformanceFormatter functionality."""
        formatter = PerformanceFormatter()
        
        record = logging.LogRecord(
            name="performance",
            level=logging.INFO,
            pathname="perf.py",
            lineno=30,
            msg="Operation completed",
            args=(),
            exc_info=None
        )
        record.duration = 1.234
        record.memory_usage = 45.6
        record.operation = "ticket_creation"
        
        formatted = formatter.format(record)
        
        assert "PERF" in formatted
        assert "Operation completed" in formatted
        assert "Duration: 1.234s" in formatted
        assert "Memory: 45.6MB" in formatted
        assert "Operation: ticket_creation" in formatted


class TestGlobalFunctions:
    """Test global logging functions."""
    
    def test_setup_logging(self):
        """Test global setup_logging function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = setup_logging(log_dir=temp_dir, log_level="DEBUG")
            
            assert isinstance(logger, TicketBotLogger)
            assert logger.log_level == logging.DEBUG
    
    def test_get_logger(self):
        """Test global get_logger function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup_logging(log_dir=temp_dir)
            
            logger = get_logger("test.module")
            assert isinstance(logger, logging.Logger)
            assert logger.name == "test.module"
    
    def test_get_audit_logger(self):
        """Test global get_audit_logger function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup_logging(log_dir=temp_dir)
            
            audit_logger = get_audit_logger()
            assert isinstance(audit_logger, AuditLogger)
    
    def test_get_logger_without_setup(self):
        """Test get_logger automatically sets up logging if not done."""
        # Reset global state
        import logging_config.logger
        logging_config.logger._logger_instance = None
        logging_config.logger._audit_logger_instance = None
        
        logger = get_logger("test.auto")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.auto"


if __name__ == "__main__":
    pytest.main([__file__])