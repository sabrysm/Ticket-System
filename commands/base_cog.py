"""
Base Cog Class

Provides common functionality and error handling for all command cogs.
"""

import logging
from typing import Optional, List, Callable, Any
from functools import wraps

import discord
from discord.ext import commands
from discord import app_commands


logger = logging.getLogger(__name__)


class TicketBotError(Exception):
    """Base exception for ticket bot errors."""
    pass


class PermissionError(TicketBotError):
    """User permission errors."""
    pass


class ConfigurationError(TicketBotError):
    """Configuration-related errors."""
    pass


def require_staff_role():
    """Decorator to check if user has staff role permissions."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            # Check if user has staff permissions
            if not await self.check_staff_permissions(interaction.user, interaction.guild):
                embed = discord.Embed(
                    title="❌ Permission Denied",
                    description="You don't have permission to use this command. Staff role required.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator


def require_admin_role():
    """Decorator to check if user has admin permissions."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            # Check if user has admin permissions
            if not (interaction.user.guild_permissions.administrator or 
                   await self.check_admin_permissions(interaction.user, interaction.guild)):
                embed = discord.Embed(
                    title="❌ Permission Denied",
                    description="You don't have permission to use this command. Administrator role required.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator


def handle_errors(func: Callable) -> Callable:
    """Decorator to handle common errors in command functions."""
    @wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        try:
            return await func(self, interaction, *args, **kwargs)
        except PermissionError as e:
            embed = discord.Embed(
                title="❌ Permission Error",
                description=str(e),
                color=discord.Color.red()
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except ConfigurationError as e:
            embed = discord.Embed(
                title="⚙️ Configuration Error",
                description=f"Bot configuration issue: {str(e)}",
                color=discord.Color.orange()
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except TicketBotError as e:
            embed = discord.Embed(
                title="❌ Error",
                description=str(e),
                color=discord.Color.red()
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ Unexpected Error",
                description="An unexpected error occurred. Please try again later.",
                color=discord.Color.red()
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
    return wrapper


class BaseCog(commands.Cog):
    """Base cog class with common functionality for all command cogs."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def check_staff_permissions(self, user: discord.Member, guild: discord.Guild) -> bool:
        """Check if user has staff role permissions."""
        try:
            # Get guild configuration (will be implemented when config manager is available)
            if hasattr(self.bot, 'config_manager') and self.bot.config_manager:
                guild_config = self.bot.config_manager.get_guild_config(guild.id)
                staff_roles = guild_config.staff_roles if guild_config else []
                
                # Check if user has any of the configured staff roles
                user_role_ids = [role.id for role in user.roles]
                return any(role_id in user_role_ids for role_id in staff_roles)
            
            # Fallback: check for common staff role names or admin permissions
            return (user.guild_permissions.administrator or 
                   user.guild_permissions.manage_channels or
                   any(role.name.lower() in ['staff', 'moderator', 'admin', 'support'] 
                       for role in user.roles))
        except Exception as e:
            self.logger.error(f"Error checking staff permissions: {e}")
            return False
    
    async def check_admin_permissions(self, user: discord.Member, guild: discord.Guild) -> bool:
        """Check if user has admin permissions."""
        try:
            # Get guild configuration (will be implemented when config manager is available)
            if hasattr(self.bot, 'config_manager') and self.bot.config_manager:
                guild_config = self.bot.config_manager.get_guild_config(guild.id)
                admin_roles = guild_config.admin_roles if guild_config and hasattr(guild_config, 'admin_roles') else []
                
                # Check if user has any of the configured admin roles
                user_role_ids = [role.id for role in user.roles]
                return any(role_id in user_role_ids for role_id in admin_roles)
            
            # Fallback: check for admin permissions
            return user.guild_permissions.administrator
        except Exception as e:
            self.logger.error(f"Error checking admin permissions: {e}")
            return False
    
    async def send_error_embed(self, interaction: discord.Interaction, title: str, description: str, 
                              color: discord.Color = discord.Color.red(), ephemeral: bool = True):
        """Send a standardized error embed."""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
    
    async def send_success_embed(self, interaction: discord.Interaction, title: str, description: str,
                                ephemeral: bool = False):
        """Send a standardized success embed."""
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.green()
        )
        
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
    
    async def cog_load(self):
        """Called when the cog is loaded."""
        self.logger.info(f"{self.__class__.__name__} cog loaded")
    
    async def cog_unload(self):
        """Called when the cog is unloaded."""
        self.logger.info(f"{self.__class__.__name__} cog unloaded")
    
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle application command errors."""
        self.logger.error(f"App command error in {interaction.command}: {error}")
        
        if isinstance(error, app_commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ Command on Cooldown",
                description=f"Please wait {error.retry_after:.1f} seconds before using this command again.",
                color=discord.Color.orange()
            )
        elif isinstance(error, app_commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description="You don't have the required permissions to use this command.",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="❌ Command Error",
                description="An error occurred while executing the command.",
                color=discord.Color.red()
            )
        
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)