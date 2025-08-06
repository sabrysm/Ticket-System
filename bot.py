#!/usr/bin/env python3
"""
Discord Ticket Bot - Main Entry Point

A comprehensive ticket management system for Discord servers with support
for multiple database backends and modular command structure.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class TicketBot(commands.Bot):
    """Main Discord bot class for ticket management system."""
    
    def __init__(self):
        # Configure bot intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.members = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        
        self.database_manager: Optional[object] = None
        self.config_manager: Optional[object] = None
        self.ticket_manager: Optional[object] = None
    
    async def setup_hook(self):
        """Initialize bot components and load extensions."""
        logger.info("Starting bot setup...")
        
        try:
            # Initialize core components (will be implemented in later tasks)
            # await self._initialize_database()
            # await self._initialize_config()
            # await self._initialize_ticket_manager()
            
            # Load command extensions
            await self.load_extensions()
            
            # Sync slash commands
            await self.tree.sync()
            logger.info("Slash commands synced successfully")
            
        except Exception as e:
            logger.error(f"Error during bot setup: {e}")
            raise
    
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
        logger.info("Bot is shutting down...")
        
        # Close database connections (will be implemented in later tasks)
        # if self.database_manager:
        #     await self.database_manager.close()
        
        await super().close()


async def main():
    """Main function to start the bot."""
    # Check for required environment variables
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN environment variable is required")
        return
    
    # Create and start bot
    bot = TicketBot()
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot encountered an error: {e}")
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())