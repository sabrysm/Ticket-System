"""
Tests for bot startup and deployment validation.
"""

import asyncio
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from startup_validator import StartupValidator, ValidationError
from bot import TicketBot, validate_environment, shutdown_handler
from config.config_manager import ConfigManager, ConfigurationError


class TestStartupValidator:
    """Test cases for startup validation."""
    
    @pytest.fixture
    def validator(self):
        """Create a StartupValidator instance."""
        return StartupValidator()
    
    def test_validate_environment_variables_success(self, validator):
        """Test successful environment variable validation."""
        with patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test_token_that_is_long_enough_to_pass_validation_check',
            'DATABASE_TYPE': 'sqlite',
            'LOG_LEVEL': 'INFO'
        }):
            result = validator.validate_environment_variables()
            assert result is True
            assert len(validator.errors) == 0
    
    def test_validate_environment_variables_missing_token(self, validator):
        """Test validation failure with missing Discord token."""
        with patch.dict(os.environ, {}, clear=True):
            result = validator.validate_environment_variables()
            assert result is False
            assert any('DISCORD_TOKEN' in error for error in validator.errors)
    
    def test_validate_environment_variables_invalid_db_type(self, validator):
        """Test validation failure with invalid database type."""
        with patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test_token_that_is_long_enough_to_pass_validation_check',
            'DATABASE_TYPE': 'invalid_db'
        }):
            result = validator.validate_environment_variables()
            assert result is False
            assert any('DATABASE_TYPE' in error for error in validator.errors)
    
    def test_validate_file_structure_success(self, validator):
        """Test successful file structure validation."""
        # Mock Path.exists to return True for required files/dirs
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            result = validator.validate_file_structure()
            assert result is True
            assert len(validator.errors) == 0
    
    def test_validate_file_structure_missing_files(self, validator):
        """Test validation failure with missing files."""
        with patch('pathlib.Path.exists', return_value=False):
            result = validator.validate_file_structure()
            assert result is False
            assert len(validator.errors) > 0
    
    def test_validate_configuration_success(self, validator):
        """Test successful configuration validation."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"global": {"database_type": "sqlite", "database_url": "test.db"}, "guilds": {}}')
            config_file = f.name
        
        try:
            with patch.dict(os.environ, {'CONFIG_FILE': config_file}):
                result = validator.validate_configuration()
                assert result is True
                assert len(validator.errors) == 0
        finally:
            os.unlink(config_file)
    
    def test_validate_configuration_invalid_json(self, validator):
        """Test validation failure with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('invalid json content')
            config_file = f.name
        
        try:
            with patch.dict(os.environ, {'CONFIG_FILE': config_file}):
                result = validator.validate_configuration()
                assert result is False
                assert len(validator.errors) > 0
        finally:
            os.unlink(config_file)
    
    @pytest.mark.asyncio
    async def test_validate_database_connection_success(self, validator):
        """Test successful database connection validation."""
        mock_adapter = AsyncMock()
        mock_adapter.connect = AsyncMock()
        mock_adapter.is_connected = AsyncMock(return_value=True)
        mock_adapter.disconnect = AsyncMock()
        
        with patch('startup_validator.SQLiteAdapter', return_value=mock_adapter), \
             patch.dict(os.environ, {'DATABASE_TYPE': 'sqlite', 'DATABASE_URL': 'test.db'}):
            result = await validator.validate_database_connection()
            assert result is True
            assert len(validator.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_database_connection_failure(self, validator):
        """Test database connection validation failure."""
        mock_adapter = AsyncMock()
        mock_adapter.connect = AsyncMock(side_effect=Exception("Connection failed"))
        mock_adapter.disconnect = AsyncMock()
        
        with patch('startup_validator.SQLiteAdapter', return_value=mock_adapter), \
             patch.dict(os.environ, {'DATABASE_TYPE': 'sqlite', 'DATABASE_URL': 'test.db'}):
            result = await validator.validate_database_connection()
            assert result is False
            assert len(validator.errors) > 0
    
    def test_validate_dependencies_success(self, validator):
        """Test successful dependency validation."""
        # Mock successful imports
        with patch('builtins.__import__', return_value=MagicMock()):
            result = validator.validate_dependencies()
            assert result is True
            assert len(validator.errors) == 0
    
    def test_validate_dependencies_missing(self, validator):
        """Test dependency validation with missing modules."""
        def mock_import(name, *args, **kwargs):
            if name in ['discord', 'aiosqlite', 'python_dotenv']:
                raise ImportError(f"No module named '{name}'")
            return MagicMock()
        
        with patch('builtins.__import__', side_effect=mock_import):
            result = validator.validate_dependencies()
            assert result is False
            assert len(validator.errors) > 0
    
    @pytest.mark.asyncio
    async def test_run_full_validation_success(self, validator):
        """Test complete validation suite success."""
        # Mock all validation methods to return True
        validator.validate_environment_variables = MagicMock(return_value=True)
        validator.validate_file_structure = MagicMock(return_value=True)
        validator.validate_configuration = MagicMock(return_value=True)
        validator.validate_database_connection = AsyncMock(return_value=True)
        validator.validate_discord_permissions = MagicMock(return_value=True)
        validator.validate_dependencies = MagicMock(return_value=True)
        
        success, results = await validator.run_full_validation()
        
        assert success is True
        assert results['success'] is True
        assert all(results['validations'].values())
        assert results['error_count'] == 0
    
    @pytest.mark.asyncio
    async def test_run_full_validation_failure(self, validator):
        """Test complete validation suite with failures."""
        # Mock some validation methods to return False
        validator.validate_environment_variables = MagicMock(return_value=False)
        validator.validate_file_structure = MagicMock(return_value=True)
        validator.validate_configuration = MagicMock(return_value=False)
        validator.validate_database_connection = AsyncMock(return_value=True)
        validator.validate_discord_permissions = MagicMock(return_value=True)
        validator.validate_dependencies = MagicMock(return_value=True)
        
        # Add some errors
        validator.add_error("Test error 1")
        validator.add_error("Test error 2")
        
        success, results = await validator.run_full_validation()
        
        assert success is False
        assert results['success'] is False
        assert not all(results['validations'].values())
        assert results['error_count'] == 2


class TestBotStartup:
    """Test cases for bot startup functionality."""
    
    def test_validate_environment_success(self):
        """Test successful environment validation."""
        with patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test_token_that_is_long_enough',
            'DATABASE_TYPE': 'sqlite',
            'LOG_LEVEL': 'INFO'
        }):
            result = validate_environment()
            assert result is True
    
    def test_validate_environment_missing_token(self):
        """Test environment validation with missing token."""
        with patch.dict(os.environ, {}, clear=True):
            result = validate_environment()
            assert result is False
    
    def test_validate_environment_invalid_db_type(self):
        """Test environment validation with invalid database type."""
        with patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test_token_that_is_long_enough',
            'DATABASE_TYPE': 'invalid'
        }):
            result = validate_environment()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_bot_initialization_success(self):
        """Test successful bot initialization."""
        with patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test_token_that_is_long_enough',
            'DATABASE_TYPE': 'sqlite',
            'DATABASE_URL': 'test.db'
        }):
            bot = TicketBot()
            
            # Mock the initialization methods
            bot._initialize_config = AsyncMock()
            bot._initialize_database = AsyncMock()
            bot._initialize_ticket_manager = AsyncMock()
            bot.load_extensions = AsyncMock()
            bot.tree.sync = AsyncMock()
            
            await bot.setup_hook()
            
            assert bot._startup_complete is True
            bot._initialize_config.assert_called_once()
            bot._initialize_database.assert_called_once()
            bot._initialize_ticket_manager.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_bot_initialization_failure(self):
        """Test bot initialization with failure."""
        bot = TicketBot()
        
        # Mock initialization to fail
        bot._initialize_config = AsyncMock(side_effect=Exception("Config failed"))
        bot._cleanup_on_error = AsyncMock()
        
        with pytest.raises(Exception, match="Config failed"):
            await bot.setup_hook()
        
        assert bot._startup_complete is False
        bot._cleanup_on_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown_handler(self):
        """Test graceful shutdown handler."""
        bot = MagicMock()
        bot.close = AsyncMock()
        
        with patch('sys.exit') as mock_exit:
            await shutdown_handler(bot, "SIGTERM")
            
            bot.close.assert_called_once()
            mock_exit.assert_called_once_with(0)
    
    def test_bot_ready_for_operation(self):
        """Test bot ready for operation check."""
        bot = TicketBot()
        
        # Initially not ready
        assert bot.is_ready_for_operation() is False
        
        # Set up as ready
        bot._startup_complete = True
        bot.database_adapter = MagicMock()
        bot.config_manager = MagicMock()
        bot.ticket_manager = MagicMock()
        
        assert bot.is_ready_for_operation() is True
        
        # Test shutdown initiated
        bot._shutdown_initiated = True
        assert bot.is_ready_for_operation() is False
    
    @pytest.mark.asyncio
    async def test_bot_close_cleanup(self):
        """Test bot cleanup during close."""
        bot = TicketBot()
        bot.database_adapter = AsyncMock()
        bot.config_manager = MagicMock()
        bot.config_manager.save_configuration = MagicMock()
        
        # Mock the parent class close method
        with patch('discord.ext.commands.Bot.close', new_callable=AsyncMock) as mock_super_close:
            await bot.close()
            
            assert bot._shutdown_initiated is True
            bot.database_adapter.disconnect.assert_called_once()
            bot.config_manager.save_configuration.assert_called_once()
            mock_super_close.assert_called_once()


