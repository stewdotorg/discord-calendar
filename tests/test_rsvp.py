"""Tests for the /cal invite me and /cal invite by-email commands."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from googleapiclient.errors import HttpError


# ── /cal invite me command ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invite_me_with_stored_email():
    """invite me uses the stored email when no email param is provided."""
    from src.commands.rsvp import invite_me

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

    await invite_me.callback(interaction, event_id="evt1", email=None)

    mock_settings.get.assert_called_once_with("12345", "email")
    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["me@example.com"]
    )
    interaction.edit_original_response.assert_called_once()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Added as attendee" in content
    assert "me@example.com" in content
    assert "invitation" in content.lower()


@pytest.mark.asyncio
async def test_invite_me_with_inline_email():
    """invite me uses the inline email param when provided, overriding stored email."""
    from src.commands.rsvp import invite_me

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "override@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await invite_me.callback(interaction, event_id="evt1", email="override@example.com")

    mock_settings.get.assert_not_called()
    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["override@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Added as attendee" in content
    assert "override@example.com" in content


@pytest.mark.asyncio
async def test_invite_me_no_email_and_no_stored_email():
    """invite me returns an error when no email is provided and none is stored."""
    from src.commands.rsvp import invite_me

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

    await invite_me.callback(interaction, event_id="evt1", email=None)

    mock_calendar.add_attendees.assert_not_called()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "No email" in content
    assert "/cal settings email set" in content.lower() or "email set" in content.lower()


@pytest.mark.asyncio
async def test_invite_me_invalid_inline_email():
    """invite me returns an error message for invalid inline email format."""
    from src.commands.rsvp import invite_me

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await invite_me.callback(interaction, event_id="evt1", email="not-an-email")

    mock_calendar.add_attendees.assert_not_called()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invalid" in content or "invalid" in content.lower()


@pytest.mark.asyncio
async def test_invite_me_calendar_not_configured():
    """invite me responds with an error when calendar is not configured."""
    from src.commands.rsvp import invite_me

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await invite_me.callback(interaction, event_id="evt1", email="me@example.com")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_invite_me_handles_api_error():
    """invite me returns a user-friendly message on API errors."""
    from src.commands.rsvp import invite_me

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 404
    mock_calendar.add_attendees.side_effect = HttpError(
        http_resp, b'{"error": "not found"}'
    )
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = "me@example.com"
    interaction.client.settings = mock_settings

    await invite_me.callback(interaction, event_id="evt1", email=None)

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "not found" in content.lower() or "event not found" in content.lower()


@pytest.mark.asyncio
async def test_invite_me_command_metadata():
    """The invite me command has correct metadata."""
    from src.commands.rsvp import invite_me

    assert invite_me.name == "me"
    assert "Add yourself" in invite_me.description or "add yourself" in invite_me.description.lower()


# ── /cal invite by-email command ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_by_email_with_multiple_emails():
    """invite by-email adds multiple comma-separated emails as attendees."""
    from src.commands.rsvp import invite_by_email

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "alice@example.com", "responseStatus": "needsAction"},
        {"email": "bob@example.com", "responseStatus": "needsAction"},
        {"email": "carol@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    await invite_by_email.callback(
        interaction,
        event_id="evt1",
        emails="alice@example.com, bob@example.com, carol@example.com",
    )

    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["alice@example.com", "bob@example.com", "carol@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invited" in content
    assert "3" in content
    assert "attendee" in content.lower()


@pytest.mark.asyncio
async def test_invite_by_email_with_single_email():
    """invite by-email works with a single email."""
    from src.commands.rsvp import invite_by_email

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "alice@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    await invite_by_email.callback(
        interaction,
        event_id="evt1",
        emails="alice@example.com",
    )

    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["alice@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invited" in content
    assert "1" in content or "attendee" in content.lower()


@pytest.mark.asyncio
async def test_invite_by_email_invalid_email():
    """invite by-email returns an error message when any email is invalid."""
    from src.commands.rsvp import invite_by_email

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar

    await invite_by_email.callback(
        interaction,
        event_id="evt1",
        emails="good@example.com, not-an-email",
    )

    mock_calendar.add_attendees.assert_not_called()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invalid" in content or "invalid" in content.lower()


@pytest.mark.asyncio
async def test_invite_by_email_calendar_not_configured():
    """invite by-email responds with an error when calendar is not configured."""
    from src.commands.rsvp import invite_by_email

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await invite_by_email.callback(interaction, event_id="evt1", emails="alice@example.com")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_invite_by_email_handles_api_error():
    """invite by-email returns a user-friendly message on API errors."""
    from src.commands.rsvp import invite_by_email

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 403
    mock_calendar.add_attendees.side_effect = HttpError(
        http_resp, b'{"error": "forbidden"}'
    )
    interaction.client.calendar = mock_calendar

    await invite_by_email.callback(interaction, event_id="evt1", emails="alice@example.com")

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "cannot add attendees" in content.lower()


@pytest.mark.asyncio
async def test_invite_by_email_command_metadata():
    """The invite by-email command has correct metadata."""
    from src.commands.rsvp import invite_by_email

    assert invite_by_email.name == "by-email"
    assert "Invite" in invite_by_email.description or "invite" in invite_by_email.description.lower()


# ── autocomplete ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_me_has_autocomplete():
    """The invite me command uses autocomplete on the event_id parameter."""
    from src.commands.delete import delete_event_autocomplete
    from src.commands.rsvp import invite_me

    param = [
        p for p in invite_me._params.values()
        if p.name == "event_id"
    ][0]
    assert param.autocomplete is not None
    assert param.autocomplete is delete_event_autocomplete


@pytest.mark.asyncio
async def test_invite_by_email_has_autocomplete():
    """The invite by-email command uses autocomplete on the event_id parameter."""
    from src.commands.delete import delete_event_autocomplete
    from src.commands.rsvp import invite_by_email

    param = [
        p for p in invite_by_email._params.values()
        if p.name == "event_id"
    ][0]
    assert param.autocomplete is not None
    assert param.autocomplete is delete_event_autocomplete
