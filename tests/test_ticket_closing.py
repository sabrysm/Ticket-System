"""
Unit tests for ticket closing and archiving functionality.
"""

import pytest
import asyncio
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import discord
from discord.ext import commands

from core.ticket_manager import (
    TicketManager, TicketClosingError, TranscriptError, 
    PermissionError, TicketNotFoundError
)
from models.ticket import Ticket, TicketStatus
from database.adapter import DatabaseAdapter
from config.config_manager import ConfigManager, GuildConfig


class MockDatabaseAdapter(DatabaseAdapter):
    """Mock database adapter for testing."""
    
    def __init__(self):
        super().__init__("mock://test")
        self.tickets = {}
        self.connected = True
    
    async def connect(self):
        self.connected = True
    
    async def disconnect(self):
        self.connected = False
    
    async def is_connected(self):
        return self.connected
    
    async def create_ticket(self, ticket):
        self.tickets[ticket.ticket_id] = ticket
        return ticket.ticket_id
    
    async def get_ticket(self, ticket_id):
        return self.tickets.get(ticket_id)
    
    async def get_tickets_by_user(self, user_id, guild_id):
        return [t for t in self.tickets.values() 
                if t.creator_id == user_id and t.guild_id == guild_id]
    
    async def get_tickets_by_guild(self, guild_id, status=None):
        tickets = [t for t in self.tickets.values() if t.guild_id == guild_id]
        if status:
            tickets = [t for t in tickets if t.status.value == status]
        return tickets
    
    async def update_ticket(self, ticket_id, updates):
        if ticket_id not in self.tickets:
            return False
        
        ticket = self.tickets[ticket_id]
        for key, value in updates.items():
            if hasattr(ticket, key):
                setattr(ticket, key, value)
        return True
    
    async def close_ticket(self, ticket_id, transcript_url=None):
        if ticket_id not in self.tickets:
            return False
        
        ticket = self.tickets[ticket_id]
        ticket.status = TicketStatus.CLOSED
        ticket.closed_at = datetime.utcnow()
        if transcript_url:
            ticket.transcript_url = transcript_url
        return True
    
    async def delete_ticket(self, ticket_id):
        if ticket_id in self.tickets:
            del self.tickets[ticket_id]
            return True
        return False
    
    async def add_participant(self, ticket_id, user_id):
        if ticket_id not in self.tickets:
            return False
        
        ticket = self.tickets[ticket_id]
        if user_id not in ticket.participants:
            ticket.participants.append(user_id)
        return True
    
    async def remove_participant(self, ticket_id, user_id):
        if ticket_id not in self.tickets:
            return False
        
        ticket = self.tickets[ticket_id]
        if user_id in ticket.participants:
            ticket.participants.remove(user_id)
        return True
    
    async def get_active_ticket_for_user(self, user_id, guild_id):
        for ticket in self.tickets.values():
            if (ticket.creator_id == user_id and 
                ticket.guild_id == guild_id and 
                ticket.status == TicketStatus.OPEN):
                return ticket
        return None


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = AsyncMock(spec=commands.Bot)
    bot.get_guild.return_value = MagicMock(spec=discord.Guild)
    bot.get_channel.return_value = MagicMock(spec=discord.TextChannel)
    return bot


@pytest.fixture
def mock_database():
    """Create a mock database adapter."""
    return MockDatabaseAdapter()


@pytest.fixture
def mock_config():
    """Create a mock configuration manager."""
    config = MagicMock(spec=ConfigManager)
    guild_config = GuildConfig(
        guild_id=12345,
        staff_roles=[67890],
        ticket_category=11111,
        archive_category=22222
    )
    config.get_guild_config.return_value = guild_config
    return config


@pytest.fixture
def ticket_manager(mock_bot, mock_database, mock_config):
    """Create a TicketManager instance for testing."""
    return TicketManager(mock_bot, mock_database, mock_config)


@pytest.fixture
def sample_ticket():
    """Create a sample ticket for testing."""
    return Ticket(
        ticket_id="TEST1234",
        guild_id=12345,
        channel_id=98765,
        creator_id=54321,
        status=TicketStatus.OPEN,
        created_at=datetime.utcnow(),
        participants=[54321]
    )


@pytest.fixture
def mock_channel():
    """Create a mock Discord channel."""
    channel = AsyncMock(spec=discord.TextChannel)
    channel.id = 98765
    channel.name = "ticket-test1234"
    channel.guild.id = 12345
    channel.guild.get_member.return_value = MagicMock(spec=discord.Member)
    channel.guild.get_channel.return_value = MagicMock(spec=discord.CategoryChannel)
    channel.guild.name = "Test Guild"
    
    # Mock message history
    mock_message = MagicMock(spec=discord.Message)
    mock_message.created_at = datetime.utcnow()
    mock_message.author.display_name = "TestUser"
    mock_message.author.id = 54321
    mock_message.content = "Test message content"
    mock_message.embeds = []
    mock_message.attachments = []
    
    async def mock_history(*args, **kwargs):
        yield mock_message
    
    channel.history.return_value = mock_history()
    return channel


