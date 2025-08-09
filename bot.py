#!/usr/bin/env python3
"""
Discord Ticket Bot - Main Entry Point

A comprehensive ticket management system for Discord servers with support
for multiple database backends and modular command structure.
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging using new logging system
from logging_config import setup_logging, get_logger, get_audit_logger
from config.config_manager import ConfigManager, ConfigurationError
from database.sqlite_adapter import SQLiteAdapter
from core.ticket_manager import TicketManager

# Setup logging
log_level = os.getenv('LOG_LEVEL', 'INFO')
setup_logging(log_dir="logs", log_level=log_level)
logger = get_logger(__name__)
audit_logger = get_audit_logger()


class TicketBot(commands.Bot):
    """Main Discord bot class for ticket management system."""
    
    def __init__(self):
        # Configure bot intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.members = True
        
        # Get command prefix from environment or use default
        command_prefix = os.getenv('COMMAND_PREFIX', '!')
        
        super().__init__(
            command_prefix=command_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        
        self.database_adapter: Optional[SQLiteAdapter] = None
        self.config_manager: Optional[ConfigManager] = None
        self.ticket_manager: Optional[TicketManager] = None
        self._startup_complete = False
        self._shutdown_initiated = False
    
    async def setup_hook(self):
        """Initialize bot components and load extensions."""
        logger.info("Starting bot setup...")
        
        try:
            # Initialize core components
            await self._initialize_config()
            await self._initialize_database()
            await self._initialize_ticket_manager()
            
            # Load command extensions
            await self.load_extensions()
            
            # Sync slash commands
            await self.tree.sync()
            logger.info("Slash commands synced successfully")
            
            self._startup_complete = True
            logger.info("Bot setup completed successfully")
            
        except Exception as e:
            logger.error(f"Error during bot setup: {e}")
            await self._cleanup_on_error()
            raise
    
    async def _initialize_config(self):
        """Initialize configuration manager."""
        logger.info("Initializing configuration manager...")
        
        try:
            config_file = os.getenv('CONFIG_FILE', 'config.json')
            self.config_manager = ConfigManager(config_file)
            
            # Validate configuration
            errors = self.config_manager.validate_configuration()
            if errors:
                error_msg = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
                logger.error(error_msg)
                raise ConfigurationError(error_msg)
            
            logger.info("Configuration manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize configuration: {e}")
            raise
    
    async def _initialize_database(self):
        """Initialize database connection and test connectivity."""
        logger.info("Initializing database connection...")
        
        try:
            # Get database configuration from environment or config
            db_type = os.getenv('DATABASE_TYPE') or self.config_manager.get_global_config('database_type', 'sqlite')
            db_url = os.getenv('DATABASE_URL') or self.config_manager.get_global_config('database_url', 'tickets.db')
            
            if db_type.lower() == 'sqlite':
                self.database_adapter = SQLiteAdapter(db_url)
            else:
                raise ConfigurationError(f"Unsupported database type: {db_type}")
            
            # Test database connection
            await self.database_adapter.connect()
            
            if not await self.database_adapter.is_connected():
                raise ConnectionError("Database connection test failed")
            
            logger.info(f"Database connection established successfully ({db_type})")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def _initialize_ticket_manager(self):
        """Initialize ticket manager with database and config."""
        logger.info("Initializing ticket manager...")
        
        try:
            if not self.database_adapter:
                raise RuntimeError("Database adapter must be initialized before ticket manager")
            
            if not self.config_manager:
                raise RuntimeError("Config manager must be initialized before ticket manager")
            
            self.ticket_manager = TicketManager(self, self.database_adapter, self.config_manager)
            logger.info("Ticket manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ticket manager: {e}")
            raise
    
    async def _cleanup_on_error(self):
        """Cleanup resources when initialization fails."""
        logger.info("Cleaning up resources due to initialization error...")
        
        if self.database_adapter:
            try:
                await self.database_adapter.disconnect()
            except Exception as e:
                logger.error(f"Error during database cleanup: {e}")
        
        self.database_adapter = None
        self.config_manager = None
        self.ticket_manager = None
    
    async def load_extensions(self):
        """Dynamically load all command modules from the commands directory."""
        commands_dir = Path("commands")
        
        if not commands_dir.exists():
            logger.warning("Commands directory not found")
            return
        
        loaded_count = 0
        failed_count = 0
        
        for file_path in commands_dir.glob("*.py"):
            # Skip __init__.py and base_cog.py (not a command module)
            if file_path.name.startswith("__") or file_path.name == "base_cog.py":
                continue
                
            module_name = f"commands.{file_path.stem}"
            
            try:
                await self.load_extension(module_name)
                logger.info(f"✅ Loaded extension: {module_name}")
                loaded_count += 1
            except Exception as e:
                logger.error(f"❌ Failed to load extension {module_name}: {e}")
                failed_count += 1
        
        logger.info(f"Extension loading complete: {loaded_count} loaded, {failed_count} failed")
        
        if failed_count > 0:
            logger.warning("Some extensions failed to load. Bot will continue with available commands.")
    
    async def reload_extension_safe(self, extension_name: str) -> bool:
        """Safely reload an extension with error handling."""
        try:
            await self.reload_extension(extension_name)
            logger.info(f"✅ Reloaded extension: {extension_name}")
            return True
        except commands.ExtensionNotLoaded:
            try:
                await self.load_extension(extension_name)
                logger.info(f"✅ Loaded extension: {extension_name}")
                return True
            except Exception as e:
                logger.error(f"❌ Failed to load extension {extension_name}: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to reload extension {extension_name}: {e}")
            return False
    
    async def on_ready(self):
        """Called when the bot is ready and connected to Discord."""
        logger.info(f"{self.user} has connected to Discord!")
        logger.info(f"Bot is in {len(self.guilds)} guilds")
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="for tickets | /help"
        )
        await self.change_presence(activity=activity)
    
    async def on_error(self, event, *args, **kwargs):
        """Global error handler for bot events."""
        logger.error(f"Error in event {event}: {args}", exc_info=True)
    
    async def close(self):
        """Cleanup when bot is shutting down."""
        if self._shutdown_initiated:
            return
        
        self._shutdown_initiated = True
        logger.info("Bot is shutting down...")
        
        try:
            # Close database connections
            if self.database_adapter:
                logger.info("Closing database connection...")
                await self.database_adapter.disconnect()
                logger.info("Database connection closed")
            
            # Save configuration if needed
            if self.config_manager:
                try:
                    self.config_manager.save_configuration()
                    logger.info("Configuration saved")
                except Exception as e:
                    logger.error(f"Error saving configuration: {e}")
            
            # Log shutdown completion
            audit_logger.info("Bot shutdown completed successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown cleanup: {e}")
        finally:
            await super().close()
    
    def is_ready_for_operation(self) -> bool:
        """Check if bot is fully initialized and ready for operation."""
        return (
            self._startup_complete and
            not self._shutdown_initiated and
            self.database_adapter is not None and
            self.config_manager is not None and
            self.ticket_manager is not None
        )


def validate_environment() -> bool:
    """
    Validate required environment variables and configuration.
    
    Returns:
        bool: True if environment is valid, False otherwise
    """
    logger.info("Validating environment configuration...")
    
    required_vars = ['DISCORD_TOKEN']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file or environment configuration")
        return False
    
    # Validate optional environment variables
    db_type = os.getenv('DATABASE_TYPE', 'sqlite')
    valid_db_types = ['sqlite', 'mysql', 'mongodb']
    
    if db_type.lower() not in valid_db_types:
        logger.error(f"Invalid DATABASE_TYPE: {db_type}. Must be one of: {', '.join(valid_db_types)}")
        return False
    
    # Validate log level
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    
    if log_level.upper() not in valid_log_levels:
        logger.warning(f"Invalid LOG_LEVEL: {log_level}. Using INFO instead")
    
    logger.info("Environment validation completed successfully")
    return True


async def shutdown_handler(bot: TicketBot, signal_name: str = None):
    """
    Handle graceful shutdown of the bot.
    
    Args:
        bot: The bot instance to shutdown
        signal_name: Name of the signal that triggered shutdown (if any)
    """
    if signal_name:
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")
    else:
        logger.info("Initiating graceful shutdown...")
    
    try:
        # Give the bot a moment to finish current operations
        await asyncio.sleep(1)
        
        # Close the bot
        await bot.close()
        
        logger.info("Graceful shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during graceful shutdown: {e}")
    finally:
        # Force exit if needed
        sys.exit(0)


def setup_signal_handlers(bot: TicketBot):
    """
    Setup signal handlers for graceful shutdown.
    
    Args:
        bot: The bot instance
    """
    def signal_handler(signum, frame):
        signal_name = signal.Signals(signum).name
        logger.info(f"Received signal {signal_name}")
        
        # Create a new event loop if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Schedule shutdown
        loop.create_task(shutdown_handler(bot, signal_name))
    
    # Register signal handlers for Unix systems
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, signal_handler)


async def main():
    """Main function to start the bot with proper initialization and error handling."""
    logger.info("Starting Discord Ticket Bot...")
    
    # Validate environment before starting
    if not validate_environment():
        logger.error("Environment validation failed. Exiting.")
        sys.exit(1)
    
    # Get Discord token
    token = os.getenv('DISCORD_TOKEN')
    
    # Create bot instance
    bot = TicketBot()
    
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers(bot)
    
    try:
        logger.info("Connecting to Discord...")
        await bot.start(token)
        
    except discord.LoginFailure:
        logger.error("Invalid Discord token. Please check your DISCORD_TOKEN environment variable.")
        sys.exit(1)
        
    except discord.HTTPException as e:
        logger.error(f"HTTP error connecting to Discord: {e}")
        sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
        
    finally:
        # Ensure cleanup happens
        if not bot._shutdown_initiated:
            await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot startup interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error during bot startup: {e}", exc_info=True)
        sys.exit(1)