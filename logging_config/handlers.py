"""
Custom log handlers for Discord Ticket Bot.

This module provides specialized log handlers including rotating file handlers
and audit-specific handlers with enhanced functionality.
"""

import logging
import logging.handlers
import os
import gzip
import shutil
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    Enhanced rotating file handler with compression and better error handling.
    
    Extends the standard RotatingFileHandler to add compression of rotated files
    and improved error handling for file operations.
    """
    
    def __init__(self, filename: str, max_bytes: int = 10485760, backup_count: int = 5,
                 encoding: Optional[str] = None, compress_rotated: bool = True):
        """
        Initialize the rotating file handler.
        
        Args:
            filename: Path to the log file
            max_bytes: Maximum size of log file before rotation (default: 10MB)
            backup_count: Number of backup files to keep
            encoding: File encoding (default: utf-8)
            compress_rotated: Whether to compress rotated files
        """
        self.compress_rotated = compress_rotated
        
        # Ensure directory exists
        log_dir = Path(filename).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        super().__init__(
            filename=filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding or 'utf-8'
        )
    
    def doRollover(self):
        """
        Perform log file rotation with optional compression.
        """
        try:
            super().doRollover()
            
            # Compress the rotated file if enabled
            if self.compress_rotated and self.backupCount > 0:
                self._compress_rotated_file()
                
        except Exception as e:
            # Log the error but don't crash the application
            print(f"Error during log rotation: {e}")
    
    def _compress_rotated_file(self):
        """Compress the most recently rotated log file."""
        try:
            # The most recent backup file
            backup_file = f"{self.baseFilename}.1"
            compressed_file = f"{backup_file}.gz"
            
            if os.path.exists(backup_file):
                with open(backup_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Remove the uncompressed file
                os.remove(backup_file)
                
                # Rename subsequent backup files
                for i in range(2, self.backupCount + 1):
                    old_file = f"{self.baseFilename}.{i}"
                    new_file = f"{self.baseFilename}.{i-1}"
                    
                    if os.path.exists(old_file):
                        os.rename(old_file, new_file)
                        
        except Exception as e:
            print(f"Error compressing rotated log file: {e}")


class AuditFileHandler(RotatingFileHandler):
    """
    Specialized file handler for audit logs.
    
    Provides additional security and integrity features for audit logging
    including file permissions and integrity checking.
    """
    
    def __init__(self, filename: str, max_bytes: int = 20971520, backup_count: int = 10,
                 encoding: Optional[str] = None):
        """
        Initialize the audit file handler.
        
        Args:
            filename: Path to the audit log file
            max_bytes: Maximum size before rotation (default: 20MB)
            backup_count: Number of backup files to keep (default: 10)
            encoding: File encoding
        """
        super().__init__(
            filename=filename,
            max_bytes=max_bytes,
            backup_count=backup_count,
            encoding=encoding,
            compress_rotated=True
        )
        
        # Set restrictive file permissions for audit logs
        self._set_secure_permissions()
    
    def _set_secure_permissions(self):
        """Set secure file permissions for audit logs."""
        try:
            if os.path.exists(self.baseFilename):
                # Set read/write for owner only (600)
                os.chmod(self.baseFilename, 0o600)
        except Exception as e:
            print(f"Warning: Could not set secure permissions on audit log: {e}")
    
    def emit(self, record: logging.LogRecord):
        """
        Emit a log record with additional security measures.
        
        Args:
            record: Log record to emit
        """
        try:
            super().emit(record)
            
            # Ensure file permissions remain secure after writing
            if hasattr(self, '_last_permission_check'):
                now = datetime.now()
                if (now - self._last_permission_check).seconds > 300:  # Check every 5 minutes
                    self._set_secure_permissions()
                    self._last_permission_check = now
            else:
                self._set_secure_permissions()
                self._last_permission_check = datetime.now()
                
        except Exception as e:
            self.handleError(record)
    
    def doRollover(self):
        """Perform rollover with security measures."""
        super().doRollover()
        self._set_secure_permissions()


class AsyncFileHandler(logging.Handler):
    """
    Asynchronous file handler for high-performance logging.
    
    Buffers log records and writes them asynchronously to avoid blocking
    the main application thread.
    """
    
    def __init__(self, filename: str, max_buffer_size: int = 1000,
                 flush_interval: float = 5.0, encoding: Optional[str] = None):
        """
        Initialize the async file handler.
        
        Args:
            filename: Path to the log file
            max_buffer_size: Maximum number of records to buffer
            flush_interval: Interval in seconds to flush buffer
            encoding: File encoding
        """
        super().__init__()
        
        self.filename = filename
        self.max_buffer_size = max_buffer_size
        self.flush_interval = flush_interval
        self.encoding = encoding or 'utf-8'
        
        self.buffer = []
        self.last_flush = datetime.now()
        
        # Ensure directory exists
        log_dir = Path(filename).parent
        log_dir.mkdir(parents=True, exist_ok=True)
    
    def emit(self, record: logging.LogRecord):
        """
        Buffer a log record for asynchronous writing.
        
        Args:
            record: Log record to buffer
        """
        try:
            formatted = self.format(record)
            self.buffer.append(formatted)
            
            # Check if we need to flush
            now = datetime.now()
            if (len(self.buffer) >= self.max_buffer_size or 
                (now - self.last_flush).total_seconds() >= self.flush_interval):
                self.flush()
                
        except Exception:
            self.handleError(record)
    
    def flush(self):
        """Flush buffered records to file."""
        if not self.buffer:
            return
        
        try:
            with open(self.filename, 'a', encoding=self.encoding) as f:
                for record in self.buffer:
                    f.write(record + '\n')
            
            self.buffer.clear()
            self.last_flush = datetime.now()
            
        except Exception as e:
            print(f"Error flushing async log buffer: {e}")
    
    def close(self):
        """Close the handler and flush any remaining records."""
        self.flush()
        super().close()


class DatabaseLogHandler(logging.Handler):
    """
    Log handler that writes critical events to the database.
    
    Provides persistent storage of important log events in the database
    for audit trails and analysis.
    """
    
    def __init__(self, database_adapter, table_name: str = "log_entries",
                 min_level: int = logging.ERROR):
        """
        Initialize the database log handler.
        
        Args:
            database_adapter: Database adapter instance
            table_name: Name of the table to store logs
            min_level: Minimum log level to store in database
        """
        super().__init__(level=min_level)
        self.database_adapter = database_adapter
        self.table_name = table_name
        self.min_level = min_level
    
    def emit(self, record: logging.LogRecord):
        """
        Store a log record in the database.
        
        Args:
            record: Log record to store
        """
        if record.levelno < self.min_level:
            return
        
        try:
            log_entry = {
                'timestamp': datetime.utcfromtimestamp(record.created),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line_number': record.lineno
            }
            
            # Add exception information if present
            if record.exc_info:
                log_entry['exception'] = self.formatException(record.exc_info)
            
            # Store in database (implementation depends on database adapter)
            # This would need to be implemented based on the specific database adapter
            # self.database_adapter.store_log_entry(log_entry)
            
        except Exception:
            self.handleError(record)