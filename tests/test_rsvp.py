"""Tests for the /cal invite command — mixed resolution of me, @mentions, and emails."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from googleapiclient.errors import HttpError


# ── /cal invite command ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_me_with_stored_email():
    """invite resolves 'me' to the caller's stored email."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "me@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = "me@example.com"
    interaction.client.settings = mock_settings

    await invite.callback(interaction, event_id="evt1", people="me")

    mock_settings.get.assert_called_once_with("12345", "email")
    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["me@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invited" in content
    assert "me@example.com" in content
    assert "invitation" in content.lower()


@pytest.mark.asyncio
async def test_invite_me_no_stored_email():
    """invite returns a warning when 'me' has no stored email."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await invite.callback(interaction, event_id="evt1", people="me")

    mock_calendar.add_attendees.assert_not_called()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "No valid recipients" in content
    assert "no email stored" in content.lower()


@pytest.mark.asyncio
async def test_invite_raw_emails():
    """invite accepts raw comma-separated email addresses."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "alice@example.com", "responseStatus": "needsAction"},
        {"email": "bob@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await invite.callback(
        interaction,
        event_id="evt1",
        people="alice@example.com, bob@example.com",
    )

    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["alice@example.com", "bob@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invited" in content
    assert "2" in content
    assert "invitation" in content.lower()


@pytest.mark.asyncio
async def test_invite_mention_with_stored_email():
    """invite resolves a Discord mention to the stored email."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "chaz@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = "chaz@example.com"
    interaction.client.settings = mock_settings

    await invite.callback(interaction, event_id="evt1", people="<@67890>")

    mock_settings.get.assert_called_once_with("67890", "email")
    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["chaz@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invited" in content
    assert "chaz@example.com" in content


@pytest.mark.asyncio
async def test_invite_mention_no_stored_email():
    """invite returns a warning for a mention with no stored email."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await invite.callback(interaction, event_id="evt1", people="<@67890>")

    mock_calendar.add_attendees.assert_not_called()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "No valid recipients" in content
    assert "no email stored" in content.lower()


@pytest.mark.asyncio
async def test_invite_mixed_with_partial_success():
    """invite adds valid entries and warns about invalid ones (partial success)."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "me@example.com", "responseStatus": "needsAction"},
        {"email": "alice@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    # 'me' lookup returns email; mention lookup returns None
    mock_settings.get.side_effect = lambda did, key: (
        "me@example.com" if did == "12345" else None
    )
    interaction.client.settings = mock_settings

    await invite.callback(
        interaction,
        event_id="evt1",
        people="me, <@67890>, alice@example.com, invalid-email",
    )

    # Only the valid entries should be added
    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["me@example.com", "alice@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invited 2" in content
    assert "me@example.com" in content
    assert "alice@example.com" in content
    # Warnings for the bad entries
    assert "no email stored" in content.lower()
    assert "invalid-email" in content


@pytest.mark.asyncio
async def test_invite_invalid_email_warning():
    """invite warns about invalid email format without blocking valid entries."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "good@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await invite.callback(
        interaction,
        event_id="evt1",
        people="good@example.com, not-an-email",
    )

    # Only the valid email is added
    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["good@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invited 1" in content
    assert "good@example.com" in content
    assert "Invalid" in content or "invalid" in content.lower()


@pytest.mark.asyncio
async def test_invite_calendar_not_configured():
    """invite responds with an error when calendar is not configured."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await invite.callback(interaction, event_id="evt1", people="me@example.com")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_invite_handles_api_error():
    """invite returns a user-friendly message on API errors."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 404
    mock_calendar.add_attendees.side_effect = HttpError(
        http_resp, b'{"error": "not found"}'
    )
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await invite.callback(interaction, event_id="evt1", people="alice@example.com")

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "not found" in content.lower() or "event not found" in content.lower()


@pytest.mark.asyncio
async def test_invite_deduplicates_duplicate_entries():
    """invite deduplicates entries (same email appears only once)."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "me@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = "me@example.com"
    interaction.client.settings = mock_settings

    await invite.callback(
        interaction,
        event_id="evt1",
        people="me, me@example.com",
    )

    # Should deduplicate: only one me@example.com entry
    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["me@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invited 1" in content


@pytest.mark.asyncio
async def test_invite_empty_people():
    """invite returns an error when people string is empty."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await invite.callback(interaction, event_id="evt1", people="  ,  ")

    mock_calendar.add_attendees.assert_not_called()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "No people" in content


# ── command metadata ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_command_metadata():
    """The invite command has correct metadata."""
    from src.commands.rsvp import invite

    assert invite.name == "invite"
    assert "invite" in invite.description.lower()


@pytest.mark.asyncio
async def test_invite_has_autocomplete():
    """The invite command uses autocomplete on the event_id parameter."""
    from src.commands.delete import delete_event_autocomplete
    from src.commands.rsvp import invite

    param = [
        p for p in invite._params.values()
        if p.name == "event_id"
    ][0]
    assert param.autocomplete is not None
    assert param.autocomplete is delete_event_autocomplete
