"""Tests for src/db/ SQLite SettingsStore — user settings and digest configs."""

import threading

import pytest

from src.db.queries import SettingsStore


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def store():
    """Create a SettingsStore backed by an in-memory SQLite database.

    Each test gets a fresh, isolated database.
    """
    s = SettingsStore(":memory:")
    yield s
    s.close()


# ── user_settings CRUD ──────────────────────────────────────────────────────


class TestUserSettingsCRUD:
    """Tests for get / set / delete on user_settings."""

    def test_get_returns_none_for_missing_key(self, store):
        """get returns None when no value has been set."""
        assert store.get("user123", "timezone") is None

    def test_set_and_get_roundtrip(self, store):
        """set stores a value that get can retrieve."""
        store.set("user123", "timezone", "US/Eastern")
        assert store.get("user123", "timezone") == "US/Eastern"

    def test_set_overwrites_existing_value(self, store):
        """set replaces the existing value for the same key."""
        store.set("user123", "timezone", "US/Eastern")
        store.set("user123", "timezone", "US/Pacific")
        assert store.get("user123", "timezone") == "US/Pacific"

    def test_delete_removes_key(self, store):
        """delete removes a previously set key so get returns None."""
        store.set("user123", "email", "alice@example.com")
        store.delete("user123", "email")
        assert store.get("user123", "email") is None

    def test_delete_nonexistent_key_does_not_raise(self, store):
        """delete on a missing key is a no-op (no exception)."""
        store.delete("user123", "nonexistent")  # should not raise

    def test_different_users_have_independent_settings(self, store):
        """Settings are keyed by (discord_id, key) — users don't collide."""
        store.set("alice", "timezone", "US/Eastern")
        store.set("bob", "timezone", "US/Pacific")

        assert store.get("alice", "timezone") == "US/Eastern"
        assert store.get("bob", "timezone") == "US/Pacific"

    def test_different_keys_for_same_user_are_independent(self, store):
        """Multiple keys can be set for the same user without collision."""
        store.set("user123", "timezone", "US/Eastern")
        store.set("user123", "email", "alice@example.com")

        assert store.get("user123", "timezone") == "US/Eastern"
        assert store.get("user123", "email") == "alice@example.com"


# ── digest_configs CRUD ─────────────────────────────────────────────────────


class TestDigestConfigsCRUD:
    """Tests for set / get / delete on digest_configs."""

    def test_get_digest_configs_returns_empty_list_when_none_set(self, store):
        """get_digest_configs returns an empty list for a guild with no configs."""
        assert store.get_digest_configs("guild1") == []

    def test_set_and_get_digest_config(self, store):
        """A config set with set_digest_config is returned by get_digest_configs."""
        store.set_digest_config("guild1", "chan1", "daily", "09:00")

        configs = store.get_digest_configs("guild1")
        assert len(configs) == 1
        assert configs[0] == {
            "guild_id": "guild1",
            "channel_id": "chan1",
            "period": "daily",
            "time": "09:00",
        }

    def test_set_overwrites_existing_digest(self, store):
        """Setting the same (guild, channel, period) overwrites the existing row."""
        store.set_digest_config("guild1", "chan1", "daily", "09:00")
        store.set_digest_config("guild1", "chan1", "daily", "12:00")

        configs = store.get_digest_configs("guild1")
        assert len(configs) == 1
        assert configs[0]["time"] == "12:00"

    def test_multiple_digests_per_guild(self, store):
        """A guild can have multiple digest configs (different periods/channels)."""
        store.set_digest_config("guild1", "chan1", "daily", "09:00")
        store.set_digest_config("guild1", "chan2", "weekly", "10:00")
        store.set_digest_config("guild1", "chan1", "monthly", "08:00")

        configs = store.get_digest_configs("guild1")
        assert len(configs) == 3

    def test_delete_digest_config_removes_row(self, store):
        """delete_digest_config removes the matching row."""
        store.set_digest_config("guild1", "chan1", "daily", "09:00")
        store.set_digest_config("guild1", "chan1", "weekly", "10:00")

        store.delete_digest_config("guild1", "chan1", "daily")

        configs = store.get_digest_configs("guild1")
        assert len(configs) == 1
        assert configs[0]["period"] == "weekly"

    def test_delete_nonexistent_digest_does_not_raise(self, store):
        """delete_digest_config on a missing row is a no-op."""
        store.delete_digest_config("guild1", "chan1", "daily")  # should not raise

    def test_different_guilds_have_independent_digests(self, store):
        """Digest configs are scoped to guild_id."""
        store.set_digest_config("guild1", "chan1", "daily", "09:00")
        store.set_digest_config("guild2", "chanX", "daily", "07:00")

        assert len(store.get_digest_configs("guild1")) == 1
        assert len(store.get_digest_configs("guild2")) == 1
        assert store.get_digest_configs("guild3") == []


# ── Migration / Idempotency ─────────────────────────────────────────────────


class TestMigration:
    """Tests for schema initialization and idempotency."""

    def test_init_is_idempotent(self, store):
        """Running init twice does not raise — IF NOT EXISTS guards the DDL."""
        # The fixture already calls init_db once.
        # Import and call it again to verify idempotency.
        from src.db.schema import init_db

        init_db(store._conn)  # should not raise


# ── Concurrent Access Safety ────────────────────────────────────────────────


class TestConcurrency:
    """Tests for thread safety under concurrent access."""

    def test_concurrent_get_and_set(self, store):
        """Multiple threads can read and write without errors."""
        errors = []
        iterations = 50

        def worker(thread_id: int):
            try:
                for i in range(iterations):
                    key = f"key_{thread_id}_{i}"
                    store.set("user1", key, f"value_{thread_id}_{i}")
                    result = store.get("user1", key)
                    assert result == f"value_{thread_id}_{i}"
            except Exception as exc:
                errors.append((thread_id, exc))

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(4)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
