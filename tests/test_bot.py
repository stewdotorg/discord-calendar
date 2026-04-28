"""Tests for the Discord bot client setup."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot import DiscalClient
from src.commands.list_events import cal
from src.commands.ping import ping
from tests.test_calendar import VALID_KEY_JSON


def test_bot_has_command_tree():
    """The DiscalClient initializes with an app_commands.CommandTree."""
    client = DiscalClient()
    assert client.tree is not None
    assert isinstance(client.tree, discord.app_commands.CommandTree)


def test_bot_has_no_message_content_intent():
    """The bot uses default intents only — no privileged intents needed."""
    client = DiscalClient()
    assert not client.intents.message_content
    assert not client.intents.members
    assert not client.intents.presences


@pytest.mark.asyncio
async def test_setup_hook_registers_commands_and_syncs():
    """setup_hook registers ping and cal commands, syncs the command tree,
    and initialises the calendar."""
    client = DiscalClient()

    client.tree.add_command = MagicMock()
    client.tree.sync = AsyncMock()
    client._init_calendar = MagicMock(return_value=None)

    await client.setup_hook()

    assert client.tree.add_command.call_count == 2
    client.tree.add_command.assert_any_call(ping)
    client.tree.add_command.assert_any_call(cal)
    client.tree.sync.assert_called_once()
    client._init_calendar.assert_called_once()


# ── _init_calendar ───────────────────────────────────────────────────────────


class TestInitCalendar:
    """Tests for the DiscalClient._init_calendar method."""

    def test_returns_none_when_env_vars_unset(self, monkeypatch):
        """_init_calendar returns None when calendar env vars are empty."""
        monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
        monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)

        client = DiscalClient()
        result = client._init_calendar()

        assert result is None

    def test_returns_service_on_success(self, monkeypatch, tmp_path):
        """_init_calendar returns a CalendarService when auth succeeds."""
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
        monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", "/nonexistent/key.json")
        monkeypatch.setenv("GOOGLE_CALENDAR_ID", "test-cal")

        client = DiscalClient()

        with pytest.raises(SystemExit) as exc_info:
            client._init_calendar()

        assert exc_info.value.code == 1

    def test_exits_on_verify_failure(self, monkeypatch, tmp_path):
        """_init_calendar calls sys.exit(1) when verify_access raises RuntimeError."""
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


@pytest.mark.asyncio
async def test_on_ready_logs_ready():
    """on_ready logs 'Ready' with the bot's username."""
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
