#!/usr/bin/env python3
"""
Startup validation script for Discord Ticket Bot.

This script validates the bot's configuration, dependencies, and environment
before starting the bot to ensure proper deployment.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple

import discord
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import bot components for validation
from config.config_manager import ConfigManager, ConfigurationError
from database.sqlite_adapter import SQLiteAdapter
from logging_config import setup_logging, get_logger

# Setup logging for validation
setup_logging(log_dir="logs", log_level="INFO")
logger = get_logger(__name__)


class ValidationError(Exception):
    """Exception raised when validation fails."""
    pass


class StartupValidator:
    """Validates bot startup requirements and configuration."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.config_manager: ConfigManager = None
        self.database_adapter: SQLiteAdapter = None
    
    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(message)
        logger.error(f"Validation Error: {message}")
    
    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
        logger.warning(f"Validation Warning: {message}")
    
    def validate_environment_variables(self) -> bool:
        """Validate required and optional environment variables."""
        logger.info("Validating environment variables...")
        
        # Required variables
        required_vars = {
            'DISCORD_TOKEN': 'Discord bot token'
        }
        
        for var, description in required_vars.items():
            value = os.getenv(var)
            if not value:
                self.add_error(f"Missing required environment variable: {var} ({description})")
            elif var == 'DISCORD_TOKEN' and len(value) < 50:
                self.add_error(f"Invalid {var}: Token appears to be too short")
        
        # Optional variables with validation
        optional_vars = {
            'DATABASE_TYPE': ('sqlite', ['sqlite', 'mysql', 'mongodb']),
            'LOG_LEVEL': ('INFO', ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),
            'COMMAND_PREFIX': ('!', None)
        }
        
        for var, (default, valid_values) in optional_vars.items():
            value = os.getenv(var, default)
            if valid_values and value not in valid_values:
                self.add_error(f"Invalid {var}: '{value}'. Must be one of: {', '.join(valid_values)}")
        
        return len(self.errors) == 0
    
    def validate_file_structure(self) -> bool:
        """Validate required files and directories exist."""
        logger.info("Validating file structure...")
        
        required_files = [
            'bot.py',
            'requirements.txt',
            '.env.example'
        ]
        
        required_dirs = [
            'commands',
            'config',
            'database',
            'core',
            'models',
            'logging_config',
            'errors'
        ]
        
        for file_path in required_files:
            if not Path(file_path).exists():
                self.add_error(f"Missing required file: {file_path}")
        
        for dir_path in required_dirs:
            if not Path(dir_path).exists():
                self.add_error(f"Missing required directory: {dir_path}")
            elif not Path(dir_path).is_dir():
                self.add_error(f"Path exists but is not a directory: {dir_path}")
        
        # Check for __init__.py files in Python packages
        python_packages = ['commands', 'config', 'database', 'core', 'models', 'logging_config', 'errors']
        for package in python_packages:
            init_file = Path(package) / '__init__.py'
            if Path(package).exists() and not init_file.exists():
                self.add_warning(f"Missing __init__.py in package: {package}")
        
        return len(self.errors) == 0
    
    def validate_configuration(self) -> bool:
        """Validate bot configuration."""
        logger.info("Validating configuration...")
        
        try:
            config_file = os.getenv('CONFIG_FILE', 'config.json')
            self.config_manager = ConfigManager(config_file)
            
            # Validate configuration
            config_errors = self.config_manager.validate_configuration()
            for error in config_errors:
                self.add_error(f"Configuration error: {error}")
            
            # Check global configuration
            global_config = self.config_manager.global_config
            if not global_config:
                self.add_warning("No global configuration found, using defaults")
            
            return len(config_errors) == 0
            
        except ConfigurationError as e:
            self.add_error(f"Configuration validation failed: {e}")
            return False
        except Exception as e:
            self.add_error(f"Unexpected error validating configuration: {e}")
            return False
    
    async def validate_database_connection(self) -> bool:
        """Validate database connection and schema."""
        logger.info("Validating database connection...")
        
        try:
            # Get database configuration
            db_type = os.getenv('DATABASE_TYPE', 'sqlite')
            db_url = os.getenv('DATABASE_URL', 'tickets.db')
            
            if db_type.lower() == 'sqlite':
                self.database_adapter = SQLiteAdapter(db_url)
            else:
                self.add_error(f"Unsupported database type for validation: {db_type}")
                return False
            
            # Test connection
            await self.database_adapter.connect()
            
            if not await self.database_adapter.is_connected():
                self.add_error("Database connection test failed")
                return False
            
            logger.info("Database connection validated successfully")
            return True
            
        except Exception as e:
            self.add_error(f"Database validation failed: {e}")
            return False
        finally:
            if self.database_adapter:
                try:
                    await self.database_adapter.disconnect()
                except Exception:
                    pass
    
    def validate_discord_permissions(self) -> bool:
        """Validate Discord bot permissions and intents."""
        logger.info("Validating Discord configuration...")
        
        # Check if token format is valid
        token = os.getenv('DISCORD_TOKEN')
        if token:
            # Basic token format validation
            if not token.startswith(('Bot ', 'Bearer ')):
                # Token should be just the token part for discord.py
                if len(token.split('.')) != 3:
                    self.add_warning("Discord token format may be invalid")
        
        # Validate required intents
        required_intents = [
            'guilds',
            'guild_messages',
            'message_content',
            'members'
        ]
        
        # Note: We can't actually test intents without connecting to Discord
        # This is more of a documentation check
        logger.info(f"Required Discord intents: {', '.join(required_intents)}")
        
        return True
    
    def validate_dependencies(self) -> bool:
        """Validate Python dependencies are installed."""
        logger.info("Validating Python dependencies...")
        
        required_modules = [
            'discord',
            'aiosqlite',
            'python-dotenv'
        ]
        
        for module in required_modules:
            try:
                __import__(module.replace('-', '_'))
            except ImportError:
                self.add_error(f"Missing required Python module: {module}")
        
        return len(self.errors) == 0
    
    async def run_full_validation(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Run complete validation suite.
        
        Returns:
            Tuple of (success, results_dict)
        """
        logger.info("Starting full validation suite...")
        
        validation_results = {
            'environment': self.validate_environment_variables(),
            'file_structure': self.validate_file_structure(),
            'configuration': self.validate_configuration(),
            'database': await self.validate_database_connection(),
            'discord': self.validate_discord_permissions(),
            'dependencies': self.validate_dependencies()
        }
        
        success = all(validation_results.values())
        
        results = {
            'success': success,
            'validations': validation_results,
            'errors': self.errors,
            'warnings': self.warnings,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }
        
        return success, results
    
    def print_validation_report(self, results: Dict[str, Any]):
        """Print a formatted validation report."""
        print("\n" + "="*60)
        print("DISCORD TICKET BOT - STARTUP VALIDATION REPORT")
        print("="*60)
        
        # Print validation results
        for validation, passed in results['validations'].items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{validation.upper():.<20} {status}")
        
        print("-"*60)
        
        # Print errors
        if results['errors']:
            print(f"\n❌ ERRORS ({len(results['errors'])}):")
            for i, error in enumerate(results['errors'], 1):
                print(f"  {i}. {error}")
        
        # Print warnings
        if results['warnings']:
            print(f"\n⚠️  WARNINGS ({len(results['warnings'])}):")
            for i, warning in enumerate(results['warnings'], 1):
                print(f"  {i}. {warning}")
        
        # Print summary
        print("\n" + "="*60)
        if results['success']:
            print("✅ VALIDATION PASSED - Bot is ready for deployment!")
        else:
            print("❌ VALIDATION FAILED - Please fix the errors above before starting the bot.")
        print("="*60 + "\n")


async def main():
    """Main validation function."""
    validator = StartupValidator()
    
    try:
        success, results = await validator.run_full_validation()
        validator.print_validation_report(results)
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"Validation failed with unexpected error: {e}", exc_info=True)
        print(f"\n❌ VALIDATION FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())