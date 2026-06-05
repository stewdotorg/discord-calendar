"""Tests for the Discord bot client setup."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot import DiscalClient
from src.commands.list_events import cal
from tests import VALID_KEY_JSON


def _make_client(monkeypatch, message_content_enabled=None):
    """Create a DiscalClient with the user property mocked.

    Returns (client, mock_user) where mock_user has name="DiscalBot" and the
    client.user property is patched to return it.
    """
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    if message_content_enabled is not None:
        monkeypatch.setenv("DISCORD_ENABLE_MESSAGE_CONTENT", message_content_enabled)
    else:
        monkeypatch.delenv("DISCORD_ENABLE_MESSAGE_CONTENT", raising=False)
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


def test_bot_has_message_content_intent(monkeypatch):
    """When DISCORD_ENABLE_MESSAGE_CONTENT is true, the intent is enabled."""
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    monkeypatch.setenv("DISCORD_ENABLE_MESSAGE_CONTENT", "true")
    client = DiscalClient()
    assert client.intents.message_content
    assert not client.intents.members
    assert not client.intents.presences


def test_message_content_intent_disabled_by_default(monkeypatch):
    """When DISCORD_ENABLE_MESSAGE_CONTENT is unset, the intent is disabled."""
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    monkeypatch.delenv("DISCORD_ENABLE_MESSAGE_CONTENT", raising=False)
    client = DiscalClient()
    assert not client.intents.message_content


def test_message_content_intent_disabled_when_false(monkeypatch):
    """When DISCORD_ENABLE_MESSAGE_CONTENT is 'false', the intent is disabled."""
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    monkeypatch.setenv("DISCORD_ENABLE_MESSAGE_CONTENT", "false")
    client = DiscalClient()
    assert not client.intents.message_content


def test_message_content_intent_case_insensitive(monkeypatch):
    """DISCORD_ENABLE_MESSAGE_CONTENT is case-insensitive: 'TRUE' enables it."""
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    monkeypatch.setenv("DISCORD_ENABLE_MESSAGE_CONTENT", "TRUE")
    client = DiscalClient()
    assert client.intents.message_content


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
        monkeypatch.setenv("DISCORD_ENABLE_MESSAGE_CONTENT", "true")
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
        monkeypatch.setenv("DISCORD_ENABLE_MESSAGE_CONTENT", "true")
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
        monkeypatch.setenv("DISCORD_ENABLE_MESSAGE_CONTENT", "true")
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
        monkeypatch.setenv("DISCORD_ENABLE_MESSAGE_CONTENT", "true")
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
        monkeypatch.setenv("DISCORD_ENABLE_MESSAGE_CONTENT", "true")
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
    async def test_dm_skipped_when_message_content_disabled(self, monkeypatch):
        """When message_content is disabled, DM handling is skipped entirely."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        # message_content defaults to disabled when unset
        with patch("src.bot.handle_dm_reply", new_callable=AsyncMock) as mock_handle:
            client = DiscalClient()
            client.calendar = MagicMock()

            message = MagicMock()
            message.author = MagicMock()
            message.guild = None

            await client.on_message(message)
            mock_handle.assert_not_called()


class TestOnInteractionRSVP:
    """Tests for RSVP on_interaction handling with message_content feature flag."""

    @pytest.mark.asyncio
    async def test_non_rsvp_interactions_ignored(self, monkeypatch):
        """on_interaction ignores non-component and non-RSVP interactions."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        monkeypatch.setenv("DISCORD_ENABLE_MESSAGE_CONTENT", "true")
        client = DiscalClient()

        # Non-component interaction
        interaction = MagicMock()
        interaction.type = discord.InteractionType.ping
        interaction.data = {"custom_id": "rsvp:abc123"}

        with patch("src.bot._handle_rsvp_interaction", new_callable=AsyncMock) as mock_rsvp:
            await client.on_interaction(interaction)
            mock_rsvp.assert_not_called()

    @pytest.mark.asyncio
    async def test_rsvp_interaction_handled_when_message_content_enabled(self, monkeypatch):
        """on_interaction forwards RSVP button clicks when message_content is enabled."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        monkeypatch.setenv("DISCORD_ENABLE_MESSAGE_CONTENT", "true")
        client = DiscalClient()

        interaction = MagicMock()
        interaction.type = discord.InteractionType.component
        interaction.data = {"custom_id": "rsvp:abc123"}

        with patch("src.bot._handle_rsvp_interaction", new_callable=AsyncMock) as mock_rsvp:
            await client.on_interaction(interaction)
            mock_rsvp.assert_called_once_with(interaction, "abc123")

    @pytest.mark.asyncio
    async def test_rsvp_interaction_handled_when_message_content_disabled(self, monkeypatch):
        """on_interaction handles RSVP button clicks even when message_content is disabled.

        RSVP interactions are component interactions that don't need the
        message_content privileged intent — the custom_id is always available.
        """
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        # message_content defaults to disabled
        client = DiscalClient()

        interaction = MagicMock()
        interaction.type = discord.InteractionType.component
        interaction.data = {"custom_id": "rsvp:abc123"}

        with patch("src.bot._handle_rsvp_interaction", new_callable=AsyncMock) as mock_rsvp:
            await client.on_interaction(interaction)
            mock_rsvp.assert_called_once_with(interaction, "abc123")


