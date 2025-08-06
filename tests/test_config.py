"""
Unit tests for configuration management system.
"""

import json
import os
import sys
import tempfile
import unittest
import shutil
from pathlib import Path
from unittest.mock import patch, mock_open

# Add the parent directory to the path so we can import the config module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ConfigManager, GuildConfig, ConfigurationError


class TestGuildConfig(unittest.TestCase):
    """Test cases for GuildConfig dataclass."""
    
    def test_valid_guild_config_creation(self):
        """Test creating a valid GuildConfig."""
        config = GuildConfig(
            guild_id=123456789,
            staff_roles=[111, 222, 333],
            ticket_category=444,
            log_channel=555,
            embed_settings={'title': 'Support Tickets', 'color': 0x00ff00}
        )
        
        self.assertEqual(config.guild_id, 123456789)
        self.assertEqual(config.staff_roles, [111, 222, 333])
        self.assertEqual(config.ticket_category, 444)
        self.assertEqual(config.log_channel, 555)
        self.assertEqual(config.embed_settings['title'], 'Support Tickets')
    
    def test_guild_config_with_defaults(self):
        """Test creating GuildConfig with default values."""
        config = GuildConfig(guild_id=123456789)
        
        self.assertEqual(config.guild_id, 123456789)
        self.assertEqual(config.staff_roles, [])
        self.assertIsNone(config.ticket_category)
        self.assertIsNone(config.log_channel)
        self.assertEqual(config.embed_settings, {})
    
    def test_invalid_guild_id(self):
        """Test GuildConfig with invalid guild_id."""
        with self.assertRaises(ValueError):
            GuildConfig(guild_id=0)
        
        with self.assertRaises(ValueError):
            GuildConfig(guild_id=-1)
        
        with self.assertRaises(ValueError):
            GuildConfig(guild_id="invalid")
    
    def test_invalid_staff_roles(self):
        """Test GuildConfig with invalid staff roles."""
        with self.assertRaises(ValueError):
            GuildConfig(guild_id=123, staff_roles="not_a_list")
        
        with self.assertRaises(ValueError):
            GuildConfig(guild_id=123, staff_roles=[1, 2, "invalid"])
        
        with self.assertRaises(ValueError):
            GuildConfig(guild_id=123, staff_roles=[1, 2, -1])
    
    def test_invalid_channel_ids(self):
        """Test GuildConfig with invalid channel IDs."""
        with self.assertRaises(ValueError):
            GuildConfig(guild_id=123, ticket_category=0)
        
        with self.assertRaises(ValueError):
            GuildConfig(guild_id=123, ticket_category="invalid")
        
        with self.assertRaises(ValueError):
            GuildConfig(guild_id=123, log_channel=-1)
    
    def test_to_dict(self):
        """Test converting GuildConfig to dictionary."""
        config = GuildConfig(
            guild_id=123,
            staff_roles=[111, 222],
            ticket_category=333,
            archive_category=555,
            log_channel=444,
            embed_settings={'color': 0xff0000}
        )
        
        expected = {
            'guild_id': 123,
            'staff_roles': [111, 222],
            'ticket_category': 333,
            'archive_category': 555,
            'log_channel': 444,
            'embed_settings': {'color': 0xff0000}
        }
        
        self.assertEqual(config.to_dict(), expected)
    
    def test_from_dict(self):
        """Test creating GuildConfig from dictionary."""
        data = {
            'guild_id': 123,
            'staff_roles': [111, 222],
            'ticket_category': 333,
            'log_channel': 444,
            'embed_settings': {'color': 0xff0000}
        }
        
        config = GuildConfig.from_dict(data)
        
        self.assertEqual(config.guild_id, 123)
        self.assertEqual(config.staff_roles, [111, 222])
        self.assertEqual(config.ticket_category, 333)
        self.assertEqual(config.log_channel, 444)
        self.assertEqual(config.embed_settings, {'color': 0xff0000})
    
    def test_from_dict_with_defaults(self):
        """Test creating GuildConfig from dictionary with missing optional fields."""
        data = {'guild_id': 123}
        config = GuildConfig.from_dict(data)
        
        self.assertEqual(config.guild_id, 123)
        self.assertEqual(config.staff_roles, [])
        self.assertIsNone(config.ticket_category)
        self.assertIsNone(config.log_channel)
        self.assertEqual(config.embed_settings, {})


