"""Tests for the Discord bot client setup."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot import DiscalClient
from src.commands.list_events import cal
from tests import VALID_KEY_JSON


def test_bot_has_command_tree(monkeypatch):
    """The DiscalClient initializes with an app_commands.CommandTree."""
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    client = DiscalClient()
    assert client.tree is not None
    assert isinstance(client.tree, discord.app_commands.CommandTree)


def test_bot_has_message_content_intent(monkeypatch):
    """The bot requires message_content intent for DM reply handling."""
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    client = DiscalClient()
    assert client.intents.message_content
    assert not client.intents.members
    assert not client.intents.presences


@pytest.mark.asyncio
async def test_setup_hook_registers_commands_and_syncs(monkeypatch):
    """setup_hook registers cal on guild tree, syncs guild + global purge, inits calendar."""
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    monkeypatch.setenv("DISCORD_GUILD_ID", "999999999999999999")
    client = DiscalClient()

    client.tree.add_command = MagicMock()
    client.tree.sync = AsyncMock()
    client._init_calendar = MagicMock(return_value=None)

    await client.setup_hook()

    # add_command called once with guild= and override=True kwargs
    assert client.tree.add_command.call_count == 1
    call_kwargs = client.tree.add_command.call_args.kwargs
    assert call_kwargs.get("guild") is not None
    assert call_kwargs.get("override") is True
    client.tree.add_command.assert_any_call(cal, **call_kwargs)

    # sync called twice: guild sync then global purge
    assert client.tree.sync.call_count == 2
    # first call: guild sync
    first_call = client.tree.sync.call_args_list[0]
    assert first_call.kwargs.get("guild") is not None
    # second call: global purge (no guild kwarg)
    second_call = client.tree.sync.call_args_list[1]
    assert second_call.kwargs.get("guild") is None

    client._init_calendar.assert_called_once()


# ── _init_calendar ───────────────────────────────────────────────────────────


class TestInitCalendar:
    """Tests for the DiscalClient._init_calendar method."""

    def test_returns_none_when_env_vars_unset(self, monkeypatch):
        """_init_calendar returns None when calendar env vars are empty."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
        monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)

        client = DiscalClient()
        result = client._init_calendar()

        assert result is None

    def test_returns_service_on_success(self, monkeypatch, tmp_path):
        """_init_calendar returns a CalendarService when auth succeeds."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        key_file = tmp_path / "key.json"
        key_file.write_text(VALID_KEY_JSON)

        monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(key_file))
        monkeypatch.setenv("GOOGLE_CALENDAR_ID", "test-cal@group.calendar.google.com")

        with patch("src.bot.CalendarService") as MockSvc:
            mock_service = MagicMock()
            MockSvc.return_value = mock_service

            client = DiscalClient()
            result = client._init_calendar()

            assert result is mock_service
            MockSvc.assert_called_once()
            mock_service.verify_access.assert_called_once()

    def test_exits_on_credential_error(self, monkeypatch):
        """_init_calendar calls sys.exit(1) when credentials cannot be loaded."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", "/nonexistent/key.json")
        monkeypatch.setenv("GOOGLE_CALENDAR_ID", "test-cal")

        client = DiscalClient()

        with pytest.raises(SystemExit) as exc_info:
            client._init_calendar()

        assert exc_info.value.code == 1

    def test_exits_on_verify_failure(self, monkeypatch, tmp_path):
        """_init_calendar calls sys.exit(1) when verify_access raises RuntimeError."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        key_file = tmp_path / "key.json"
        key_file.write_text(VALID_KEY_JSON)

        monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(key_file))
        monkeypatch.setenv("GOOGLE_CALENDAR_ID", "test-cal")

        with patch("src.bot.CalendarService") as MockSvc:
            mock_service = MagicMock()
            mock_service.verify_access.side_effect = RuntimeError("API error")
            MockSvc.return_value = mock_service

            client = DiscalClient()

            with pytest.raises(SystemExit) as exc_info:
                client._init_calendar()

            assert exc_info.value.code == 1


# ── on_message ───────────────────────────────────────────────────────────────


class TestOnMessage:
    """Tests for the DiscalClient.on_message handler."""

    @pytest.mark.asyncio
    async def test_dm_message_with_pending_invite_is_handled(self, monkeypatch):
        """When a DM arrives from a user with a pending invite,
        handle_dm_reply is called and processing returns True."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        initial_cal = MagicMock()
        with patch("src.bot.handle_dm_reply", new_callable=AsyncMock) as mock_handle:
            mock_handle.return_value = True
            client = DiscalClient()
            client.calendar = initial_cal

            message = MagicMock()
            message.author = MagicMock()
            message.guild = None  # DM

            await client.on_message(message)

            mock_handle.assert_called_once_with(
                message, client.settings, initial_cal
            )

    @pytest.mark.asyncio
    async def test_guild_message_is_ignored(self, monkeypatch):
        """Messages in guild channels are not processed by on_message."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        with patch("src.bot.handle_dm_reply", new_callable=AsyncMock) as mock_handle:
            client = DiscalClient()
            client.calendar = MagicMock()

            message = MagicMock()
            message.author = MagicMock()
            message.guild = MagicMock()  # Not a DM

            await client.on_message(message)

            mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_own_message_is_skipped(self, monkeypatch):
        """The bot's own messages are skipped before any processing."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        with patch("src.bot.handle_dm_reply", new_callable=AsyncMock) as mock_handle:
            client = DiscalClient()
            client.calendar = MagicMock()

            message = MagicMock()
            # author is the bot itself
            message.author = client.user
            message.guild = None

            await client.on_message(message)

            mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_calendar_is_ignored(self, monkeypatch):
        """When calendar is None, DMs are silently ignored."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        with patch("src.bot.handle_dm_reply", new_callable=AsyncMock) as mock_handle:
            client = DiscalClient()
            client.calendar = None

            message = MagicMock()
            message.author = MagicMock()
            message.guild = None

            await client.on_message(message)

            mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_in_handler_is_caught_and_logged(self, monkeypatch):
        """When handle_dm_reply raises an unexpected exception,
        it is caught and logged so on_message doesn't crash."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        with patch("src.bot.handle_dm_reply", new_callable=AsyncMock) as mock_handle:
            mock_handle.side_effect = RuntimeError("unexpected DB error")
            client = DiscalClient()
            client.calendar = MagicMock()

            message = MagicMock()
            message.author = MagicMock()
            message.guild = None

            with patch.object(
                logging.getLogger("src.bot"), "error"
            ) as mock_log:
                # Should not raise
                await client.on_message(message)

                mock_handle.assert_called_once()
                mock_log.assert_called_once()
                assert "handle_dm_reply" in mock_log.call_args.args[0]


@pytest.mark.asyncio
async def test_on_ready_logs_ready(monkeypatch):
    """on_ready logs 'Ready' with the bot's username."""
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    client = DiscalClient()

    mock_user = MagicMock()
    mock_user.name = "DiscalBot"

    with patch.object(type(client), "user", new_callable=lambda: property(lambda self: mock_user)):
        with patch.object(logging.getLogger("src.bot"), "info") as mock_log:
            await client.on_ready()
            mock_log.assert_called_once()
            fmt_string, name = mock_log.call_args[0]
            assert fmt_string == "Ready: %s"
            assert name == "DiscalBot"