@pytest.mark.asyncio
async def test_on_ready_logs_ready(monkeypatch):
    """on_ready logs 'Ready' with the bot's username."""
    client, mock_user = _make_client(monkeypatch)

    with patch.object(type(client), "user", new_callable=lambda: property(lambda self: mock_user)):
        with patch("src.bot.notify.notify", new_callable=AsyncMock):
            with patch("src.bot.notify.check_and_notify_deploy", new_callable=AsyncMock):
                with patch.object(logging.getLogger("src.bot"), "info") as mock_log:
                    await client.on_ready()
                    mock_log.assert_called()
                    ready_call = [c for c in mock_log.call_args_list
                                  if c[0][0] == "Ready: %s"]
                    assert len(ready_call) == 1
                    assert ready_call[0][0][1] == "DiscalBot"


# ── on_ready notifications ──────────────────────────────────────────────────


class TestOnReadyNotifications:
    """Tests for restart/deploy notifications dispatched from on_ready."""

    @pytest.mark.asyncio
    async def test_sends_restart_notification(self, monkeypatch):
        """on_ready dispatches a restart notification via notify.notify."""
        client, mock_user = _make_client(monkeypatch)
        monkeypatch.setenv("DISCAL_COMMIT_SHA", "abc123")

        with patch.object(type(client), "user",
                          new_callable=lambda: property(lambda self: mock_user)):
            with patch("src.bot.notify.notify", new_callable=AsyncMock) as mock_notify:
                with patch("src.bot.notify.check_and_notify_deploy",
                           new_callable=AsyncMock):
                    await client.on_ready()

                    mock_notify.assert_called_once()
                    call_args = mock_notify.call_args
                    assert call_args[0][0] is client
                    assert call_args[0][1] == "restart"
                    assert call_args.kwargs["sha"] == "abc123"
                    assert "timestamp" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_restart_without_git_sha(self, monkeypatch):
        """Restart notification sends empty string for sha when git unavailable."""
        client, mock_user = _make_client(monkeypatch)
        monkeypatch.delenv("DISCAL_COMMIT_SHA", raising=False)

        with patch.object(type(client), "user",
                          new_callable=lambda: property(lambda self: mock_user)):
            with patch("src.bot.notify.notify", new_callable=AsyncMock) as mock_notify:
                with patch("src.bot.notify.check_and_notify_deploy",
                           new_callable=AsyncMock):
                    with patch("src.bot.notify.get_current_commit_sha",
                               return_value=None):
                        await client.on_ready()
                        assert mock_notify.call_args.kwargs["sha"] == ""

    @pytest.mark.asyncio
    async def test_calls_deploy_check(self, monkeypatch):
        """on_ready calls notify.check_and_notify_deploy."""
        client, mock_user = _make_client(monkeypatch)

        with patch.object(type(client), "user",
                          new_callable=lambda: property(lambda self: mock_user)):
            with patch("src.bot.notify.notify", new_callable=AsyncMock):
                with patch("src.bot.notify.check_and_notify_deploy",
                           new_callable=AsyncMock) as mock_deploy:
                    await client.on_ready()
                    mock_deploy.assert_called_once_with(client)

    @pytest.mark.asyncio
    async def test_cleans_up_expired_invites(self, monkeypatch):
        """on_ready calls settings.cleanup_expired_invites."""
        client, mock_user = _make_client(monkeypatch)
        client.settings.cleanup_expired_invites = MagicMock()

        with patch.object(type(client), "user",
                          new_callable=lambda: property(lambda self: mock_user)):
            with patch("src.bot.notify.notify", new_callable=AsyncMock):
                with patch("src.bot.notify.check_and_notify_deploy",
                           new_callable=AsyncMock):
                    await client.on_ready()
                    client.settings.cleanup_expired_invites.assert_called_once()


