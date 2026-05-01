"""SettingsStore — per-user settings and digest config persistence.

Backed by SQLite.  Tables are created automatically on first use.
Uses WAL mode and a threading lock for safe concurrent access.
"""

import os
import sqlite3
import threading
from typing import Optional

from src.db.schema import init_db


class SettingsStore:
    """Key-value store for per-user settings and per-guild digest configs.

    Args:
        db_path: Path to the SQLite database file.  Use ``":memory:"`` for
            an in-memory database (tests) or a real path for production.
    """

    def __init__(self, db_path: str = "data/discal.db") -> None:
        # Create parent directory if needed (e.g. local dev without Docker).
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        init_db(self._conn)

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    # ── user_settings ──────────────────────────────────────────────────

    def get(self, discord_id: str, key: str) -> Optional[str]:
        """Return the value for *discord_id* and *key*, or ``None`` if not set."""
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM user_settings WHERE discord_id = ? AND key = ?",
                (discord_id, key),
            ).fetchone()
            return row["value"] if row else None

    def set(self, discord_id: str, key: str, value: str) -> None:
        """Store *value* for *discord_id* and *key*.

        Overwrites any existing value (INSERT OR REPLACE).
        """
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO user_settings (discord_id, key, value) "
                "VALUES (?, ?, ?)",
                (discord_id, key, value),
            )
            self._conn.commit()

    def delete(self, discord_id: str, key: str) -> None:
        """Remove the setting for *discord_id* and *key*.  No-op if not set."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM user_settings WHERE discord_id = ? AND key = ?",
                (discord_id, key),
            )
            self._conn.commit()

    # ── digest_configs ─────────────────────────────────────────────────

    def get_digest_configs(self, guild_id: str) -> list[dict]:
        """Return all digest configs for *guild_id* as a list of dicts.

        Each dict has keys ``guild_id``, ``channel_id``, ``period``, ``time``.
        Returns an empty list when no configs exist for the guild.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT guild_id, channel_id, period, time "
                "FROM digest_configs WHERE guild_id = ?",
                (guild_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def set_digest_config(self, guild_id: str, channel_id: str,
                          period: str, time: str) -> None:
        """Create or update a digest config.

        The composite key is *(guild_id, channel_id, period)* — setting the
        same triple again overwrites the existing row.
        """
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO digest_configs "
                "(guild_id, channel_id, period, time) VALUES (?, ?, ?, ?)",
                (guild_id, channel_id, period, time),
            )
            self._conn.commit()

    def delete_digest_config(self, guild_id: str, channel_id: str,
                             period: str) -> None:
        """Remove a single digest config.  No-op if it does not exist."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM digest_configs "
                "WHERE guild_id = ? AND channel_id = ? AND period = ?",
                (guild_id, channel_id, period),
            )
            self._conn.commit()
