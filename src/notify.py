"""Notification dispatch for bot lifecycle events.

Sends messages to configurable Discord channels and/or users (DM) when
bot lifecycle events occur (restart, shutdown, error, deploy).
Configured via DISCORD_NOTIFY_TARGETS and DISCORD_NOTIFY_EVENTS env vars.

When ``DISCORD_ENABLE_MESSAGE_CONTENT`` is not ``"true"``, user-DM targets
are skipped but channel targets still receive notifications.
"""

import logging
import os
import subprocess
from typing import Any

import discord

logger = logging.getLogger(__name__)

_VALID_EVENTS = {"restart", "shutdown", "error", "deploy"}
_DEFAULT_EVENTS = {"restart", "shutdown", "error"}


# ── Config parsing ───────────────────────────────────────────────────────────


def parse_notify_targets(raw: str | None = None) -> list[tuple[str, int]]:
    """Parse DISCORD_NOTIFY_TARGETS into list of ``(type, id)`` tuples.

    *type* is ``"user"`` for ``u:`` prefix or ``"channel"`` for ``c:``.
    Invalid entries are skipped with a warning.
    """
    if raw is None:
        raw = os.environ.get("DISCORD_NOTIFY_TARGETS", "")
    targets: list[tuple[str, int]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("u:"):
            try:
                targets.append(("user", int(part[2:].strip())))
            except ValueError:
                logger.warning("Invalid notify target user ID: %s", part)
        elif part.startswith("c:"):
            try:
                targets.append(("channel", int(part[2:].strip())))
            except ValueError:
                logger.warning("Invalid notify target channel ID: %s", part)
        else:
            logger.warning(
                "Invalid notify target format (use u:ID or c:ID): %s", part
            )
    return targets


def parse_notify_events(raw: str | None = None) -> set[str]:
    """Parse DISCORD_NOTIFY_EVENTS into a set of event names.

    Default if unset, empty, or all-invalid: ``{"restart", "shutdown", "error"}``.
    """
    if raw is None:
        raw = os.environ.get("DISCORD_NOTIFY_EVENTS", "")
    if not raw.strip():
        return _DEFAULT_EVENTS.copy()
    events: set[str] = set()
    for part in raw.split(","):
        part = part.strip().lower()
        if part in _VALID_EVENTS:
            events.add(part)
        elif part:
            logger.warning("Unknown notify event: %s", part)
    if not events:
        return _DEFAULT_EVENTS.copy()
    return events


# ── Message builders ─────────────────────────────────────────────────────────


def _build_message(event: str, **kwargs: Any) -> str:
    """Build the notification message for a given event type."""
    ts = kwargs.get("timestamp", "")

    if event == "restart":
        sha = kwargs.get("sha", "")
        if sha:
            return f"🟢 Discal restarted at {ts} (commit: {sha})"
        return f"🟢 Discal restarted at {ts}"

    if event == "shutdown":
        return f"🔴 Discal shutting down at {ts}"

    if event == "error":
        handler = kwargs.get("handler", "unknown")
        message = kwargs.get("message", "unknown error")
        return f"⚠️ Error in {handler}: {message}"

    if event == "deploy":
        old_sha = kwargs.get("old_sha", "unknown")[:7]
        new_sha = kwargs.get("new_sha", "unknown")[:7]
        return f"🚀 Deployed {old_sha} → {new_sha}"

    return f"Notification: {event}"


# ── Dispatch ─────────────────────────────────────────────────────────────────


async def _send_to_target(
    client: Any, target_type: str, target_id: int, message: str
) -> None:
    """Send a message to a single notification target, catching errors.

    On failure (not found, forbidden, HTTP error) logs a warning and
    continues — a single unreachable target never blocks the rest.
    """
    try:
        if target_type == "user":
            user = await client.fetch_user(target_id)
            await user.send(message)
        else:
            channel = client.get_channel(target_id)
            if channel is None:
                channel = await client.fetch_channel(target_id)
            await channel.send(message)
    except discord.NotFound:
        logger.warning(
            "Notify target not found: %s:%d", target_type, target_id
        )
    except discord.Forbidden:
        logger.warning(
            "Notify target forbidden (DMs blocked or no channel access): %s:%d",
            target_type,
            target_id,
        )
    except discord.HTTPException as exc:
        logger.warning(
            "Notify target HTTP error %s:%d: %s", target_type, target_id, exc
        )


async def notify(client: Any, event: str, **kwargs: Any) -> None:
    """Send an event notification to all configured targets if enabled.

    Args:
        client: The Discord client (must have ``fetch_user``, ``get_channel``,
            ``fetch_channel``).
        event: Event name — ``restart``, ``shutdown``, ``error``, or ``deploy``.
        **kwargs: Additional data passed through to ``_build_message``
            (e.g. ``sha``, ``timestamp``, ``handler``, ``message``,
            ``old_sha``, ``new_sha``).
    """
    targets = parse_notify_targets()
    if not targets:
        return

    enabled_events = parse_notify_events()
    if event not in enabled_events:
        return

    message = _build_message(event, **kwargs)

    # When message_content is not enabled, skip user DM targets.
    # Channel messages don't require the message_content intent.
    message_content_enabled = getattr(client, "_message_content_enabled", True)

    for target_type, target_id in targets:
        if target_type == "user" and not message_content_enabled:
            continue
        await _send_to_target(client, target_type, target_id, message)


# ── Deploy hash tracking ─────────────────────────────────────────────────────


def _get_deploy_hash_path() -> str:
    """Return the filesystem path to the stored deploy-hash file."""
    return os.path.join("data", ".deploy-hash")


def get_current_commit_sha() -> str | None:
    """Return the current commit SHA from env or git, or ``None`` if unavailable.

    Prefers ``DISCAL_COMMIT_SHA`` env var (set during deploy) over
    ``git rev-parse HEAD`` (local dev fallback).
    """
    sha = os.environ.get("DISCAL_COMMIT_SHA", "")
    if sha:
        return sha

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass

    return None


def check_deploy() -> tuple[str, str] | None:
    """Compare the current commit SHA against the stored hash from last run.

    Returns ``(old_sha, new_sha)`` when a deploy is detected, or ``None``
    when the SHA hasn't changed or is unavailable (including first run).
    Stores the new SHA for future comparison.
    """
    new_sha = get_current_commit_sha()
    if not new_sha:
        return None

    hash_path = _get_deploy_hash_path()
    old_sha: str | None = None
    if os.path.exists(hash_path):
        try:
            with open(hash_path) as f:
                old_sha = f.read().strip()
        except OSError:
            pass

    if old_sha and old_sha == new_sha:
        return None

    # Store new hash
    os.makedirs(os.path.dirname(hash_path), exist_ok=True)
    try:
        with open(hash_path, "w") as f:
            f.write(new_sha)
    except OSError:
        pass

    if old_sha:
        return old_sha, new_sha
    return None


async def check_and_notify_deploy(client: Any) -> None:
    """Check for a deploy and send a notification if one is detected."""
    result = check_deploy()
    if result is None:
        return
    old_sha, new_sha = result
    await notify(client, "deploy", old_sha=old_sha, new_sha=new_sha)