class TestDeploymentValidation:
    """Test cases for deployment validation."""
    
    @pytest.mark.asyncio
    async def test_deployment_readiness_check(self):
        """Test complete deployment readiness validation."""
        validator = StartupValidator()
        
        # Mock all validations to pass
        with patch.object(validator, 'validate_environment_variables', return_value=True), \
             patch.object(validator, 'validate_file_structure', return_value=True), \
             patch.object(validator, 'validate_configuration', return_value=True), \
             patch.object(validator, 'validate_database_connection', return_value=True), \
             patch.object(validator, 'validate_discord_permissions', return_value=True), \
             patch.object(validator, 'validate_dependencies', return_value=True):
            
            success, results = await validator.run_full_validation()
            
            assert success is True
            assert results['success'] is True
            assert results['error_count'] == 0
    
    def test_production_environment_variables(self):
        """Test validation of production environment variables."""
        production_vars = {
            'DISCORD_TOKEN': 'production_token_that_is_long_enough_for_validation',
            'DATABASE_TYPE': 'sqlite',
            'DATABASE_URL': '/app/data/tickets.db',
            'LOG_LEVEL': 'WARNING',
            'COMMAND_PREFIX': '!'
        }
        
        validator = StartupValidator()
        
        with patch.dict(os.environ, production_vars):
            result = validator.validate_environment_variables()
            assert result is True
            assert len(validator.errors) == 0
    
    def test_docker_deployment_validation(self):
        """Test validation for Docker deployment scenario."""
        docker_vars = {
            'DISCORD_TOKEN': 'docker_token_that_is_long_enough_for_validation_and_meets_minimum_length_requirements',
            'DATABASE_TYPE': 'sqlite',
            'DATABASE_URL': '/app/data/tickets.db',
            'LOG_LEVEL': 'INFO',
            'CONFIG_FILE': '/app/config/config.json'
        }
        
        validator = StartupValidator()
        
        with patch.dict(os.environ, docker_vars):
            result = validator.validate_environment_variables()
            assert result is True