@pytest.fixture
def mock_staff():
    """Create a mock staff member."""
    staff = MagicMock(spec=discord.Member)
    staff.id = 99999
    staff.mention = "<@99999>"
    staff.display_name = "StaffMember"
    staff.roles = [MagicMock(id=67890)]  # Staff role
    staff.guild.id = 12345
    return staff


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


class TestTranscriptGeneration:
    """Test transcript generation functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_transcript_success(self, ticket_manager, mock_channel):
        """Test successful transcript generation."""
        transcript = await ticket_manager._generate_transcript(mock_channel)
        
        assert "Ticket Transcript - ticket-test1234" in transcript
        assert "Generated:" in transcript
        assert "TestUser (54321): Test message content" in transcript
        assert "End of Transcript" in transcript
    
    @pytest.mark.asyncio
    async def test_generate_transcript_forbidden(self, ticket_manager, mock_channel):
        """Test transcript generation with permission error."""
        mock_channel.history.side_effect = discord.Forbidden(MagicMock(), "Forbidden")
        
        with pytest.raises(TranscriptError, match="Bot lacks permission"):
            await ticket_manager._generate_transcript(mock_channel)
    
    @pytest.mark.asyncio
    async def test_generate_transcript_http_error(self, ticket_manager, mock_channel):
        """Test transcript generation with HTTP error."""
        mock_channel.history.side_effect = discord.HTTPException(MagicMock(), "HTTP Error")
        
        with pytest.raises(TranscriptError, match="Discord API error"):
            await ticket_manager._generate_transcript(mock_channel)
    
    @pytest.mark.asyncio
    async def test_generate_transcript_with_embeds(self, ticket_manager, mock_channel):
        """Test transcript generation with embed messages."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.created_at = datetime.utcnow()
        mock_message.author.display_name = "TestUser"
        mock_message.author.id = 54321
        mock_message.content = ""
        
        mock_embed = MagicMock(spec=discord.Embed)
        mock_embed.title = "Test Embed"
        mock_embed.description = "Test Description"
        mock_message.embeds = [mock_embed]
        mock_message.attachments = []
        
        async def mock_history(*args, **kwargs):
            yield mock_message
        
        mock_channel.history.return_value = mock_history()
        
        transcript = await ticket_manager._generate_transcript(mock_channel)
        assert "[Embed Message] Title: Test Embed Description: Test Description" in transcript
    
    @pytest.mark.asyncio
    async def test_generate_transcript_with_attachments(self, ticket_manager, mock_channel):
        """Test transcript generation with attachment messages."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.created_at = datetime.utcnow()
        mock_message.author.display_name = "TestUser"
        mock_message.author.id = 54321
        mock_message.content = ""
        mock_message.embeds = []
        
        mock_attachment = MagicMock(spec=discord.Attachment)
        mock_attachment.filename = "test.png"
        mock_message.attachments = [mock_attachment]
        
        async def mock_history(*args, **kwargs):
            yield mock_message
        
        mock_channel.history.return_value = mock_history()
        
        transcript = await ticket_manager._generate_transcript(mock_channel)
        assert "[1 Attachment(s)] test.png" in transcript


class TestTranscriptSaving:
    """Test transcript saving functionality."""
    
    @pytest.mark.asyncio
    async def test_save_transcript_success(self, ticket_manager, temp_dir):
        """Test successful transcript saving."""
        transcript_content = "Test transcript content"
        ticket_id = "TEST1234"
        guild_id = 12345
        
        with patch('core.ticket_manager.Path') as mock_path:
            mock_path.return_value = temp_dir
            mock_path.side_effect = lambda x: temp_dir / x if isinstance(x, str) else Path(x)
            
            with patch('builtins.open', mock_open()) as mock_file:
                result = await ticket_manager._save_transcript(
                    transcript_content, ticket_id, guild_id
                )
                
                assert result is not None
                assert f"ticket_{ticket_id}" in result
                mock_file.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_transcript_os_error(self, ticket_manager):
        """Test transcript saving with OS error."""
        transcript_content = "Test transcript content"
        ticket_id = "TEST1234"
        guild_id = 12345
        
        with patch('builtins.open', side_effect=OSError("Permission denied")):
            with pytest.raises(TranscriptError, match="Failed to save transcript"):
                await ticket_manager._save_transcript(
                    transcript_content, ticket_id, guild_id
                )


class TestChannelArchiving:
    """Test channel archiving functionality."""
    
    @pytest.mark.asyncio
    async def test_archive_channel_to_category(self, ticket_manager, mock_channel):
        """Test archiving channel to archive category."""
        ticket_id = "TEST1234"
        
        await ticket_manager._archive_channel(mock_channel, ticket_id)
        
        mock_channel.edit.assert_called_once()
        call_args = mock_channel.edit.call_args
        assert call_args[1]['name'].startswith('closed-')
        assert call_args[1]['reason'] == f"Archived ticket {ticket_id}"
    
    @pytest.mark.asyncio
    async def test_archive_channel_delete_fallback(self, ticket_manager, mock_channel, mock_config):
        """Test channel deletion when no archive category."""
        # Remove archive category
        guild_config = mock_config.get_guild_config.return_value
        guild_config.archive_category = None
        
        ticket_id = "TEST1234"
        
        with patch('asyncio.sleep'):  # Skip the delay
            await ticket_manager._archive_channel(mock_channel, ticket_id)
        
        mock_channel.delete.assert_called_once_with(reason=f"Closed ticket {ticket_id}")
    
    @pytest.mark.asyncio
    async def test_archive_channel_forbidden(self, ticket_manager, mock_channel):
        """Test channel archiving with permission error."""
        mock_channel.edit.side_effect = discord.Forbidden(MagicMock(), "Forbidden")
        
        with pytest.raises(TicketClosingError, match="Bot lacks permission"):
            await ticket_manager._archive_channel(mock_channel, "TEST1234")
    
    @pytest.mark.asyncio
    async def test_archive_channel_http_error(self, ticket_manager, mock_channel):
        """Test channel archiving with HTTP error."""
        mock_channel.edit.side_effect = discord.HTTPException(MagicMock(), "HTTP Error")
        
        with pytest.raises(TicketClosingError, match="Discord API error"):
            await ticket_manager._archive_channel(mock_channel, "TEST1234")


class TestTicketClosing:
    """Test ticket closing functionality."""
    
    @pytest.mark.asyncio
    async def test_close_ticket_success(self, ticket_manager, mock_channel, mock_staff, 
                                       sample_ticket, mock_database):
        """Test successful ticket closing."""
        # Add ticket to mock database
        await mock_database.create_ticket(sample_ticket)
        
        with patch.object(ticket_manager, 'get_ticket_by_channel', return_value=sample_ticket):
            with patch.object(ticket_manager, '_generate_transcript', return_value="transcript"):
                with patch.object(ticket_manager, '_save_transcript', return_value="/path/to/transcript"):
                    with patch.object(ticket_manager, '_archive_channel'):
                        with patch('asyncio.sleep'):  # Skip delays
                            result = await ticket_manager.close_ticket(mock_channel, mock_staff)
        
        assert result is True
        
        # Verify ticket was closed in database
        closed_ticket = await mock_database.get_ticket(sample_ticket.ticket_id)
        assert closed_ticket.status == TicketStatus.CLOSED
        assert closed_ticket.closed_at is not None
        assert closed_ticket.transcript_url == "/path/to/transcript"
    
    @pytest.mark.asyncio
    async def test_close_ticket_not_found(self, ticket_manager, mock_channel, mock_staff):
        """Test closing non-existent ticket."""
        with pytest.raises(TicketNotFoundError):
            await ticket_manager.close_ticket(mock_channel, mock_staff)
    
    @pytest.mark.asyncio
    async def test_close_ticket_already_closed(self, ticket_manager, mock_channel, mock_staff,
                                              sample_ticket, mock_database):
        """Test closing already closed ticket."""
        sample_ticket.status = TicketStatus.CLOSED
        await mock_database.create_ticket(sample_ticket)
        
        with patch.object(ticket_manager, 'get_ticket_by_channel', return_value=sample_ticket):
            with pytest.raises(TicketClosingError, match="already closed"):
                await ticket_manager.close_ticket(mock_channel, mock_staff)
    
    @pytest.mark.asyncio
    async def test_close_ticket_insufficient_permissions(self, ticket_manager, mock_channel,
                                                        sample_ticket, mock_database):
        """Test closing ticket without staff permissions."""
        await mock_database.create_ticket(sample_ticket)
        
        # Create non-staff user
        non_staff = MagicMock(spec=discord.Member)
        non_staff.id = 88888
        non_staff.roles = [MagicMock(id=99999)]  # Not a staff role
        
        with patch.object(ticket_manager, 'get_ticket_by_channel', return_value=sample_ticket):
            with pytest.raises(PermissionError, match="not authorized"):
                await ticket_manager.close_ticket(mock_channel, non_staff)
    
    @pytest.mark.asyncio
    async def test_close_ticket_transcript_failure(self, ticket_manager, mock_channel, mock_staff,
                                                  sample_ticket, mock_database):
        """Test ticket closing when transcript generation fails."""
        await mock_database.create_ticket(sample_ticket)
        
        with patch.object(ticket_manager, 'get_ticket_by_channel', return_value=sample_ticket):
            with patch.object(ticket_manager, '_generate_transcript', 
                             side_effect=TranscriptError("Transcript failed")):
                with patch.object(ticket_manager, '_archive_channel'):
                    with patch('asyncio.sleep'):
                        result = await ticket_manager.close_ticket(mock_channel, mock_staff)
        
        assert result is True
        
        # Verify ticket was still closed despite transcript failure
        closed_ticket = await mock_database.get_ticket(sample_ticket.ticket_id)
        assert closed_ticket.status == TicketStatus.CLOSED
        assert closed_ticket.transcript_url is None
    
    @pytest.mark.asyncio
    async def test_close_ticket_with_reason(self, ticket_manager, mock_channel, mock_staff,
                                           sample_ticket, mock_database):
        """Test closing ticket with a reason."""
        await mock_database.create_ticket(sample_ticket)
        
        with patch.object(ticket_manager, 'get_ticket_by_channel', return_value=sample_ticket):
            with patch.object(ticket_manager, '_generate_transcript', return_value="transcript"):
                with patch.object(ticket_manager, '_save_transcript', return_value="/path/to/transcript"):
                    with patch.object(ticket_manager, '_archive_channel'):
                        with patch('asyncio.sleep'):
                            result = await ticket_manager.close_ticket(
                                mock_channel, mock_staff, reason="Issue resolved"
                            )
        
        assert result is True
        
        # Verify closing message was sent with reason
        mock_channel.send.assert_called()
        embed_arg = mock_channel.send.call_args[1]['embed']
        assert any(field.name == "Reason" and field.value == "Issue resolved" 
                  for field in embed_arg.fields)


class TestForceCloseTicket:
    """Test force close ticket functionality."""
    
    @pytest.mark.asyncio
    async def test_force_close_ticket_success(self, ticket_manager, mock_staff,
                                             sample_ticket, mock_database, mock_bot):
        """Test successful force close ticket."""
        await mock_database.create_ticket(sample_ticket)
        
        # Mock guild
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = sample_ticket.guild_id
        mock_guild.get_member.return_value = MagicMock(spec=discord.Member)
        mock_guild.name = "Test Guild"
        mock_bot.get_guild.return_value = mock_guild
        
        result = await ticket_manager.force_close_ticket(
            sample_ticket.ticket_id, mock_staff
        )
        
        assert result is True
        
        # Verify ticket was closed in database
        closed_ticket = await mock_database.get_ticket(sample_ticket.ticket_id)
        assert closed_ticket.status == TicketStatus.CLOSED
        assert closed_ticket.closed_at is not None
    
    @pytest.mark.asyncio
    async def test_force_close_ticket_not_found(self, ticket_manager, mock_staff):
        """Test force closing non-existent ticket."""
        with pytest.raises(TicketNotFoundError):
            await ticket_manager.force_close_ticket("NONEXISTENT", mock_staff)
    
    @pytest.mark.asyncio
    async def test_force_close_ticket_already_closed(self, ticket_manager, mock_staff,
                                                    sample_ticket, mock_database, mock_bot):
        """Test force closing already closed ticket."""
        sample_ticket.status = TicketStatus.CLOSED
        await mock_database.create_ticket(sample_ticket)
        
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = sample_ticket.guild_id
        mock_bot.get_guild.return_value = mock_guild
        
        with pytest.raises(TicketClosingError, match="already closed"):
            await ticket_manager.force_close_ticket(sample_ticket.ticket_id, mock_staff)
    
    @pytest.mark.asyncio
    async def test_force_close_ticket_guild_not_found(self, ticket_manager, mock_staff,
                                                     sample_ticket, mock_database, mock_bot):
        """Test force closing ticket when guild not found."""
        await mock_database.create_ticket(sample_ticket)
        mock_bot.get_guild.return_value = None
        
        with pytest.raises(TicketClosingError, match="Guild .* not found"):
            await ticket_manager.force_close_ticket(sample_ticket.ticket_id, mock_staff)
    
    @pytest.mark.asyncio
    async def test_force_close_ticket_insufficient_permissions(self, ticket_manager,
                                                              sample_ticket, mock_database, mock_bot):
        """Test force closing ticket without staff permissions."""
        await mock_database.create_ticket(sample_ticket)
        
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = sample_ticket.guild_id
        mock_bot.get_guild.return_value = mock_guild
        
        # Create non-staff user
        non_staff = MagicMock(spec=discord.Member)
        non_staff.id = 88888
        non_staff.roles = [MagicMock(id=99999)]  # Not a staff role
        
        with pytest.raises(PermissionError, match="not authorized"):
            await ticket_manager.force_close_ticket(sample_ticket.ticket_id, non_staff)


if __name__ == "__main__":
    pytest.main([__file__])