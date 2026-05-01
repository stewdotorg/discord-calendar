"""Tests for the /cal rsvp and /cal invite commands."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from googleapiclient.errors import HttpError


# ── /cal rsvp command ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rsvp_with_stored_email():
    """RSVP uses the stored email when no email param is provided."""
    from src.commands.rsvp import rsvp

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

    await rsvp.callback(interaction, event_id="evt1", email=None)

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
async def test_rsvp_with_inline_email():
    """RSVP uses the inline email param when provided, overriding stored email."""
    from src.commands.rsvp import rsvp

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

    await rsvp.callback(interaction, event_id="evt1", email="override@example.com")

    mock_settings.get.assert_not_called()
    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["override@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Added as attendee" in content
    assert "override@example.com" in content


@pytest.mark.asyncio
async def test_rsvp_no_email_and_no_stored_email():
    """RSVP returns an error when no email is provided and none is stored."""
    from src.commands.rsvp import rsvp

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

    await rsvp.callback(interaction, event_id="evt1", email=None)

    mock_calendar.add_attendees.assert_not_called()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "No email" in content
    assert "email set" in content.lower() or "/cal email" in content.lower()


@pytest.mark.asyncio
async def test_rsvp_invalid_inline_email():
    """RSVP returns an error message for invalid inline email format."""
    from src.commands.rsvp import rsvp

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await rsvp.callback(interaction, event_id="evt1", email="not-an-email")

    mock_calendar.add_attendees.assert_not_called()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invalid" in content or "invalid" in content.lower()


@pytest.mark.asyncio
async def test_rsvp_calendar_not_configured():
    """RSVP responds with an error when calendar is not configured."""
    from src.commands.rsvp import rsvp

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await rsvp.callback(interaction, event_id="evt1", email="me@example.com")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_rsvp_handles_api_error():
    """RSVP returns a user-friendly message on API errors."""
    from src.commands.rsvp import rsvp

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

    await rsvp.callback(interaction, event_id="evt1", email=None)

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "not found" in content.lower() or "event not found" in content.lower()


@pytest.mark.asyncio
async def test_rsvp_command_metadata():
    """The rsvp command has correct metadata."""
    from src.commands.rsvp import rsvp

    assert rsvp.name == "rsvp"
    assert "RSVP" in rsvp.description or "rsvp" in rsvp.description.lower()


# ── /cal invite command ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_with_multiple_emails():
    """Invite adds multiple comma-separated emails as attendees."""
    from src.commands.rsvp import invite

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

    await invite.callback(
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
async def test_invite_with_single_email():
    """Invite works with a single email."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "alice@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    await invite.callback(
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
async def test_invite_invalid_email():
    """Invite returns an error message when any email is invalid."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar

    await invite.callback(
        interaction,
        event_id="evt1",
        emails="good@example.com, not-an-email",
    )

    mock_calendar.add_attendees.assert_not_called()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invalid" in content or "invalid" in content.lower()


@pytest.mark.asyncio
async def test_invite_calendar_not_configured():
    """Invite responds with an error when calendar is not configured."""
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await invite.callback(interaction, event_id="evt1", emails="alice@example.com")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_invite_handles_api_error():
    """Invite returns a user-friendly message on API errors."""
    from src.commands.rsvp import invite

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

    await invite.callback(interaction, event_id="evt1", emails="alice@example.com")

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "permission" in content.lower()


@pytest.mark.asyncio
async def test_invite_command_metadata():
    """The invite command has correct metadata."""
    from src.commands.rsvp import invite

    assert invite.name == "invite"
    assert "Invite" in invite.description or "invite" in invite.description.lower()


# ── autocomplete ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rsvp_has_autocomplete():
    """The rsvp command uses autocomplete on the event_id parameter."""
    from src.commands.delete import delete_event_autocomplete
    from src.commands.rsvp import rsvp

    param = [
        p for p in rsvp._params.values()
        if p.name == "event_id"
    ][0]
    assert param.autocomplete is not None
    assert param.autocomplete is delete_event_autocomplete


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