class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.json')
    
    def tearDown(self):
        """Clean up test fixtures."""
        try:
            shutil.rmtree(self.temp_dir)
        except OSError:
            pass  # Ignore cleanup errors
    
    def test_config_manager_with_nonexistent_file(self):
        """Test ConfigManager when config file doesn't exist."""
        manager = ConfigManager(self.config_file)
        
        # Should create default configuration
        self.assertTrue(os.path.exists(self.config_file))
        self.assertEqual(manager.get_global_config('database_type'), 'sqlite')
        self.assertEqual(manager.get_global_config('database_url'), 'tickets.db')
    
    def test_config_manager_with_valid_file(self):
        """Test ConfigManager with valid configuration file."""
        config_data = {
            'global': {
                'database_type': 'mysql',
                'database_url': 'mysql://localhost/tickets',
                'log_level': 'DEBUG'
            },
            'guilds': {
                '123456789': {
                    'guild_id': 123456789,
                    'staff_roles': [111, 222],
                    'ticket_category': 333,
                    'log_channel': 444
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager(self.config_file)
        
        # Test global config
        self.assertEqual(manager.get_global_config('database_type'), 'mysql')
        self.assertEqual(manager.get_global_config('database_url'), 'mysql://localhost/tickets')
        self.assertEqual(manager.get_global_config('log_level'), 'DEBUG')
        
        # Test guild config
        guild_config = manager.get_guild_config(123456789)
        self.assertEqual(guild_config.guild_id, 123456789)
        self.assertEqual(guild_config.staff_roles, [111, 222])
        self.assertEqual(guild_config.ticket_category, 333)
        self.assertEqual(guild_config.log_channel, 444)
    
    def test_config_manager_with_invalid_json(self):
        """Test ConfigManager with invalid JSON file."""
        with open(self.config_file, 'w') as f:
            f.write('invalid json content')
        
        with self.assertRaises(ConfigurationError):
            ConfigManager(self.config_file)
    
    def test_config_manager_with_invalid_guild_config(self):
        """Test ConfigManager with invalid guild configuration."""
        config_data = {
            'global': {'database_type': 'sqlite', 'database_url': 'test.db'},
            'guilds': {
                '123': {
                    'guild_id': 123,
                    'staff_roles': [1, 2, "invalid"]  # Invalid staff role
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f)
        
        with self.assertRaises(ConfigurationError):
            ConfigManager(self.config_file)
    
    def test_get_guild_config_creates_default(self):
        """Test that getting non-existent guild config creates default."""
        manager = ConfigManager(self.config_file)
        
        guild_config = manager.get_guild_config(999999999)
        
        self.assertEqual(guild_config.guild_id, 999999999)
        self.assertEqual(guild_config.staff_roles, [])
        self.assertIsNone(guild_config.ticket_category)
    
    def test_get_guild_config_invalid_id(self):
        """Test getting guild config with invalid ID."""
        manager = ConfigManager(self.config_file)
        
        with self.assertRaises(ConfigurationError):
            manager.get_guild_config(0)
        
        with self.assertRaises(ConfigurationError):
            manager.get_guild_config("invalid")
    
    def test_set_guild_config(self):
        """Test setting guild configuration."""
        manager = ConfigManager(self.config_file)
        
        guild_config = GuildConfig(
            guild_id=123456789,
            staff_roles=[111, 222],
            ticket_category=333
        )
        
        manager.set_guild_config(guild_config)
        
        retrieved_config = manager.get_guild_config(123456789)
        self.assertEqual(retrieved_config.guild_id, 123456789)
        self.assertEqual(retrieved_config.staff_roles, [111, 222])
        self.assertEqual(retrieved_config.ticket_category, 333)
    
    def test_set_guild_config_invalid_type(self):
        """Test setting guild config with invalid type."""
        manager = ConfigManager(self.config_file)
        
        with self.assertRaises(ConfigurationError):
            manager.set_guild_config("not_a_guild_config")
    
    def test_global_config_operations(self):
        """Test global configuration get/set operations."""
        manager = ConfigManager(self.config_file)
        
        # Test getting with default
        self.assertEqual(manager.get_global_config('nonexistent', 'default'), 'default')
        
        # Test setting and getting
        manager.set_global_config('test_key', 'test_value')
        self.assertEqual(manager.get_global_config('test_key'), 'test_value')
    
    def test_save_configuration(self):
        """Test saving configuration to file."""
        manager = ConfigManager(self.config_file)
        
        # Modify configuration
        manager.set_global_config('test_key', 'test_value')
        guild_config = GuildConfig(guild_id=123, staff_roles=[111])
        manager.set_guild_config(guild_config)
        
        # Save configuration
        manager.save_configuration()
        
        # Create new manager and verify data persisted
        new_manager = ConfigManager(self.config_file)
        self.assertEqual(new_manager.get_global_config('test_key'), 'test_value')
        
        retrieved_guild_config = new_manager.get_guild_config(123)
        self.assertEqual(retrieved_guild_config.staff_roles, [111])
    
    def test_validate_configuration_valid(self):
        """Test configuration validation with valid config."""
        config_data = {
            'global': {
                'database_type': 'sqlite',
                'database_url': 'test.db'
            },
            'guilds': {}
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager(self.config_file)
        errors = manager.validate_configuration()
        
        self.assertEqual(errors, [])
    
    def test_validate_configuration_missing_required(self):
        """Test configuration validation with missing required fields."""
        config_data = {
            'global': {},  # Missing required fields
            'guilds': {}
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager(self.config_file)
        errors = manager.validate_configuration()
        
        self.assertIn('Missing required global configuration: database_type', errors)
        self.assertIn('Missing required global configuration: database_url', errors)
    
    def test_validate_configuration_invalid_database_type(self):
        """Test configuration validation with invalid database type."""
        config_data = {
            'global': {
                'database_type': 'invalid_db',
                'database_url': 'test.db'
            },
            'guilds': {}
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager(self.config_file)
        errors = manager.validate_configuration()
        
        self.assertTrue(any('Invalid database_type' in error for error in errors))
    
    def test_reload_configuration(self):
        """Test reloading configuration from file."""
        manager = ConfigManager(self.config_file)
        
        # Modify file externally
        config_data = {
            'global': {
                'database_type': 'mysql',
                'database_url': 'mysql://localhost/test'
            },
            'guilds': {
                '123': {
                    'guild_id': 123,
                    'staff_roles': [999]
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Reload and verify changes
        manager.reload_configuration()
        
        self.assertEqual(manager.get_global_config('database_type'), 'mysql')
        guild_config = manager.get_guild_config(123)
        self.assertEqual(guild_config.staff_roles, [999])


if __name__ == '__main__':
    unittest.main()