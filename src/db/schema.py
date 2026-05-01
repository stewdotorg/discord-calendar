"""SQLite schema definitions and initialization for Discal."""

import sqlite3

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS user_settings (
    discord_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (discord_id, key)
);

CREATE TABLE IF NOT EXISTS digest_configs (
    guild_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    period TEXT NOT NULL,
    time TEXT NOT NULL,
    PRIMARY KEY (guild_id, channel_id, period)
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Run schema migrations on the given connection.

    Safe to call multiple times — uses IF NOT EXISTS for idempotency.
    Enables WAL journal mode for concurrent read safety.
    """
    conn.executescript(_SCHEMA_SQL)
    conn.execute("PRAGMA journal_mode=WAL")
