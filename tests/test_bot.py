"""Tests for the Discord bot client setup."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot import DiscalClient
from src.commands.list_events import cal
from tests import VALID_KEY_JSON

ADMIN_USER_ID = "123456789012345678"


def _make_client(monkeypatch, admin_id=None):
    """Create a DiscalClient with the user property mocked and optional admin config.

    Returns (client, mock_user) where mock_user has name="DiscalBot" and the
    client.user property is patched to return it.
    """
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    if admin_id is not None:
        monkeypatch.setenv("DISCORD_ADMIN_USER_ID", admin_id)
    else:
        monkeypatch.delenv("DISCORD_ADMIN_USER_ID", raising=False)
    client = DiscalClient()
    mock_user = MagicMock()
    mock_user.name = "DiscalBot"
    return client, mock_user


def test_bot_has_command_tree(monkeypatch):
    """The DiscalClient initializes with an app_commands.CommandTree."""
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    client = DiscalClient()
    assert client.tree is not None
    assert isinstance(client.tree, discord.app_commands.CommandTree)


def test_bot_has_no_message_content_intent(monkeypatch):
    """The bot uses default intents only — no privileged intents needed."""
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    client = DiscalClient()
    assert not client.intents.message_content
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


@pytest.mark.asyncio
async def test_on_ready_logs_ready(monkeypatch):
    """on_ready logs 'Ready' with the bot's username."""
    client, mock_user = _make_client(monkeypatch, admin_id=None)

    with patch.object(type(client), "user", new_callable=lambda: property(lambda self: mock_user)):
        with patch.object(logging.getLogger("src.bot"), "info") as mock_log:
            await client.on_ready()
            mock_log.assert_called()
            ready_call = [c for c in mock_log.call_args_list
                          if c[0][0] == "Ready: %s"]
            assert len(ready_call) == 1
            assert ready_call[0][0][1] == "DiscalBot"


# ── on_ready DM admin ────────────────────────────────────────────────────────


class TestOnReadyDMAdmin:
    """Tests for DM-to-admin-on-restart functionality in on_ready."""

    @pytest.mark.asyncio
    async def test_no_dm_when_admin_not_configured(self, monkeypatch):
        """on_ready does not attempt DM when DISCORD_ADMIN_USER_ID is unset."""
        client, mock_user = _make_client(monkeypatch, admin_id=None)

        with patch.object(type(client), "user",
                          new_callable=lambda: property(lambda self: mock_user)):
            with patch.object(client, "fetch_user", new_callable=AsyncMock) as mock_fetch:
                await client.on_ready()
                mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_dm_on_restart(self, monkeypatch):
        """on_ready fetches admin user and sends a DM with restart timestamp."""
        client, mock_user = _make_client(monkeypatch, admin_id=ADMIN_USER_ID)

        mock_admin = MagicMock()
        mock_admin.send = AsyncMock()

        with patch.object(type(client), "user",
                          new_callable=lambda: property(lambda self: mock_user)):
            with patch.object(client, "fetch_user", new_callable=AsyncMock,
                              return_value=mock_admin) as mock_fetch:
                await client.on_ready()

                mock_fetch.assert_called_once_with(int(ADMIN_USER_ID))
                mock_admin.send.assert_called_once()
                msg = mock_admin.send.call_args.args[0]
                assert "Discal restarted at" in msg

    @pytest.mark.asyncio
    async def test_warns_when_admin_user_not_found(self, monkeypatch):
        """on_ready logs warning when admin user ID not found on Discord."""
        client, mock_user = _make_client(monkeypatch, admin_id=ADMIN_USER_ID)

        with patch.object(type(client), "user",
                          new_callable=lambda: property(lambda self: mock_user)):
            with patch.object(client, "fetch_user", new_callable=AsyncMock,
                              side_effect=discord.NotFound(
                                  MagicMock(), "User not found")):
                with patch.object(logging.getLogger("src.bot"), "warning") as mock_warn:
                    await client.on_ready()
                    mock_warn.assert_called()
                    assert "admin user" in mock_warn.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_warns_when_dm_blocked(self, monkeypatch):
        """on_ready logs warning when admin has DMs blocked."""
        client, mock_user = _make_client(monkeypatch, admin_id=ADMIN_USER_ID)

        mock_admin = MagicMock()
        mock_admin.send = AsyncMock(side_effect=discord.Forbidden(
            MagicMock(), "Cannot send DM"))

        with patch.object(type(client), "user",
                          new_callable=lambda: property(lambda self: mock_user)):
            with patch.object(client, "fetch_user", new_callable=AsyncMock,
                              return_value=mock_admin):
                with patch.object(logging.getLogger("src.bot"), "warning") as mock_warn:
                    await client.on_ready()
                    mock_warn.assert_called()
                    assert "dm" in mock_warn.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_warns_on_fetch_http_error(self, monkeypatch):
        """on_ready logs warning when fetching admin user fails with HTTP error."""
        client, mock_user = _make_client(monkeypatch, admin_id=ADMIN_USER_ID)

        with patch.object(type(client), "user",
                          new_callable=lambda: property(lambda self: mock_user)):
            with patch.object(client, "fetch_user", new_callable=AsyncMock,
                              side_effect=discord.HTTPException(
                                  MagicMock(), "Rate limited")):
                with patch.object(logging.getLogger("src.bot"), "warning") as mock_warn:
                    await client.on_ready()
                    mock_warn.assert_called()
                    assert "admin" in mock_warn.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_no_dm_when_admin_id_empty_string(self, monkeypatch):
        """on_ready treats empty string admin id as not configured."""
        client, mock_user = _make_client(monkeypatch, admin_id="")

        with patch.object(type(client), "user",
                          new_callable=lambda: property(lambda self: mock_user)):
            with patch.object(client, "fetch_user", new_callable=AsyncMock) as mock_fetch:
                await client.on_ready()
                mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_warns_when_admin_id_invalid(self, monkeypatch):
        """on_ready logs warning when admin user ID is not a valid integer."""
        client, mock_user = _make_client(monkeypatch, admin_id="not-a-number")

        with patch.object(type(client), "user",
                          new_callable=lambda: property(lambda self: mock_user)):
            with patch.object(client, "fetch_user", new_callable=AsyncMock) as mock_fetch:
                with patch.object(logging.getLogger("src.bot"), "warning") as mock_warn:
                    await client.on_ready()
                    mock_fetch.assert_not_called()
                    mock_warn.assert_called()
                    assert "invalid" in mock_warn.call_args[0][0].lower()
