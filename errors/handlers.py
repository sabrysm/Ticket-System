"""
Error handling utilities and decorators for Discord Ticket Bot.

This module provides decorators and utility functions for consistent
error handling across commands and database operations.
"""

import logging
import traceback
import functools
from typing import Optional, Callable, Any, Union
from datetime import datetime

import discord
from discord.ext import commands

from .exceptions import TicketBotError, PermissionError, RateLimitError

logger = logging.getLogger(__name__)


def log_error(error: Exception, context: Optional[str] = None, 
              user_id: Optional[int] = None, guild_id: Optional[int] = None,
              additional_info: Optional[dict] = None) -> None:
    """
    Log an error with context information.
    
    Args:
        error: The exception that occurred
        context: Additional context about where the error occurred
        user_id: ID of the user involved (if applicable)
        guild_id: ID of the guild involved (if applicable)
        additional_info: Additional information to log
    """
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context,
        'user_id': user_id,
        'guild_id': guild_id,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if additional_info:
        error_info.update(additional_info)
    
    # Log with appropriate level based on error type
    if isinstance(error, TicketBotError):
        if error.error_code in ['PERMISSION_ERROR', 'VALIDATION_ERROR']:
            logger.warning(f"Bot error: {error_info}")
        else:
            logger.error(f"Bot error: {error_info}")
    else:
        logger.error(f"Unexpected error: {error_info}", exc_info=True)


def format_error_message(error: Exception, include_details: bool = False) -> str:
    """
    Format an error message for display to users.
    
    Args:
        error: The exception to format
        include_details: Whether to include technical details
        
    Returns:
        str: Formatted error message
    """
    if isinstance(error, TicketBotError):
        message = error.user_message
        if include_details and error.details:
            details = ", ".join(f"{k}: {v}" for k, v in error.details.items())
            message += f"\n\n**Details:** {details}"
        return message
    else:
        return "An unexpected error occurred. Please try again later."


async def send_error_embed(interaction_or_context: Union[discord.Interaction, commands.Context],
                          title: str, description: str, 
                          color: discord.Color = discord.Color.red(),
                          ephemeral: bool = True) -> None:
    """
    Send an error embed to the user.
    
    Args:
        interaction_or_context: Discord interaction or command context
        title: Error embed title
        description: Error embed description
        color: Embed color (default: red)
        ephemeral: Whether the message should be ephemeral (for interactions)
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="Ticket Bot Error")
    
    try:
        if isinstance(interaction_or_context, discord.Interaction):
            if interaction_or_context.response.is_done():
                await interaction_or_context.followup.send(embed=embed, ephemeral=ephemeral)
            else:
                await interaction_or_context.response.send_message(embed=embed, ephemeral=ephemeral)
        else:
            # Context from traditional commands
            await interaction_or_context.send(embed=embed)
    except discord.HTTPException as e:
        logger.error(f"Failed to send error embed: {e}")


def handle_errors(func: Callable) -> Callable:
    """
    Decorator for handling errors in command functions.
    
    This decorator catches exceptions, logs them appropriately,
    and sends user-friendly error messages.
    
    Args:
        func: The function to wrap
        
    Returns:
        Callable: Wrapped function with error handling
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract interaction/context and user info
        interaction_or_context = None
        user_id = None
        guild_id = None
        
        # Find interaction or context in arguments
        for arg in args:
            if isinstance(arg, discord.Interaction):
                interaction_or_context = arg
                user_id = arg.user.id
                guild_id = arg.guild.id if arg.guild else None
                break
            elif isinstance(arg, commands.Context):
                interaction_or_context = arg
                user_id = arg.author.id
                guild_id = arg.guild.id if arg.guild else None
                break
        
        try:
            return await func(*args, **kwargs)
            
        except PermissionError as e:
            log_error(e, context=func.__name__, user_id=user_id, guild_id=guild_id)
            
            if interaction_or_context:
                await send_error_embed(
                    interaction_or_context,
                    "❌ Permission Denied",
                    format_error_message(e),
                    color=discord.Color.orange()
                )
            
        except RateLimitError as e:
            log_error(e, context=func.__name__, user_id=user_id, guild_id=guild_id)
            
            if interaction_or_context:
                await send_error_embed(
                    interaction_or_context,
                    "⏱️ Rate Limited",
                    format_error_message(e),
                    color=discord.Color.yellow()
                )
            
        except TicketBotError as e:
            log_error(e, context=func.__name__, user_id=user_id, guild_id=guild_id)
            
            if interaction_or_context:
                await send_error_embed(
                    interaction_or_context,
                    "❌ Error",
                    format_error_message(e)
                )
            
        except discord.Forbidden as e:
            error_msg = "The bot doesn't have permission to perform this action. Please check bot permissions."
            log_error(e, context=func.__name__, user_id=user_id, guild_id=guild_id)
            
            if interaction_or_context:
                await send_error_embed(
                    interaction_or_context,
                    "❌ Permission Error",
                    error_msg
                )
            
        except discord.NotFound as e:
            error_msg = "The requested resource was not found. It may have been deleted."
            log_error(e, context=func.__name__, user_id=user_id, guild_id=guild_id)
            
            if interaction_or_context:
                await send_error_embed(
                    interaction_or_context,
                    "❌ Not Found",
                    error_msg
                )
            
        except discord.HTTPException as e:
            error_msg = "A Discord API error occurred. Please try again later."
            log_error(e, context=func.__name__, user_id=user_id, guild_id=guild_id)
            
            if interaction_or_context:
                await send_error_embed(
                    interaction_or_context,
                    "❌ API Error",
                    error_msg
                )
            
        except Exception as e:
            # Log unexpected errors with full traceback
            log_error(e, context=func.__name__, user_id=user_id, guild_id=guild_id,
                     additional_info={'traceback': traceback.format_exc()})
            
            if interaction_or_context:
                await send_error_embed(
                    interaction_or_context,
                    "❌ Unexpected Error",
                    "An unexpected error occurred. The issue has been logged and will be investigated."
                )
    
    return wrapper