# ── close / shutdown notification ───────────────────────────────────────────


class TestCloseShutdown:
    """Tests for shutdown notification in close()."""

    @pytest.mark.asyncio
    async def test_close_sends_shutdown_notification(self, monkeypatch):
        """close() dispatches a shutdown notification then calls super()."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        client = DiscalClient()

        with patch("src.bot.notify.notify", new_callable=AsyncMock) as mock_notify:
            # Patch super().close() so it doesn't actually close anything
            with patch.object(discord.Client, "close", new_callable=AsyncMock) as mock_super:
                await client.close()

                mock_notify.assert_called_once()
                call_args = mock_notify.call_args
                assert call_args[0][0] is client
                assert call_args[0][1] == "shutdown"
                assert "timestamp" in call_args.kwargs
                mock_super.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_super_called_even_when_notify_fails(self, monkeypatch):
        """When notify raises, close() still calls super().close()."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        client = DiscalClient()

        with patch("src.bot.notify.notify", new_callable=AsyncMock,
                   side_effect=RuntimeError("notify blew up")):
            with patch.object(discord.Client, "close", new_callable=AsyncMock) as mock_super:
                await client.close()
                mock_super.assert_called_once()


# ── on_error ────────────────────────────────────────────────────────────────


class TestOnError:
    """Tests for the global error handler (gateway events)."""

    @pytest.mark.asyncio
    async def test_on_error_sends_notification(self, monkeypatch):
        """on_error dispatches an error notification with handler and message."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        client = DiscalClient()

        with patch("src.bot.notify.notify", new_callable=AsyncMock) as mock_notify:
            # Simulate an error having occurred
            try:
                raise ValueError("test error")
            except ValueError:
                await client.on_error("on_message")

            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            assert call_args[0][0] is client
            assert call_args[0][1] == "error"
            assert call_args.kwargs["handler"] == "event:on_message"
            assert call_args.kwargs["message"] == "test error"

    @pytest.mark.asyncio
    async def test_on_error_notify_failure_is_caught(self, monkeypatch):
        """When notify raises in on_error, it logs and doesn't propagate."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        client = DiscalClient()

        with patch("src.bot.notify.notify", new_callable=AsyncMock,
                   side_effect=RuntimeError("notify failed")):
            try:
                raise ValueError("test")
            except ValueError:
                # Should not raise
                await client.on_error("on_message")


# ── _on_tree_error ──────────────────────────────────────────────────────────


class TestOnTreeError:
    """Tests for the tree (slash-command) error handler."""

    @pytest.mark.asyncio
    async def test_sends_error_notification_with_command_name(self, monkeypatch):
        """_on_tree_error dispatches notification with command name in handler."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        client = DiscalClient()

        interaction = MagicMock()
        interaction.command = MagicMock()
        interaction.command.name = "create"
        error = discord.app_commands.CommandInvokeError(
            MagicMock(), "Something broke"
        )

        with patch("src.bot.notify.notify", new_callable=AsyncMock) as mock_notify:
            await client._on_tree_error(interaction, error)

            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            assert call_args[0][0] is client
            assert call_args[0][1] == "error"
            assert call_args.kwargs["handler"] == "command:/create"
            assert "Something broke" in call_args.kwargs["message"]

    @pytest.mark.asyncio
    async def test_unknown_command_uses_fallback_name(self, monkeypatch):
        """When interaction.command is None, uses 'unknown' as command name."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        client = DiscalClient()

        interaction = MagicMock()
        interaction.command = None
        error = ValueError("bad")

        with patch("src.bot.notify.notify", new_callable=AsyncMock) as mock_notify:
            await client._on_tree_error(interaction, error)

            assert mock_notify.call_args.kwargs["handler"] == "command:/unknown"

    @pytest.mark.asyncio
    async def test_notify_failure_is_caught(self, monkeypatch):
        """When notify raises in _on_tree_error, it's caught and logged."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
        client = DiscalClient()

        interaction = MagicMock()
        interaction.command = None
        error = ValueError("bad")

        with patch("src.bot.notify.notify", new_callable=AsyncMock,
                   side_effect=RuntimeError("no")):
            # Should not raise
            await client._on_tree_error(interaction, error)
