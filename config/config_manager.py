"""
Configuration management system for the Discord Ticket Bot.

This module provides configuration loading, validation, and management
for both global bot settings and per-server (guild) configurations.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class GuildConfig:
    """Configuration settings for a specific Discord guild (server)."""
    
    guild_id: int
    staff_roles: List[int] = field(default_factory=list)
    ticket_category: Optional[int] = None
    log_channel: Optional[int] = None
    embed_settings: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not isinstance(self.guild_id, int) or self.guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {self.guild_id}")
        
        if not isinstance(self.staff_roles, list):
            raise ValueError("staff_roles must be a list")
        
        # Validate staff roles are integers
        for role_id in self.staff_roles:
            if not isinstance(role_id, int) or role_id <= 0:
                raise ValueError(f"Invalid staff role ID: {role_id}")
        
        # Validate optional channel IDs
        if self.ticket_category is not None:
            if not isinstance(self.ticket_category, int) or self.ticket_category <= 0:
                raise ValueError(f"Invalid ticket_category: {self.ticket_category}")
        
        if self.log_channel is not None:
            if not isinstance(self.log_channel, int) or self.log_channel <= 0:
                raise ValueError(f"Invalid log_channel: {self.log_channel}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert GuildConfig to dictionary for serialization."""
        return {
            'guild_id': self.guild_id,
            'staff_roles': self.staff_roles,
            'ticket_category': self.ticket_category,
            'log_channel': self.log_channel,
            'embed_settings': self.embed_settings
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GuildConfig':
        """Create GuildConfig from dictionary."""
        return cls(
            guild_id=data['guild_id'],
            staff_roles=data.get('staff_roles', []),
            ticket_category=data.get('ticket_category'),
            log_channel=data.get('log_channel'),
            embed_settings=data.get('embed_settings', {})
        )


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors."""
    pass


class ConfigManager:
    """Manages bot configuration including global settings and per-guild configurations."""
    
    def __init__(self, config_file: str = "config.json"):
        """
        Initialize ConfigManager.
        
        Args:
            config_file: Path to the main configuration file
        """
        self.config_file = Path(config_file)
        self.guild_configs: Dict[int, GuildConfig] = {}
        self.global_config: Dict[str, Any] = {}
        self._load_configuration()
    
    def _load_configuration(self):
        """Load configuration from file with error handling."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # Load global configuration
                self.global_config = config_data.get('global', {})
                
                # Load guild configurations
                guild_configs_data = config_data.get('guilds', {})
                for guild_id_str, guild_data in guild_configs_data.items():
                    try:
                        guild_id = int(guild_id_str)
                        guild_data['guild_id'] = guild_id
                        guild_config = GuildConfig.from_dict(guild_data)
                        self.guild_configs[guild_id] = guild_config
                    except (ValueError, TypeError) as e:
                        logger.error(f"Invalid guild configuration for {guild_id_str}: {e}")
                        raise ConfigurationError(f"Invalid guild configuration for {guild_id_str}: {e}")
                
                logger.info(f"Configuration loaded successfully from {self.config_file}")
            else:
                logger.info(f"Configuration file {self.config_file} not found, using defaults")
                self._create_default_config()
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise ConfigurationError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise ConfigurationError(f"Error loading configuration: {e}")
    
    def _create_default_config(self):
        """Create default configuration file."""
        default_config = {
            'global': {
                'database_type': 'sqlite',
                'database_url': 'tickets.db',
                'log_level': 'INFO'
            },
            'guilds': {}
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
            
            self.global_config = default_config['global']
            logger.info(f"Created default configuration file at {self.config_file}")
            
        except Exception as e:
            logger.error(f"Error creating default configuration: {e}")
            raise ConfigurationError(f"Error creating default configuration: {e}")
    
    def get_guild_config(self, guild_id: int) -> GuildConfig:
        """
        Get configuration for a specific guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            GuildConfig for the specified guild
            
        Raises:
            ConfigurationError: If guild_id is invalid
        """
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ConfigurationError(f"Invalid guild_id: {guild_id}")
        
        if guild_id not in self.guild_configs:
            # Create default guild config
            self.guild_configs[guild_id] = GuildConfig(guild_id=guild_id)
            logger.info(f"Created default configuration for guild {guild_id}")
        
        return self.guild_configs[guild_id]
    
    def set_guild_config(self, guild_config: GuildConfig):
        """
        Set configuration for a specific guild.
        
        Args:
            guild_config: GuildConfig object to set
        """
        if not isinstance(guild_config, GuildConfig):
            raise ConfigurationError("guild_config must be a GuildConfig instance")
        
        self.guild_configs[guild_config.guild_id] = guild_config
        logger.info(f"Updated configuration for guild {guild_config.guild_id}")
    
    def get_global_config(self, key: str, default: Any = None) -> Any:
        """
        Get a global configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self.global_config.get(key, default)
    
    def set_global_config(self, key: str, value: Any):
        """
        Set a global configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self.global_config[key] = value
        logger.info(f"Updated global configuration: {key} = {value}")
    
    def save_configuration(self):
        """Save current configuration to file."""
        try:
            config_data = {
                'global': self.global_config,
                'guilds': {
                    str(guild_id): guild_config.to_dict()
                    for guild_id, guild_config in self.guild_configs.items()
                }
            }
            
            # Create backup of existing config
            if self.config_file.exists():
                backup_file = self.config_file.with_suffix('.bak')
                self.config_file.rename(backup_file)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Configuration saved to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            raise ConfigurationError(f"Error saving configuration: {e}")
    
    def validate_configuration(self) -> List[str]:
        """
        Validate the current configuration.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate global configuration
        required_global_keys = ['database_type', 'database_url']
        for key in required_global_keys:
            if key not in self.global_config:
                errors.append(f"Missing required global configuration: {key}")
        
        # Validate database type
        valid_db_types = ['sqlite', 'mysql', 'mongodb']
        db_type = self.global_config.get('database_type')
        if db_type and db_type not in valid_db_types:
            errors.append(f"Invalid database_type: {db_type}. Must be one of {valid_db_types}")
        
        # Validate guild configurations
        for guild_id, guild_config in self.guild_configs.items():
            try:
                # GuildConfig validation is handled in __post_init__
                pass
            except ValueError as e:
                errors.append(f"Invalid guild configuration for {guild_id}: {e}")
        
        return errors
    
    def reload_configuration(self):
        """Reload configuration from file."""
        self.guild_configs.clear()
        self.global_config.clear()
        self._load_configuration()
        logger.info("Configuration reloaded")