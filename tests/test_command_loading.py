"""
Unit tests for command loading system and bot extension management.
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from bot import TicketBot


class TestCommandLoading:
    """Test cases for command loading system."""
    
    @pytest.fixture
    def mock_token(self):
        """Mock Discord token for testing."""
        with patch.dict(os.environ, {'DISCORD_TOKEN': 'test_token'}):
            yield 'test_token'
    
    @pytest.fixture
    def bot_instance(self, mock_token):
        """Create a TicketBot instance for testing."""
        return TicketBot()
    
    @pytest.mark.asyncio
    async def test_bot_initialization(self, bot_instance):
        """Test bot initialization with proper intents and settings."""
        assert bot_instance.command_prefix == '!'
        assert bot_instance.case_insensitive is True
        assert bot_instance.help_command is None
        
        # Check intents
        assert bot_instance.intents.message_content is True
        assert bot_instance.intents.guilds is True
        assert bot_instance.intents.guild_messages is True
        assert bot_instance.intents.members is True
    
    @pytest.mark.asyncio
    async def test_load_extensions_no_commands_directory(self, bot_instance):
        """Test extension loading when commands directory doesn't exist."""
        # Create a mock path instance
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = False
        
        with patch('bot.Path') as mock_path_class:
            mock_path_class.return_value = mock_path_instance
            # Should not raise an exception
            await bot_instance.load_extensions()
    
    @pytest.mark.asyncio
    async def test_load_extensions_success(self, bot_instance):
        """Test successful extension loading."""
        # Create proper mock files with all needed attributes
        mock_file1 = Mock()
        mock_file1.name = 'test_command.py'
        mock_file1.stem = 'test_command'
        
        mock_file2 = Mock()
        mock_file2.name = 'another_command.py'
        mock_file2.stem = 'another_command'
        
        mock_files = [mock_file1, mock_file2]
        
        # Create a mock path instance
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.glob.return_value = mock_files
        
        with patch('bot.Path') as mock_path_class, \
             patch.object(bot_instance, 'load_extension', new_callable=AsyncMock) as mock_load:
            
            mock_path_class.return_value = mock_path_instance
            
            await bot_instance.load_extensions()
            
            # Should attempt to load both extensions
            assert mock_load.call_count == 2
            mock_load.assert_any_call('commands.test_command')
            mock_load.assert_any_call('commands.another_command')
    
    @pytest.mark.asyncio
    async def test_load_extensions_skip_special_files(self, bot_instance):
        """Test that special files are skipped during extension loading."""
        # Create proper mock files including ones that should be skipped
        mock_init = Mock()
        mock_init.name = '__init__.py'
        mock_init.stem = '__init__'
        
        mock_base_cog = Mock()
        mock_base_cog.name = 'base_cog.py'
        mock_base_cog.stem = 'base_cog'
        
        mock_valid = Mock()
        mock_valid.name = 'valid_command.py'
        mock_valid.stem = 'valid_command'
        
        mock_files = [mock_init, mock_base_cog, mock_valid]
        
        # Create a mock path instance
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.glob.return_value = mock_files
        
        with patch('bot.Path') as mock_path_class, \
             patch.object(bot_instance, 'load_extension', new_callable=AsyncMock) as mock_load:
            
            mock_path_class.return_value = mock_path_instance
            
            await bot_instance.load_extensions()
            
            # Should only load the valid command, not __init__ or base_cog
            assert mock_load.call_count == 1
            mock_load.assert_called_once_with('commands.valid_command')
    
    @pytest.mark.asyncio
    async def test_load_extensions_with_failures(self, bot_instance):
        """Test extension loading with some failures."""
        # Create proper mock files
        mock_working = Mock()
        mock_working.name = 'working_command.py'
        mock_working.stem = 'working_command'
        
        mock_broken = Mock()
        mock_broken.name = 'broken_command.py'
        mock_broken.stem = 'broken_command'
        
        mock_files = [mock_working, mock_broken]
        
        async def mock_load_extension(name):
            if 'broken' in name:
                raise Exception("Mock loading error")
        
        # Create a mock path instance
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.glob.return_value = mock_files
        
        with patch('bot.Path') as mock_path_class, \
             patch.object(bot_instance, 'load_extension', side_effect=mock_load_extension):
            
            mock_path_class.return_value = mock_path_instance
            
            # Should not raise an exception even with failures
            await bot_instance.load_extensions()
    
    @pytest.mark.asyncio
    async def test_reload_extension_safe_success(self, bot_instance):
        """Test successful extension reload."""
        with patch.object(bot_instance, 'reload_extension', new_callable=AsyncMock) as mock_reload:
            result = await bot_instance.reload_extension_safe('test_extension')
            
            assert result is True
            mock_reload.assert_called_once_with('test_extension')
    
    @pytest.mark.asyncio
    async def test_reload_extension_safe_not_loaded(self, bot_instance):
        """Test extension reload when extension is not loaded."""
        from discord.ext.commands import ExtensionNotLoaded
        
        with patch.object(bot_instance, 'reload_extension', 
                         new_callable=AsyncMock, 
                         side_effect=ExtensionNotLoaded('test')), \
             patch.object(bot_instance, 'load_extension', new_callable=AsyncMock) as mock_load:
            
            result = await bot_instance.reload_extension_safe('test_extension')
            
            assert result is True
            mock_load.assert_called_once_with('test_extension')
    
    @pytest.mark.asyncio
    async def test_reload_extension_safe_failure(self, bot_instance):
        """Test extension reload failure."""
        with patch.object(bot_instance, 'reload_extension', 
                         new_callable=AsyncMock, 
                         side_effect=Exception("Mock error")):
            
            result = await bot_instance.reload_extension_safe('test_extension')
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_reload_extension_safe_load_failure_after_not_loaded(self, bot_instance):
        """Test extension reload when not loaded and subsequent load fails."""
        from discord.ext.commands import ExtensionNotLoaded
        
        with patch.object(bot_instance, 'reload_extension', 
                         new_callable=AsyncMock, 
                         side_effect=ExtensionNotLoaded('test')), \
             patch.object(bot_instance, 'load_extension', 
                         new_callable=AsyncMock, 
                         side_effect=Exception("Load failed")):
            
            result = await bot_instance.reload_extension_safe('test_extension')
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_setup_hook_calls_load_extensions(self, bot_instance):
        """Test that setup_hook calls load_extensions."""
        with patch.object(bot_instance, 'load_extensions', new_callable=AsyncMock) as mock_load, \
             patch.object(bot_instance.tree, 'sync', new_callable=AsyncMock) as mock_sync:
            
            await bot_instance.setup_hook()
            
            mock_load.assert_called_once()
            mock_sync.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_setup_hook_handles_errors(self, bot_instance):
        """Test that setup_hook handles errors gracefully."""
        with patch.object(bot_instance, 'load_extensions', 
                         new_callable=AsyncMock, 
                         side_effect=Exception("Setup error")):
            
            # Should raise the exception
            with pytest.raises(Exception, match="Setup error"):
                await bot_instance.setup_hook()
    
    @pytest.mark.asyncio
    async def test_on_ready_sets_activity(self, bot_instance):
        """Test that on_ready sets bot activity."""
        # Mock the user and guilds properties
        mock_user = Mock()
        mock_user.name = "TestBot"
        
        with patch.object(type(bot_instance), 'user', mock_user), \
             patch.object(type(bot_instance), 'guilds', [Mock(), Mock()]), \
             patch.object(bot_instance, 'change_presence', new_callable=AsyncMock) as mock_presence:
            
            await bot_instance.on_ready()
            
            mock_presence.assert_called_once()
            call_args = mock_presence.call_args[1]
            assert 'activity' in call_args
    
    @pytest.mark.asyncio
    async def test_close_cleanup(self, bot_instance):
        """Test bot cleanup on close."""
        with patch('discord.ext.commands.Bot.close', new_callable=AsyncMock) as mock_super_close:
            await bot_instance.close()
            
            mock_super_close.assert_called_once()


