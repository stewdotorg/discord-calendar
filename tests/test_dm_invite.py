"""Tests for DM invite flow: pending_invites table, DM sending, and reply handling."""

import datetime
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from src.db.queries import SettingsStore


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def store():
    """Create a SettingsStore backed by an in-memory SQLite database."""
    s = SettingsStore(":memory:")
    yield s
    s.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  db: pending_invites table operations
# ═══════════════════════════════════════════════════════════════════════════════


class TestPendingInvitesDB:
    """Tests for pending_invites CRUD operations."""

    def test_insert_and_get_pending_invite(self, store):
        """insert_pending_invite stores a record; get_pending_invite retrieves it."""
        now = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now.isoformat()
        store.insert_pending_invite("user1", "evt_abc", "inviter1", now_iso)

        result = store.get_pending_invite("user1")
        assert result is not None
        assert result["user_id"] == "user1"
        assert result["event_id"] == "evt_abc"
        assert result["inviter_id"] == "inviter1"
        assert result["created_at"] == now_iso

    def test_get_pending_invite_returns_none_for_missing(self, store):
        """get_pending_invite returns None when no pending invite exists."""
        assert store.get_pending_invite("nonexistent") is None

    def test_insert_overwrites_existing_pending_invite(self, store):
        """Re-inviting a user to a different event overwrites the old pending."""
        now = datetime.datetime.now(datetime.timezone.utc)
        store.insert_pending_invite("user1", "evt_old", "inviter1", now.isoformat())
        store.insert_pending_invite("user1", "evt_new", "inviter2", (now + datetime.timedelta(hours=1)).isoformat())

        result = store.get_pending_invite("user1")
        assert result["event_id"] == "evt_new"
        assert result["inviter_id"] == "inviter2"

    def test_delete_pending_invite(self, store):
        """delete_pending_invite removes the record."""
        store.insert_pending_invite("user1", "evt_abc", "inviter1", datetime.datetime.now(datetime.timezone.utc).isoformat())
        store.delete_pending_invite("user1")
        assert store.get_pending_invite("user1") is None

    def test_delete_nonexistent_pending_invite_does_not_raise(self, store):
        """delete_pending_invite on a missing record is a no-op."""
        store.delete_pending_invite("nonexistent")  # should not raise

    def test_cleanup_expired_invites(self, store):
        """cleanup_expired_invites removes entries older than 7 days."""
        ref = datetime.datetime(2026, 5, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)

        # fresh invite: 6 days ago — should stay
        fresh = (ref - datetime.timedelta(days=6)).isoformat()
        # old invite: 8 days ago — should be cleaned
        old = (ref - datetime.timedelta(days=8)).isoformat()

        store.insert_pending_invite("user_fresh", "evt1", "inviter1", fresh)
        store.insert_pending_invite("user_old", "evt2", "inviter2", old)

        store.cleanup_expired_invites(now=ref)

        assert store.get_pending_invite("user_fresh", now=ref) is not None
        assert store.get_pending_invite("user_old") is None

    def test_get_pending_invite_skips_expired(self, store):
        """get_pending_invite returns None for an expired invite (older than 7 days)."""
        ref = datetime.datetime(2026, 5, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        old = (ref - datetime.timedelta(days=8)).isoformat()

        store.insert_pending_invite("user_old", "evt2", "inviter2", old)

        result = store.get_pending_invite("user_old", now=ref)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
#  DM reply handling via on_message
# ═══════════════════════════════════════════════════════════════════════════════


class TestDMReplyHandling:
    """Tests for the on_message handler that processes DM replies."""

    @pytest.mark.asyncio
    async def test_valid_email_reply_saves_email_and_adds_attendee(self):
        """When a user with a pending invite replies with a valid email,
        the email is saved, they're added to the event, and confirmed."""
        from src.dm_handler import handle_dm_reply

        message = MagicMock()
        message.content = "me@example.com"
        message.channel = MagicMock()
        message.channel.send = AsyncMock()
        message.author = MagicMock()
        message.author.id = 12345
        message.guild = None  # DM

        # Mock settings store
        mock_settings = MagicMock()
        # No email stored initially
        mock_settings.get.return_value = None
        # Pending invite exists
        mock_settings.get_pending_invite.return_value = {
            "user_id": "12345",
            "event_id": "evt_test",
            "inviter_id": "99999",
            "created_at": "2026-05-01T00:00:00+00:00",
        }

        # Mock calendar
        mock_calendar = MagicMock()
        mock_calendar.get_event.return_value = {
            "id": "evt_test",
            "summary": "Team Sync",
            "start": {"dateTime": "2026-05-05T18:00:00+00:00"},
            "htmlLink": "https://calendar.google.com/event?eid=evt_test",
        }

        result = await handle_dm_reply(message, mock_settings, mock_calendar)
        assert result is True

        # Email should be saved
        mock_settings.set.assert_called_once_with("12345", "email", "me@example.com")
        # Attendee should be added
        mock_calendar.add_attendees.assert_called_once_with(
            "evt_test", ["me@example.com"]
        )
        # User should be confirmed
        message.channel.send.assert_called_once()
        sent = message.channel.send.call_args.args[0]
        assert "Team Sync" in sent
        assert "✅" in sent
        # Pending invite should be deleted
        mock_settings.delete_pending_invite.assert_called_once_with("12345")

    @pytest.mark.asyncio
    async def test_user_already_has_email_uses_stored(self):
        """When a user already has an email stored, the bot uses the stored
        email instead of the reply text, and doesn't overwrite."""
        from src.dm_handler import handle_dm_reply

        message = MagicMock()
        message.content = "some-other@example.com"
        message.channel = MagicMock()
        message.channel.send = AsyncMock()
        message.author = MagicMock()
        message.author.id = 12345
        message.guild = None

        mock_settings = MagicMock()
        mock_settings.get_pending_invite.return_value = {
            "user_id": "12345",
            "event_id": "evt_test",
            "inviter_id": "99999",
            "created_at": "2026-05-01T00:00:00+00:00",
        }
        # User already has a stored email
        mock_settings.get.return_value = "existing@example.com"

        mock_calendar = MagicMock()
        mock_calendar.get_event.return_value = {
            "id": "evt_test",
            "summary": "Team Sync",
            "start": {"dateTime": "2026-05-05T18:00:00+00:00"},
            "htmlLink": "https://calendar.google.com/event?eid=evt_test",
        }

        result = await handle_dm_reply(message, mock_settings, mock_calendar)
        assert result is True

        # Should NOT overwrite stored email
        mock_settings.set.assert_not_called()
        # Should use existing email as attendee
        mock_calendar.add_attendees.assert_called_once_with(
            "evt_test", ["existing@example.com"]
        )
        # Should confirm
        message.channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_email_reply_shows_error(self):
        """When a user replies with an invalid email (has @ but invalid format),
        the bot replies with an error and the pending invite stays."""
        from src.dm_handler import handle_dm_reply

        message = MagicMock()
        message.content = "user@nodot"
        message.channel = MagicMock()
        message.channel.send = AsyncMock()
        message.author = MagicMock()
        message.author.id = 12345
        message.guild = None

        mock_settings = MagicMock()
        mock_settings.get.return_value = None
        mock_settings.get_pending_invite.return_value = {
            "user_id": "12345",
            "event_id": "evt_test",
            "inviter_id": "99999",
            "created_at": "2026-05-01T00:00:00+00:00",
        }

        mock_calendar = MagicMock()

        result = await handle_dm_reply(message, mock_settings, mock_calendar)
        assert result is True

        # Should NOT save email
        mock_settings.set.assert_not_called()
        # Should NOT add attendee
        mock_calendar.add_attendees.assert_not_called()
        # Should send error message
        message.channel.send.assert_called_once()
        sent = message.channel.send.call_args.args[0]
        assert "valid email" in sent.lower() or "doesn't look" in sent.lower()
        # Pending invite should NOT be deleted
        mock_settings.delete_pending_invite.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_email_reply_ignored(self):
        """When a user with a pending invite replies with something that
        doesn't look like an email attempt, the bot ignores it silently."""
        from src.dm_handler import handle_dm_reply

        message = MagicMock()
        message.content = "no thanks"
        message.channel = MagicMock()
        message.channel.send = AsyncMock()
        message.author = MagicMock()
        message.author.id = 12345
        message.guild = None

        mock_settings = MagicMock()
        mock_settings.get.return_value = None
        mock_settings.get_pending_invite.return_value = {
            "user_id": "12345",
            "event_id": "evt_test",
            "inviter_id": "99999",
            "created_at": "2026-05-01T00:00:00+00:00",
        }

        mock_calendar = MagicMock()

        result = await handle_dm_reply(message, mock_settings, mock_calendar)
        assert result is True

        # Nothing should happen
        mock_settings.set.assert_not_called()
        mock_calendar.add_attendees.assert_not_called()
        message.channel.send.assert_not_called()
        mock_settings.delete_pending_invite.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_pending_invite_ignored(self):
        """When a user has no pending invite, DM is ignored."""
        from src.dm_handler import handle_dm_reply

        message = MagicMock()
        message.content = "me@example.com"
        message.channel = MagicMock()
        message.channel.send = AsyncMock()
        message.author = MagicMock()
        message.author.id = 12345
        message.guild = None

        mock_settings = MagicMock()
        mock_settings.get.return_value = None
        mock_settings.get_pending_invite.return_value = None

        mock_calendar = MagicMock()

        result = await handle_dm_reply(message, mock_settings, mock_calendar)
        assert result is False

        # Nothing should happen
        mock_calendar.get_event.assert_not_called()
        message.channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_event_deleted_shows_error(self):
        """When the event has been deleted by the time the user replies,
        the bot replies with an error and drops the pending invite."""
        from src.dm_handler import handle_dm_reply

        message = MagicMock()
        message.content = "me@example.com"
        message.channel = MagicMock()
        message.channel.send = AsyncMock()
        message.author = MagicMock()
        message.author.id = 12345
        message.guild = None

        mock_settings = MagicMock()
        mock_settings.get.return_value = None
        mock_settings.get_pending_invite.return_value = {
            "user_id": "12345",
            "event_id": "evt_deleted",
            "inviter_id": "99999",
            "created_at": "2026-05-01T00:00:00+00:00",
        }

        mock_calendar = MagicMock()
        http_resp = MagicMock()
        http_resp.status = 404
        mock_calendar.get_event.side_effect = HttpError(
            http_resp, b'{"error": {"message": "Not Found"}}'
        )

        result = await handle_dm_reply(message, mock_settings, mock_calendar)
        assert result is True

        # Should send error about event not existing
        message.channel.send.assert_called_once()
        sent = message.channel.send.call_args.args[0]
        assert "no longer exists" in sent.lower()
        # Pending invite should be dropped
        mock_settings.delete_pending_invite.assert_called_once_with("12345")

    @pytest.mark.asyncio
    async def test_add_attendees_error_handled(self):
        """When add_attendees fails, the error is caught and user gets feedback."""
        from src.dm_handler import handle_dm_reply

        message = MagicMock()
        message.content = "me@example.com"
        message.channel = MagicMock()
        message.channel.send = AsyncMock()
        message.author = MagicMock()
        message.author.id = 12345
        message.guild = None

        mock_settings = MagicMock()
        mock_settings.get.return_value = None
        mock_settings.get_pending_invite.return_value = {
            "user_id": "12345",
            "event_id": "evt_test",
            "inviter_id": "99999",
            "created_at": "2026-05-01T00:00:00+00:00",
        }

        mock_calendar = MagicMock()
        mock_calendar.get_event.return_value = {
            "id": "evt_test",
            "summary": "Team Sync",
            "start": {"dateTime": "2026-05-05T18:00:00+00:00"},
            "htmlLink": "https://calendar.google.com/event?eid=evt_test",
        }
        http_resp = MagicMock()
        http_resp.status = 403
        mock_calendar.add_attendees.side_effect = HttpError(
            http_resp, b'{"error": {"message": "Forbidden"}}'
        )

        result = await handle_dm_reply(message, mock_settings, mock_calendar)
        assert result is True

        # Email should be saved
        mock_settings.set.assert_called_once()
        # add_attendees was attempted
        mock_calendar.add_attendees.assert_called_once()
        # Error message sent
        message.channel.send.assert_called_once()
        sent = message.channel.send.call_args.args[0]
        assert "couldn" in sent.lower()
        # Pending invite should be deleted even on error
        mock_settings.delete_pending_invite.assert_called_once_with("12345")


# ═══════════════════════════════════════════════════════════════════════════════
#  DM sending from commands (create / invite)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDMInviteSending:
    """Tests for DM sending when invite fails for unresolvable mentions."""

    @pytest.mark.asyncio
    async def test_send_pending_invite_dm(self):
        """send_pending_invite_dm sends a DM to the unresolvable user and
        stores a pending invite."""
        from src.dm_handler import send_pending_invite_dm

        mock_user = AsyncMock()
        mock_user.id = 12345

        mock_settings = MagicMock()

        result = await send_pending_invite_dm(
            user=mock_user,
            event_id="evt_test",
            event_title="Team Sync",
            event_start="2026-05-05T18:00:00+00:00",
            event_html_link="https://calendar.google.com/event?eid=evt_test",
            inviter_name="stew",
            inviter_id="99999",
            settings_store=mock_settings,
        )
        assert result is True

        # DM should be sent
        mock_user.send.assert_called_once()
        sent = mock_user.send.call_args.args[0]
        assert "stew" in sent
        assert "Team Sync" in sent
        assert "Reply with your email" in sent

        # Pending invite should be stored
        mock_settings.insert_pending_invite.assert_called_once()
        call_args = mock_settings.insert_pending_invite.call_args
        assert call_args.args[0] == "12345"
        assert call_args.args[1] == "evt_test"
        assert call_args.args[2] == "99999"

    @pytest.mark.asyncio
    async def test_send_pending_invite_dm_handles_dm_disabled(self):
        """When the user has DMs disabled, the bot logs a warning and does
        NOT try to send the DM."""
        from src.dm_handler import send_pending_invite_dm

        mock_user = AsyncMock()
        mock_user.id = 12345
        # Make send raise Forbidden (DMs disabled)
        import discord
        mock_user.send.side_effect = discord.Forbidden(
            MagicMock(), "Cannot send messages to this user"
        )

        mock_settings = MagicMock()

        with patch.object(logging.getLogger("src.dm_handler"), "warning") as mock_warn:
            result = await send_pending_invite_dm(
                user=mock_user,
                event_id="evt_test",
                event_title="Team Sync",
                event_start="2026-05-05T18:00:00+00:00",
                event_html_link="https://calendar.google.com/event?eid=evt_test",
                inviter_name="stew",
                inviter_id="99999",
                settings_store=mock_settings,
            )
            assert result is False
            mock_warn.assert_called_once()

        # Should NOT store a pending invite if DM fails
        mock_settings.insert_pending_invite.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_with_unresolvable_mention_dms_user(self):
        """When /cal create has an unresolvable @mention, the bot DMs that
        user with the invite prompt."""
        from src.commands.create import create

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 999
        interaction.user.name = "stew"
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.edit_original_response = AsyncMock()
        # Override send on the interaction user to allow DM lookup
        interaction.user.send = AsyncMock()

        # Mock the calendar
        mock_calendar = MagicMock()
        mock_calendar.create_event.return_value = {
            "id": "evt_create",
            "htmlLink": "https://calendar.google.com/event?eid=evt_create",
        }
        interaction.client.calendar = mock_calendar

        # Mock settings: no email for the mentioned user
        mock_settings = MagicMock()
        mock_settings.get.return_value = None  # no email stored
        interaction.client.settings = mock_settings

        # Mock the client to allow fetching the mentioned user
        mock_client = MagicMock()
        mock_client.fetch_user = AsyncMock()
        mock_target_user = AsyncMock()
        mock_target_user.id = 111111
        mock_target_user.send = AsyncMock()
        mock_client.fetch_user.return_value = mock_target_user
        interaction.client.fetch_user = mock_client.fetch_user

        await create.callback(
            interaction,
            title="Team Sync",
            when="2026-05-01 14:00",
            duration=30,
            description=None,
            invite="<@111111>",
        )

        # Event should still be created
        mock_calendar.create_event.assert_called_once()

        # User should be fetched and DM'd
        mock_client.fetch_user.assert_called_once_with(111111)
        mock_target_user.send.assert_called_once()

        # Pending invite should be stored
        mock_settings.insert_pending_invite.assert_called_once_with(
            "111111", "evt_create", "999", mock_settings.insert_pending_invite.call_args.args[3]
        )

        # Warning should still appear in response
        response = interaction.edit_original_response.call_args.kwargs["content"]
        assert "⚠️" in response

    @pytest.mark.asyncio
    async def test_rsvp_invite_unresolvable_mention_dms_user(self):
        """When /cal invite has an unresolvable @mention and valid recipients,
        the unresolvable user gets a DM."""
        from src.commands.rsvp import invite

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 999
        interaction.user.name = "stew"
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.edit_original_response = AsyncMock()

        # Mock calendar
        mock_calendar = MagicMock()
        mock_calendar.add_attendees.return_value = [
            {"email": "good@example.com", "responseStatus": "needsAction"},
        ]
        mock_calendar.get_event.return_value = {
            "id": "evt_inv",
            "summary": "Team Sync",
            "start": {"dateTime": "2026-05-05T18:00:00+00:00"},
            "htmlLink": "https://calendar.google.com/event?eid=evt_inv",
        }
        interaction.client.calendar = mock_calendar

        # Mock settings: mention has no email
        mock_settings = MagicMock()
        mock_settings.get.return_value = None
        interaction.client.settings = mock_settings

        # Mock client.fetch_user for DM
        mock_client = MagicMock()
        mock_client.fetch_user = AsyncMock()
        mock_target_user = AsyncMock()
        mock_target_user.id = 111111
        mock_target_user.send = AsyncMock()
        mock_client.fetch_user.return_value = mock_target_user
        interaction.client.fetch_user = mock_client.fetch_user

        await invite.callback(
            interaction,
            event_id="evt_inv",
            people="good@example.com, <@111111>",
        )

        # Valid email should still be added
        mock_calendar.add_attendees.assert_called_once_with(
            "evt_inv", ["good@example.com"]
        )

        # Unresolvable user should get a DM
        mock_client.fetch_user.assert_called_once_with(111111)
        mock_target_user.send.assert_called_once()

        # Pending invite should be stored
        mock_settings.insert_pending_invite.assert_called_once()

        # Response should include warning
        content = interaction.edit_original_response.call_args.kwargs["content"]
        assert "⚠️" in content


# ═══════════════════════════════════════════════════════════════════════════════
#  resolve_mentions returns unresolvable IDs
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveMentions:
    """Tests for resolve_mentions returning unresolvable discord IDs."""

    def test_returns_unresolvable_ids(self):
        """resolve_mentions returns discord IDs of unresolvable mentions
        alongside resolved emails and warnings."""
        from src.utils import resolve_mentions

        mock_settings = MagicMock()
        mock_settings.get.return_value = None  # no email for anyone

        resolved, warnings, unresolvable_ids = resolve_mentions(
            ["<@111>", "<@222>", "good@example.com"],
            mock_settings,
        )

        assert resolved == ["good@example.com"]
        assert len(warnings) == 2
        assert "111" in warnings[0]
        assert "222" in warnings[1]
        assert unresolvable_ids == set(["111", "222"])

    def test_returns_empty_unresolvable_when_all_resolved(self):
        """resolve_mentions returns empty unresolvable_ids when all mentions resolve."""
        from src.utils import resolve_mentions

        mock_settings = MagicMock()
        mock_settings.get.return_value = "user@example.com"

        resolved, warnings, unresolvable_ids = resolve_mentions(
            ["<@111>", "<@222>"],
            mock_settings,
        )

        assert resolved == ["user@example.com", "user@example.com"]
        assert len(warnings) == 0
        assert unresolvable_ids == set()

    def test_deduplicates_unresolvable_ids(self):
        """Multiple mentions of the same user produce one unresolvable ID."""
        from src.utils import resolve_mentions

        mock_settings = MagicMock()
        mock_settings.get.return_value = None

        resolved, warnings, unresolvable_ids = resolve_mentions(
            ["<@111>", "<@111>"],
            mock_settings,
        )

        assert len(unresolvable_ids) == 1
