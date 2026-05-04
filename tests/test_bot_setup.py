"""Tests for DiscalClient command tree setup — guards against silent sync failure."""

import os
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

    Regression test: a missing ``copy_global_to`` call leaves the guild with
    zero commands, making all slash commands invisible in Discord.  This test
    would have caught the 0-commands bug before it reached production.
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

    # 3 ── Mock the tree sync so it never hits Discord's API ────────────────
    with patch.object(client.tree, "sync", new_callable=AsyncMock) as mock_sync:
        await client.setup_hook()

    # 4 ── Assertions ───────────────────────────────────────────────────────
    # a. sync was called with the guild
    mock_sync.assert_called_once()
    call_kwargs = mock_sync.call_args.kwargs
    assert call_kwargs.get("guild") is not None, (
        "sync must be called with guild=... — global sync doesn't push guild commands"
    )
    assert call_kwargs["guild"].id == int(test_guild_id)

    # b. guild has commands registered locally
    guild_cmds = client.tree.get_commands(guild=guild)
    assert len(guild_cmds) > 0, (
        "tree.get_commands(guild=...) returned 0 — commands were never copied "
        "to guild scope.  Ensure copy_global_to(guild=guild) runs before sync."
    )

    # c. the top-level group is 'cal'
    assert guild_cmds[0].name == "cal"

    # d. subcommands we expect to exist (catches accidental removal)
    sub_names = {cmd.name for cmd in guild_cmds[0].walk_commands()}
    required = {"create", "invite", "settings", "reminders", "today", "ping"}
    missing = required - sub_names
    assert not missing, f"Missing top-level subcommands: {missing}"