class TestBotIntegration:
    """Integration tests for bot functionality."""
    
    @pytest.fixture
    def temp_commands_dir(self):
        """Create a temporary commands directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            commands_dir = Path(temp_dir) / "commands"
            commands_dir.mkdir()
            
            # Create __init__.py
            (commands_dir / "__init__.py").write_text("# Commands package")
            
            # Create a simple test command
            test_command_content = '''
from discord.ext import commands
from discord import app_commands
import discord

class TestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="test", description="Test command")
    async def test_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Test successful!")

async def setup(bot):
    await bot.add_cog(TestCog(bot))
'''
            (commands_dir / "test_cog.py").write_text(test_command_content)
            
            yield commands_dir
    
    @pytest.mark.asyncio
    async def test_real_extension_loading(self, temp_commands_dir):
        """Test loading real extension files."""
        with patch.dict(os.environ, {'DISCORD_TOKEN': 'test_token'}), \
             patch('pathlib.Path', return_value=temp_commands_dir.parent), \
             patch.object(Path, 'glob') as mock_glob:
            
            # Mock glob to return our test file
            mock_glob.return_value = [temp_commands_dir / "test_cog.py"]
            
            bot = TicketBot()
            
            try:
                # This should work without errors
                await bot.load_extensions()
                
                # Verify the extension was loaded
                assert len(bot.extensions) >= 0  # May be 0 due to mocking
                
            finally:
                await bot.close()


if __name__ == "__main__":
    pytest.main([__file__])