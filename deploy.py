#!/usr/bin/env python3
"""
Deployment script for Discord Ticket Bot.

This script handles deployment preparation, validation, and startup
for production environments.
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any

from startup_validator import StartupValidator
from bot import main as bot_main


def create_deployment_config():
    """Create deployment configuration files if they don't exist."""
    print("Creating deployment configuration files...")
    
    # Create config.json if it doesn't exist
    config_file = Path("config.json")
    if not config_file.exists():
        default_config = {
            "global": {
                "database_type": "sqlite",
                "database_url": "tickets.db",
                "log_level": "INFO"
            },
            "guilds": {}
        }
        
        import json
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        print(f"✅ Created default configuration: {config_file}")
    else:
        print(f"✅ Configuration file already exists: {config_file}")
    
    # Create .env file if it doesn't exist
    env_file = Path(".env")
    if not env_file.exists():
        env_template = """# Discord Bot Configuration
DISCORD_TOKEN=your_bot_token_here

# Database Configuration
DATABASE_TYPE=sqlite
DATABASE_URL=tickets.db

# Bot Configuration
LOG_LEVEL=INFO
COMMAND_PREFIX=!
"""
        with open(env_file, 'w') as f:
            f.write(env_template)
        
        print(f"✅ Created environment template: {env_file}")
        print("⚠️  Please edit .env file with your actual configuration values")
    else:
        print(f"✅ Environment file already exists: {env_file}")
    
    # Create logs directory
    logs_dir = Path("logs")
    if not logs_dir.exists():
        logs_dir.mkdir()
        print(f"✅ Created logs directory: {logs_dir}")
    else:
        print(f"✅ Logs directory already exists: {logs_dir}")


def check_production_readiness() -> Dict[str, Any]:
    """Check if the bot is ready for production deployment."""
    print("Checking production readiness...")
    
    issues = []
    warnings = []
    
    # Check for development/debug settings
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    if log_level == 'DEBUG':
        warnings.append("LOG_LEVEL is set to DEBUG - consider using INFO or WARNING for production")
    
    # Check database configuration
    db_type = os.getenv('DATABASE_TYPE', 'sqlite')
    db_url = os.getenv('DATABASE_URL', 'tickets.db')
    
    if db_type == 'sqlite' and not db_url.startswith('/'):
        warnings.append("SQLite database path is relative - consider using absolute path for production")
    
    # Check Discord token
    token = os.getenv('DISCORD_TOKEN', '')
    if token == 'your_bot_token_here' or not token:
        issues.append("DISCORD_TOKEN is not set or using placeholder value")
    
    # Check file permissions (Unix systems)
    if hasattr(os, 'getuid'):  # Unix systems
        config_file = Path("config.json")
        if config_file.exists():
            stat = config_file.stat()
            if stat.st_mode & 0o077:  # Check if group/other have any permissions
                warnings.append("config.json has overly permissive file permissions")
    
    return {
        'issues': issues,
        'warnings': warnings,
        'ready': len(issues) == 0
    }


async def run_deployment_validation(skip_validation: bool = False) -> bool:
    """Run complete deployment validation."""
    if skip_validation:
        print("⚠️  Skipping validation as requested")
        return True
    
    print("Running deployment validation...")
    print("-" * 50)
    
    validator = StartupValidator()
    success, results = await validator.run_full_validation()
    
    validator.print_validation_report(results)
    
    if not success:
        print("\n❌ Deployment validation failed!")
        print("Please fix the issues above before deploying.")
        return False
    
    # Additional production readiness check
    prod_check = check_production_readiness()
    
    if prod_check['issues']:
        print("\n❌ Production readiness issues found:")
        for issue in prod_check['issues']:
            print(f"  - {issue}")
        return False
    
    if prod_check['warnings']:
        print("\n⚠️  Production warnings:")
        for warning in prod_check['warnings']:
            print(f"  - {warning}")
        
        if not os.getenv('IGNORE_WARNINGS'):
            response = input("\nContinue despite warnings? (y/N): ")
            if response.lower() != 'y':
                return False
    
    print("\n✅ Deployment validation passed!")
    return True


async def deploy_bot(args):
    """Deploy the bot with validation."""
    print("Discord Ticket Bot - Deployment Script")
    print("=" * 50)
    
    # Create deployment files if needed
    if args.init:
        create_deployment_config()
        print("\nDeployment files created. Please configure your settings and run again.")
        return
    
    # Run validation
    if not await run_deployment_validation(args.skip_validation):
        sys.exit(1)
    
    # Start the bot
    if not args.validate_only:
        print("\n🚀 Starting Discord Ticket Bot...")
        print("-" * 50)
        
        try:
            await bot_main()
        except KeyboardInterrupt:
            print("\n👋 Bot stopped by user")
        except Exception as e:
            print(f"\n❌ Bot failed to start: {e}")
            sys.exit(1)


def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(
        description="Deploy Discord Ticket Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy.py --init                    # Initialize deployment files
  python deploy.py --validate-only          # Run validation only
  python deploy.py --skip-validation        # Skip validation and start bot
  python deploy.py                          # Full deployment with validation
        """
    )
    
    parser.add_argument(
        '--init',
        action='store_true',
        help='Initialize deployment configuration files'
    )
    
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Run validation only, do not start the bot'
    )
    
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip validation and start the bot directly'
    )
    
    parser.add_argument(
        '--ignore-warnings',
        action='store_true',
        help='Ignore production warnings and continue deployment'
    )
    
    args = parser.parse_args()
    
    # Set environment variable for ignore warnings
    if args.ignore_warnings:
        os.environ['IGNORE_WARNINGS'] = '1'
    
    try:
        asyncio.run(deploy_bot(args))
    except KeyboardInterrupt:
        print("\n👋 Deployment interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()