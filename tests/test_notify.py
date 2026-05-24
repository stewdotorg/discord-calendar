"""Tests for the notification module — config parsing, dispatch, deploy detection."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.notify import (
    _build_message,
    _send_to_target,
    check_deploy,
    get_current_commit_sha,
    notify,
    parse_notify_events,
    parse_notify_targets,
)


# ── parse_notify_targets ─────────────────────────────────────────────────────


class TestParseNotifyTargets:
    """Tests for parse_notify_targets."""

    def test_empty_string_returns_empty_list(self):
        """Empty string returns empty list."""
        assert parse_notify_targets("") == []

    def test_single_user_target(self):
        """Single u: prefix parses to ('user', id)."""
        assert parse_notify_targets("u:123456789") == [("user", 123456789)]

    def test_single_channel_target(self):
        """Single c: prefix parses to ('channel', id)."""
        assert parse_notify_targets("c:987654321") == [("channel", 987654321)]

    def test_multiple_targets(self):
        """Comma-separated targets of both types parse correctly."""
        result = parse_notify_targets("u:123456789,c:987654321,u:111222333")
        assert result == [
            ("user", 123456789),
            ("channel", 987654321),
            ("user", 111222333),
        ]

    def test_whitespace_is_stripped(self):
        """Whitespace around entries is stripped."""
        result = parse_notify_targets(" u:123 , c:456 ")
        assert result == [("user", 123), ("channel", 456)]

    def test_trailing_comma_is_ignored(self):
        """Trailing commas produce no extra entries."""
        result = parse_notify_targets("u:123,")
        assert result == [("user", 123)]

    def test_invalid_prefix_is_warned_and_skipped(self):
        """Entries without u: or c: prefix log warning and are skipped."""
        result = parse_notify_targets("x:123,u:456")
        assert result == [("user", 456)]

    def test_invalid_id_is_warned_and_skipped(self):
        """Non-numeric IDs log warning and are skipped."""
        result = parse_notify_targets("u:abc,c:456")
        assert result == [("channel", 456)]

    def test_reads_from_env_when_no_argument(self, monkeypatch):
        """When called without args, reads DISCORD_NOTIFY_TARGETS from env."""
        monkeypatch.setenv("DISCORD_NOTIFY_TARGETS", "u:111,c:222")
        assert parse_notify_targets() == [("user", 111), ("channel", 222)]


# ── parse_notify_events ─────────────────────────────────────────────────────


class TestParseNotifyEvents:
    """Tests for parse_notify_events."""

    def test_empty_string_returns_defaults(self):
        """Empty string returns the three default events."""
        assert parse_notify_events("") == {"restart", "shutdown", "error"}

    def test_whitespace_only_returns_defaults(self):
        """Whitespace-only string returns defaults."""
        assert parse_notify_events("  ") == {"restart", "shutdown", "error"}

    def test_single_event(self):
        """Single event parses correctly."""
        assert parse_notify_events("restart") == {"restart"}

    def test_multiple_events(self):
        """Comma-separated events parse correctly."""
        result = parse_notify_events("restart,shutdown,error,deploy")
        assert result == {"restart", "shutdown", "error", "deploy"}

    def test_case_insensitive(self):
        """Event names are case-insensitive."""
        assert parse_notify_events("RESTART,Error,Deploy") == {"restart", "error", "deploy"}

    def test_unknown_event_is_warned_and_skipped(self):
        """Unknown event names are skipped."""
        result = parse_notify_events("restart,unknown_event,error")
        assert result == {"restart", "error"}

    def test_all_unknown_returns_defaults(self):
        """When all events are unknown, defaults are returned."""
        result = parse_notify_events("foo,bar")
        assert result == {"restart", "shutdown", "error"}

    def test_whitespace_is_stripped(self):
        """Whitespace around entries is stripped."""
        result = parse_notify_events(" restart , shutdown ")
        assert result == {"restart", "shutdown"}

    def test_reads_from_env_when_no_argument(self, monkeypatch):
        """When called without args, reads DISCORD_NOTIFY_EVENTS from env."""
        monkeypatch.setenv("DISCORD_NOTIFY_EVENTS", "restart,deploy")
        assert parse_notify_events() == {"restart", "deploy"}


# ── _build_message ───────────────────────────────────────────────────────────


class TestBuildMessage:
    """Tests for _build_message."""

    def test_restart_with_sha(self):
        """Restart message includes timestamp and commit SHA."""
        msg = _build_message("restart", timestamp="2026-01-15 10:30:00 UTC", sha="abc1234")
        assert "🟢" in msg
        assert "Discal restarted" in msg
        assert "2026-01-15 10:30:00 UTC" in msg
        assert "abc1234" in msg

    def test_restart_without_sha(self):
        """Restart message works without commit SHA."""
        msg = _build_message("restart", timestamp="2026-01-15 10:30:00 UTC")
        assert "🟢" in msg
        assert "Discal restarted" in msg
        assert "commit:" not in msg

    def test_shutdown(self):
        """Shutdown message includes timestamp."""
        msg = _build_message("shutdown", timestamp="2026-01-15 10:30:00 UTC")
        assert "🔴" in msg
        assert "Discal shutting down" in msg
        assert "2026-01-15 10:30:00 UTC" in msg

    def test_error(self):
        """Error message includes handler and message."""
        msg = _build_message("error", handler="on_message", message="Something broke")
        assert "⚠️" in msg
        assert "on_message" in msg
        assert "Something broke" in msg

    def test_error_defaults(self):
        """Error message uses defaults when kwargs missing."""
        msg = _build_message("error")
        assert "⚠️" in msg
        assert "unknown" in msg

    def test_deploy(self):
        """Deploy message shows old SHA → new SHA."""
        msg = _build_message("deploy", old_sha="abc1234567", new_sha="def7654321")
        assert "🚀" in msg
        assert "abc1234" in msg  # truncated to 7 chars
        assert "def7654" in msg
        assert "→" in msg


# ── _send_to_target ─────────────────────────────────────────────────────────


class TestSendToTarget:
    """Tests for _send_to_target."""

    @pytest.mark.asyncio
    async def test_user_target_fetches_and_sends(self):
        """User targets call fetch_user then user.send."""
        client = MagicMock()
        mock_user = MagicMock()
        mock_user.send = AsyncMock()
        client.fetch_user = AsyncMock(return_value=mock_user)

        await _send_to_target(client, "user", 123456789, "Hello!")

        client.fetch_user.assert_called_once_with(123456789)
        mock_user.send.assert_called_once_with("Hello!")

    @pytest.mark.asyncio
    async def test_channel_target_uses_get_channel_first(self):
        """Channel targets try get_channel before fetch_channel."""
        client = MagicMock()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        client.get_channel = MagicMock(return_value=mock_channel)

        await _send_to_target(client, "channel", 987654321, "Hello!")

        client.get_channel.assert_called_once_with(987654321)
        client.fetch_channel = AsyncMock()
        client.fetch_channel.assert_not_called()
        mock_channel.send.assert_called_once_with("Hello!")

    @pytest.mark.asyncio
    async def test_channel_target_falls_back_to_fetch_channel(self):
        """Channel targets use fetch_channel when get_channel returns None."""
        client = MagicMock()
        client.get_channel = MagicMock(return_value=None)
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        client.fetch_channel = AsyncMock(return_value=mock_channel)

        await _send_to_target(client, "channel", 987654321, "Hello!")

        client.get_channel.assert_called_once_with(987654321)
        client.fetch_channel.assert_called_once_with(987654321)
        mock_channel.send.assert_called_once_with("Hello!")

    @pytest.mark.asyncio
    async def test_notfound_is_warned_and_swallowed(self):
        """NotFound exception logs warning, does not raise."""
        client = MagicMock()
        client.fetch_user = AsyncMock(side_effect=discord.NotFound(
            MagicMock(), "Not found"))

        # Should not raise
        await _send_to_target(client, "user", 123, "Hello!")

    @pytest.mark.asyncio
    async def test_forbidden_is_warned_and_swallowed(self):
        """Forbidden exception logs warning, does not raise."""
        client = MagicMock()
        mock_user = MagicMock()
        mock_user.send = AsyncMock(side_effect=discord.Forbidden(
            MagicMock(), "Blocked"))
        client.fetch_user = AsyncMock(return_value=mock_user)

        # Should not raise
        await _send_to_target(client, "user", 123, "Hello!")

    @pytest.mark.asyncio
    async def test_http_exception_is_warned_and_swallowed(self):
        """HTTPException logs warning, does not raise."""
        client = MagicMock()
        client.fetch_user = AsyncMock(side_effect=discord.HTTPException(
            MagicMock(), "Rate limited"))

        # Should not raise
        await _send_to_target(client, "user", 123, "Hello!")


# ── notify ────────────────────────────────────────────────────────────────────


class TestNotify:
    """Tests for the notify dispatch function."""

    @pytest.mark.asyncio
    async def test_no_targets_returns_immediately(self, monkeypatch):
        """When DISCORD_NOTIFY_TARGETS is empty, notify returns early."""
        monkeypatch.setenv("DISCORD_NOTIFY_TARGETS", "")
        client = MagicMock()

        with patch("src.notify._send_to_target", new_callable=AsyncMock) as mock_send:
            await notify(client, "restart")
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_disabled_event_is_skipped(self, monkeypatch):
        """Events not in DISCORD_NOTIFY_EVENTS are skipped."""
        monkeypatch.setenv("DISCORD_NOTIFY_TARGETS", "u:123")
        monkeypatch.setenv("DISCORD_NOTIFY_EVENTS", "restart,error")

        with patch("src.notify._send_to_target", new_callable=AsyncMock) as mock_send:
            await notify(client=MagicMock(), event="shutdown")
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_enabled_event_dispatches_to_all_targets(self, monkeypatch):
        """Enabled events are sent to all configured targets."""
        monkeypatch.setenv("DISCORD_NOTIFY_TARGETS", "u:123,c:456")
        monkeypatch.setenv("DISCORD_NOTIFY_EVENTS", "restart,shutdown,error")
        client = MagicMock()

        with patch("src.notify._send_to_target", new_callable=AsyncMock) as mock_send:
            await notify(client, "restart")

            assert mock_send.call_count == 2
            calls = [c.args for c in mock_send.call_args_list]
            assert ("user", 123) in [(c[1], c[2]) for c in calls]
            assert ("channel", 456) in [(c[1], c[2]) for c in calls]

    @pytest.mark.asyncio
    async def test_default_events_when_unset(self, monkeypatch):
        """When DISCORD_NOTIFY_EVENTS is unset, default events fire."""
        monkeypatch.setenv("DISCORD_NOTIFY_TARGETS", "u:123")
        monkeypatch.delenv("DISCORD_NOTIFY_EVENTS", raising=False)
        client = MagicMock()

        with patch("src.notify._send_to_target", new_callable=AsyncMock) as mock_send:
            await notify(client, "restart")
            assert mock_send.call_count == 1

        with patch("src.notify._send_to_target", new_callable=AsyncMock) as mock_send:
            await notify(client, "deploy")
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_deploy_event_only_when_explicitly_enabled(self, monkeypatch):
        """Deploy does NOT fire by default; only when explicitly listed."""
        monkeypatch.setenv("DISCORD_NOTIFY_TARGETS", "u:123")
        monkeypatch.delenv("DISCORD_NOTIFY_EVENTS", raising=False)
        client = MagicMock()

        with patch("src.notify._send_to_target", new_callable=AsyncMock) as mock_send:
            await notify(client, "deploy")
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_deploy_event_fires_when_explicitly_enabled(self, monkeypatch):
        """Deploy DOES fire when explicitly in DISCORD_NOTIFY_EVENTS."""
        monkeypatch.setenv("DISCORD_NOTIFY_TARGETS", "u:123")
        monkeypatch.setenv("DISCORD_NOTIFY_EVENTS", "restart,error,deploy")
        client = MagicMock()

        with patch("src.notify._send_to_target", new_callable=AsyncMock) as mock_send:
            await notify(client, "deploy", old_sha="a1b2c3d", new_sha="e4f5g6h")
            assert mock_send.call_count == 1

    @pytest.mark.asyncio
    async def test_message_content_disabled_skips_user_targets(self, monkeypatch):
        """When message_content is disabled, user DM targets are skipped,
        but channel targets still receive notifications."""
        monkeypatch.setenv("DISCORD_NOTIFY_TARGETS", "u:123,c:456")
        monkeypatch.setenv("DISCORD_NOTIFY_EVENTS", "restart")
        client = MagicMock()
        client._message_content_enabled = False

        with patch("src.notify._send_to_target", new_callable=AsyncMock) as mock_send:
            await notify(client, "restart")

            # Only channel target should be sent
            assert mock_send.call_count == 1
            call_args = mock_send.call_args.args
            assert call_args[1] == "channel"
            assert call_args[2] == 456

    @pytest.mark.asyncio
    async def test_message_content_enabled_sends_to_all(self, monkeypatch):
        """When message_content is enabled, all targets receive notifications."""
        monkeypatch.setenv("DISCORD_NOTIFY_TARGETS", "u:123,c:456")
        monkeypatch.setenv("DISCORD_NOTIFY_EVENTS", "restart")
        client = MagicMock()
        client._message_content_enabled = True

        with patch("src.notify._send_to_target", new_callable=AsyncMock) as mock_send:
            await notify(client, "restart")
            assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_missing_message_content_attr_treats_as_enabled(self, monkeypatch):
        """When client doesn't have _message_content_enabled, all targets fire."""
        monkeypatch.setenv("DISCORD_NOTIFY_TARGETS", "u:123,c:456")
        monkeypatch.setenv("DISCORD_NOTIFY_EVENTS", "restart")
        client = MagicMock()
        # No _message_content_enabled attribute

        with patch("src.notify._send_to_target", new_callable=AsyncMock) as mock_send:
            await notify(client, "restart")
            assert mock_send.call_count == 2


# ── get_current_commit_sha ──────────────────────────────────────────────────


class TestGetCurrentCommitSha:
    """Tests for get_current_commit_sha."""

    def test_reads_from_env_var(self, monkeypatch):
        """Prefers DISCAL_COMMIT_SHA env var when set."""
        monkeypatch.setenv("DISCAL_COMMIT_SHA", "abc123def456")
        assert get_current_commit_sha() == "abc123def456"

    def test_falls_back_to_git(self, monkeypatch):
        """Falls back to git rev-parse when env var unset."""
        monkeypatch.delenv("DISCAL_COMMIT_SHA", raising=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="def789abc\n")
            result = get_current_commit_sha()
            assert result == "def789abc"

    def test_returns_none_when_git_fails(self, monkeypatch):
        """Returns None when both env var and git are unavailable."""
        monkeypatch.delenv("DISCAL_COMMIT_SHA", raising=False)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = get_current_commit_sha()
            assert result is None

    def test_returns_none_when_git_nonzero(self, monkeypatch):
        """Returns None when git rev-parse returns non-zero."""
        monkeypatch.delenv("DISCAL_COMMIT_SHA", raising=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            result = get_current_commit_sha()
            assert result is None


# ── check_deploy ─────────────────────────────────────────────────────────────


class TestCheckDeploy:
    """Tests for check_deploy — deploy detection via stored commit hash."""

    def test_first_run_no_stored_hash(self, monkeypatch, tmp_path):
        """First run (no stored hash) records current SHA, returns None."""
        monkeypatch.setenv("DISCAL_COMMIT_SHA", "abc123")
        hash_path = tmp_path / ".deploy-hash"

        with patch("src.notify._get_deploy_hash_path", return_value=str(hash_path)):
            os.makedirs(tmp_path, exist_ok=True)
            result = check_deploy()
            # First run: no deploy detected
            assert result is None
            # SHA is stored
            assert hash_path.read_text().strip() == "abc123"

    def test_same_sha_returns_none(self, monkeypatch, tmp_path):
        """When stored SHA matches current, returns None."""
        monkeypatch.setenv("DISCAL_COMMIT_SHA", "abc123")
        hash_path = tmp_path / ".deploy-hash"
        hash_path.write_text("abc123")

        with patch("src.notify._get_deploy_hash_path", return_value=str(hash_path)):
            result = check_deploy()
            assert result is None

    def test_different_sha_detects_deploy(self, monkeypatch, tmp_path):
        """When stored SHA differs from current, returns (old, new)."""
        monkeypatch.setenv("DISCAL_COMMIT_SHA", "newsha456")
        hash_path = tmp_path / ".deploy-hash"
        hash_path.write_text("oldsha123")

        with patch("src.notify._get_deploy_hash_path", return_value=str(hash_path)):
            result = check_deploy()
            assert result == ("oldsha123", "newsha456")
            # New SHA is stored
            assert hash_path.read_text().strip() == "newsha456"

    def test_no_sha_available_returns_none(self, monkeypatch):
        """When no commit SHA can be determined, returns None."""
        monkeypatch.delenv("DISCAL_COMMIT_SHA", raising=False)
        with patch("src.notify.get_current_commit_sha", return_value=None):
            result = check_deploy()
            assert result is None
