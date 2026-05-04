"""Tests for DiscalClient command tree setup — guards against silent sync failure."""

import logging
from unittest.mock import AsyncMock, patch

import discord
import pytest

# Import bot module to trigger side-effect command registration before the test
# runs (imports in bot.py register commands on the `cal` group).
import src.bot  # noqa: F401
from src.bot import DiscalClient


@pytest.mark.asyncio
async def test_setup_hook_populates_guild_commands(monkeypatch):
    """After setup_hook, tree.get_commands(guild=...) is non-empty.

    Verifies that cal is registered directly on the guild tree (not via
    copy_global_to) and that the global tree ends up empty after the purge sync.
    """
    test_guild_id = "999999999999999999"

    # 1 ── Configure environment for guild-scoped sync ──────────────────────
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    monkeypatch.setenv("DISCORD_GUILD_ID", test_guild_id)
    monkeypatch.setenv("DISCORD_TOKEN", "fake-token")
    monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)

    # 2 ── Create client ────────────────────────────────────────────────────
    client = DiscalClient(db_path=":memory:")
    guild = discord.Object(id=int(test_guild_id))

    # 3 ── Spy on add_command to capture call args ──────────────────────────
    with patch.object(client.tree, "add_command", wraps=client.tree.add_command) as spy_add:
        with patch.object(client.tree, "sync", new_callable=AsyncMock) as mock_sync:
            await client.setup_hook()

    # 4 ── Assertions ───────────────────────────────────────────────────────
    # a. add_command was called with guild= kwarg (direct guild registration)
    guild_calls = [c for c in spy_add.call_args_list if c.kwargs.get("guild") is not None]
    assert len(guild_calls) >= 1, (
        "add_command must be called with guild= kwarg — "
        "cal should be registered directly on the guild tree"
    )
    cal_call = [c for c in guild_calls if c.args[0].name == "cal"]
    assert len(cal_call) == 1, "cal must be registered on a guild tree"
    assert cal_call[0].kwargs.get("override") is True, (
        "add_command should use override=True for guild registration"
    )

    # b. sync was called twice: once for guild, once for global purge
    assert mock_sync.call_count == 2, (
        f"Expected 2 sync calls (guild + global purge), got {mock_sync.call_count}"
    )

    # c. first call is guild sync
    first_call_kwargs = mock_sync.call_args_list[0].kwargs
    assert first_call_kwargs.get("guild") is not None, (
        "First sync must be guild-scoped"
    )
    assert first_call_kwargs["guild"].id == int(test_guild_id)

    # d. second call is global purge (no guild kwarg)
    second_call_kwargs = mock_sync.call_args_list[1].kwargs
    assert second_call_kwargs.get("guild") is None, (
        "Second sync must be global (no guild kwarg) to purge stale global commands"
    )

    # e. guild has commands registered locally
    guild_cmds = client.tree.get_commands(guild=guild)
    assert len(guild_cmds) > 0, (
        "tree.get_commands(guild=...) returned 0 — commands were never registered "
        "on guild scope."
    )

    # f. global tree is empty (commands are guild-only)
    global_cmds = client.tree.get_commands(guild=None)
    assert len(global_cmds) == 0, (
        f"tree.get_commands(guild=None) should be empty after setup_hook, "
        f"got {[c.name for c in global_cmds]}"
    )

    # g. the top-level group is 'cal'
    assert guild_cmds[0].name == "cal"

    # h. subcommands we expect to exist (catches accidental removal)
    sub_names = {cmd.name for cmd in guild_cmds[0].walk_commands()}
    required = {"create", "invite", "settings", "reminders", "today", "ping"}
    missing = required - sub_names
    assert not missing, f"Missing top-level subcommands: {missing}"


@pytest.mark.asyncio
async def test_setup_hook_exits_when_guild_id_missing(monkeypatch):
    """setup_hook logs critical error and exits when DISCORD_GUILD_ID is unset."""
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    monkeypatch.setenv("DISCORD_TOKEN", "fake-token")
    monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)

    client = DiscalClient(db_path=":memory:")

    with patch.object(logging.getLogger("src.bot"), "critical") as mock_critical:
        with pytest.raises(SystemExit) as exc_info:
            await client.setup_hook()

    assert exc_info.value.code == 1
    mock_critical.assert_called_once()
    assert "DISCORD_GUILD_ID" in mock_critical.call_args[0][0]


@pytest.mark.asyncio
async def test_setup_hook_exits_when_guild_id_empty(monkeypatch):
    """setup_hook exits when DISCORD_GUILD_ID is set to an empty string."""
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "111111111111111111")
    monkeypatch.setenv("DISCORD_GUILD_ID", "")
    monkeypatch.setenv("DISCORD_TOKEN", "fake-token")
    monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)

    client = DiscalClient(db_path=":memory:")

    with pytest.raises(SystemExit) as exc_info:
        await client.setup_hook()

    assert exc_info.value.code == 1
