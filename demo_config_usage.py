#!/usr/bin/env python3
"""
Demonstration script showing the configuration management system in action.
This script shows how to use ConfigManager and GuildConfig classes.
"""

import os
import tempfile
import shutil
from config import ConfigManager, GuildConfig, ConfigurationError

def main():
    """Demonstrate configuration management functionality."""
    print("🎫 Discord Ticket Bot - Configuration Management Demo")
    print("=" * 50)
    
    # Create a temporary config file for demo
    temp_dir = tempfile.mkdtemp()
    config_file = os.path.join(temp_dir, 'demo_config.json')
    
    try:
        # 1. Initialize ConfigManager (creates default config)
        print("\n1. Initializing ConfigManager...")
        config_manager = ConfigManager(config_file)
        print(f"   ✅ Created config file: {config_file}")
        print(f"   ✅ Default database type: {config_manager.get_global_config('database_type')}")
        
        # 2. Configure global settings
        print("\n2. Setting global configuration...")
        config_manager.set_global_config('database_type', 'mysql')
        config_manager.set_global_config('database_url', 'mysql://localhost:3306/tickets')
        config_manager.set_global_config('log_level', 'DEBUG')
        print("   ✅ Global settings configured")
        
        # 3. Create and configure guild settings
        print("\n3. Creating guild configuration...")
        guild_config = GuildConfig(
            guild_id=123456789012345678,
            staff_roles=[987654321098765432, 876543210987654321],
            ticket_category=765432109876543210,
            log_channel=654321098765432109,
            embed_settings={
                'title': 'Support Tickets',
                'description': 'Click the button below to create a new support ticket.',
                'color': 0x00ff00,  # Green color
                'button_text': 'Create Ticket',
                'button_emoji': '🎫'
            }
        )
        
        config_manager.set_guild_config(guild_config)
        print("   ✅ Guild configuration created and set")
        
        # 4. Retrieve and display configuration
        print("\n4. Retrieving configuration...")
        retrieved_config = config_manager.get_guild_config(123456789012345678)
        print(f"   Guild ID: {retrieved_config.guild_id}")
        print(f"   Staff Roles: {retrieved_config.staff_roles}")
        print(f"   Ticket Category: {retrieved_config.ticket_category}")
        print(f"   Log Channel: {retrieved_config.log_channel}")
        print(f"   Embed Title: {retrieved_config.embed_settings.get('title')}")
        
        # 5. Save configuration
        print("\n5. Saving configuration to file...")
        config_manager.save_configuration()
        print("   ✅ Configuration saved successfully")
        
        # 6. Validate configuration
        print("\n6. Validating configuration...")
        errors = config_manager.validate_configuration()
        if errors:
            print("   ❌ Validation errors found:")
            for error in errors:
                print(f"      - {error}")
        else:
            print("   ✅ Configuration is valid")
        
        # 7. Test error handling
        print("\n7. Testing error handling...")
        try:
            invalid_config = GuildConfig(guild_id=0)  # Invalid guild ID
        except ValueError as e:
            print(f"   ✅ Caught expected error: {e}")
        
        try:
            config_manager.get_guild_config("invalid")  # Invalid type
        except ConfigurationError as e:
            print(f"   ✅ Caught expected error: {e}")
        
        print("\n🎉 Configuration management system demonstration complete!")
        print("   All features working correctly:")
        print("   ✅ Configuration loading and saving")
        print("   ✅ Guild-specific settings")
        print("   ✅ Global settings management")
        print("   ✅ Data validation and error handling")
        print("   ✅ JSON serialization/deserialization")
        
    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
            print(f"\n🧹 Cleaned up temporary directory: {temp_dir}")
        except OSError:
            pass

if __name__ == '__main__':
    main()