def handle_database_errors(func: Callable) -> Callable:
    """
    Decorator specifically for database operation error handling.
    
    This decorator provides specialized handling for database-related
    operations with retry logic and connection management.
    
    Args:
        func: The database function to wrap
        
    Returns:
        Callable: Wrapped function with database error handling
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                return await func(*args, **kwargs)
                
            except Exception as e:
                retry_count += 1
                
                # Log the error
                log_error(e, context=f"{func.__name__} (attempt {retry_count})")
                
                # If this was the last retry, re-raise the exception
                if retry_count >= max_retries:
                    from .exceptions import DatabaseError
                    raise DatabaseError(
                        f"Database operation failed after {max_retries} attempts: {str(e)}",
                        operation=func.__name__
                    )
                
                # Wait before retrying (exponential backoff)
                import asyncio
                await asyncio.sleep(2 ** retry_count)
    
    return wrapper


def require_staff_role(error_message: Optional[str] = None) -> Callable:
    """
    Decorator to require staff role for command execution.
    
    Args:
        error_message: Custom error message for permission denial
        
    Returns:
        Callable: Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Find the interaction or context
            interaction_or_context = None
            for arg in args:
                if isinstance(arg, discord.Interaction):
                    interaction_or_context = arg
                    user = arg.user
                    guild = arg.guild
                    break
                elif isinstance(arg, commands.Context):
                    interaction_or_context = arg
                    user = arg.author
                    guild = arg.guild
                    break
            
            if not interaction_or_context or not guild:
                raise PermissionError("Command must be used in a guild")
            
            # Check if user has staff role
            # This would need to be integrated with the config manager
            # For now, we'll check for administrator permission as a fallback
            if not user.guild_permissions.administrator:
                # Try to get staff roles from bot's config manager
                try:
                    # Get the bot instance from the cog
                    bot = None
                    for arg in args:
                        if hasattr(arg, 'bot'):
                            bot = arg.bot
                            break
                    
                    if bot and hasattr(bot, 'config_manager') and bot.config_manager:
                        guild_config = bot.config_manager.get_guild_config(guild.id)
                        is_staff = any(role.id in guild_config.staff_roles for role in user.roles)
                        if not is_staff:
                            raise PermissionError(
                                f"User {user.id} does not have required staff role",
                                required_permission="staff_role",
                                user_message=error_message or "You must be a staff member to use this command."
                            )
                    else:
                        # Fallback to administrator check
                        raise PermissionError(
                            f"User {user.id} does not have administrator permission",
                            required_permission="administrator",
                            user_message=error_message or "You must be an administrator to use this command."
                        )
                except PermissionError:
                    raise
                except Exception as e:
                    logger.error(f"Error checking staff role: {e}")
                    raise PermissionError(
                        "Failed to verify permissions",
                        user_message="Permission verification failed. Please try again."
                    )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, 
                    backoff_factor: float = 2.0) -> Callable:
    """
    Decorator to retry function execution on failure.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Factor to multiply delay by for each retry
        
    Returns:
        Callable: Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        # Last attempt failed, re-raise the exception
                        raise
                    
                    # Log retry attempt
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    
                    # Wait before retrying
                    import asyncio
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff_factor
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator