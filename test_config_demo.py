#!/usr/bin/env python3
"""
Demo script to test the configuration management system.
"""

import os
import sys

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager, GuildConfig, ConfigurationError


def main():
    """Demonstrate configuration management functionality."""
    print("=== Configuration Management System Demo ===\n")
    
    # Create a config manager with a test file
    config_file = "demo_config.json"
    
    try:
        # Initialize config manager
        print("1. Initializing ConfigManager...")
        manager = ConfigManager(config_file)
        print(f"   ✓ Config file created: {config_file}")
        
        # Test global configuration
        print("\n2. Testing global configuration...")
        print(f"   Database type: {manager.get_global_config('database_type')}")
        print(f"   Database URL: {manager.get_global_config('database_url')}")
        
        manager.set_global_config('bot_token', 'demo_token_123')
        print(f"   Set bot_token: {manager.get_global_config('bot_token')}")
        
        # Test guild configuration
        print("\n3. Testing guild configuration...")
        guild_id = 123456789
        
        # Get default guild config (should create one)
        guild_config = manager.get_guild_config(guild_id)
        print(f"   Default guild config for {guild_id}: {guild_config.to_dict()}")
        
        # Create and set a custom guild config
        custom_config = GuildConfig(
            guild_id=guild_id,
            staff_roles=[111111, 222222, 333333],
            ticket_category=444444,
            log_channel=555555,
            embed_settings={
                'title': 'Demo Support',
                'color': 0x00ff00,
                'button_text': 'Get Help'
            }
        )
        
        manager.set_guild_config(custom_config)
        print(f"   ✓ Set custom guild config")
        
        # Retrieve and verify
        retrieved_config = manager.get_guild_config(guild_id)
        print(f"   Retrieved config: {retrieved_config.to_dict()}")
        
        # Test validation
        print("\n4. Testing configuration validation...")
        errors = manager.validate_configuration()
        if errors:
            print(f"   Validation errors: {errors}")
        else:
            print("   ✓ Configuration is valid")
        
        # Save configuration
        print("\n5. Saving configuration...")
        manager.save_configuration()
        print("   ✓ Configuration saved successfully")
        
        # Test reload
        print("\n6. Testing configuration reload...")
        manager.reload_configuration()
        reloaded_config = manager.get_guild_config(guild_id)
        print(f"   Reloaded guild config: {reloaded_config.to_dict()}")
        
        print("\n=== Demo completed successfully! ===")
        
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        # Clean up demo file
        if os.path.exists(config_file):
            os.remove(config_file)
            print(f"\nCleaned up demo file: {config_file}")


if __name__ == "__main__":
    main()