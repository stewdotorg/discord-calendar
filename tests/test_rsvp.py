"""Tests for the /cal invite command — mixed resolution of me, @mentions, and emails."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from googleapiclient.errors import HttpError


# ── /cal invite command ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_me_with_stored_email():
    """invite resolves 'me' to the caller's stored email."""
    from src.views import PostToChannelView
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
    kwargs = interaction.edit_original_response.call_args.kwargs
    assert isinstance(kwargs["view"], PostToChannelView)
    content = kwargs["content"]
    assert "Invited" in content
    assert "me@example.com" in content
    assert "invitation" in content.lower()


@pytest.mark.asyncio
async def test_invite_me_no_stored_email():
    """invite returns a warning when 'me' has no stored email."""
    from src.views import PostToChannelView
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
    kwargs = interaction.edit_original_response.call_args.kwargs
    assert isinstance(kwargs["view"], PostToChannelView)
    content = kwargs["content"]
    assert "No valid recipients" in content
    assert "no email stored" in content.lower()


@pytest.mark.asyncio
async def test_invite_raw_emails():
    """invite accepts raw comma-separated email addresses."""
    from src.views import PostToChannelView
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
    kwargs = interaction.edit_original_response.call_args.kwargs
    assert isinstance(kwargs["view"], PostToChannelView)
    content = kwargs["content"]
    assert "Invited" in content
    assert "2" in content
    assert "invitation" in content.lower()


@pytest.mark.asyncio
async def test_invite_mention_with_stored_email():
    """invite resolves a Discord mention to the stored email."""
    from src.views import PostToChannelView
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
    kwargs = interaction.edit_original_response.call_args.kwargs
    assert isinstance(kwargs["view"], PostToChannelView)
    content = kwargs["content"]
    assert "Invited" in content
    assert "chaz@example.com" in content


@pytest.mark.asyncio
async def test_invite_mention_no_stored_email():
    """invite returns a warning for a mention with no stored email."""
    from src.views import PostToChannelView
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
    kwargs = interaction.edit_original_response.call_args.kwargs
    assert isinstance(kwargs["view"], PostToChannelView)
    content = kwargs["content"]
    assert "No valid recipients" in content
    assert "no email stored" in content.lower()


@pytest.mark.asyncio
async def test_invite_mixed_with_partial_success():
    """invite adds valid entries and warns about invalid ones (partial success)."""
    from src.views import PostToChannelView
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
    kwargs = interaction.edit_original_response.call_args.kwargs
    assert isinstance(kwargs["view"], PostToChannelView)
    content = kwargs["content"]
    assert "Invited 2" in content
    assert "me@example.com" in content
    assert "alice@example.com" in content
    # Warnings for the bad entries
    assert "no email stored" in content.lower()
    assert "invalid-email" in content


@pytest.mark.asyncio
async def test_invite_invalid_email_warning():
    """invite warns about invalid email format without blocking valid entries."""
    from src.views import PostToChannelView
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
    kwargs = interaction.edit_original_response.call_args.kwargs
    assert isinstance(kwargs["view"], PostToChannelView)
    content = kwargs["content"]
    assert "Invited 1" in content
    assert "good@example.com" in content
    assert "Invalid" in content or "invalid" in content.lower()


@pytest.mark.asyncio
async def test_invite_calendar_not_configured():
    """invite responds with an error when calendar is not configured."""
    from src.views import PostToChannelView
    from src.commands.rsvp import invite

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await invite.callback(interaction, event_id="evt1", people="me@example.com")

    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert kwargs["ephemeral"] is True
    assert isinstance(kwargs["view"], PostToChannelView)
    msg = interaction.response.send_message.call_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_invite_handles_api_error():
    """invite returns a user-friendly message on API errors."""
    from src.views import PostToChannelView
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

    kwargs = interaction.edit_original_response.call_args.kwargs
    assert isinstance(kwargs["view"], PostToChannelView)
    content = kwargs["content"]
    assert "not found" in content.lower() or "event not found" in content.lower()


@pytest.mark.asyncio
async def test_invite_deduplicates_duplicate_entries():
    """invite deduplicates entries (same email appears only once)."""
    from src.views import PostToChannelView
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
    kwargs = interaction.edit_original_response.call_args.kwargs
    assert isinstance(kwargs["view"], PostToChannelView)
    content = kwargs["content"]
    assert "Invited 1" in content


@pytest.mark.asyncio
async def test_invite_empty_people():
    """invite returns an error when people string is empty."""
    from src.views import PostToChannelView
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
    kwargs = interaction.edit_original_response.call_args.kwargs
    assert isinstance(kwargs["view"], PostToChannelView)
    content = kwargs["content"]
    assert "No people" in content


# ── RSVP button ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rsvp_button_email_stored_adds_attendee():
    """RSVP button with stored email adds user as attendee with confirmation."""
    from src.commands.rsvp import _handle_rsvp_interaction

    interaction = MagicMock()
    interaction.user.id = 12345
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "abc123",
        "summary": "Team Standup",
        "attendees": [],
    }
    mock_calendar.add_attendees.return_value = []
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = "user@example.com"
    interaction.client.settings = mock_settings

    await _handle_rsvp_interaction(interaction, "abc123")

    mock_settings.get.assert_called_once_with("12345", "email")
    mock_calendar.get_event.assert_called_once_with("abc123")
    mock_calendar.add_attendees.assert_called_once_with(
        "abc123", ["user@example.com"]
    )
    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "Team Standup" in msg
    assert "✅" in msg


@pytest.mark.asyncio
async def test_rsvp_button_already_attendee_shows_message():
    """RSVP button when user is already an attendee shows already-on-list message."""
    from src.commands.rsvp import _handle_rsvp_interaction

    interaction = MagicMock()
    interaction.user.id = 12345
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "abc123",
        "summary": "Team Standup",
        "attendees": [{"email": "user@example.com"}],
    }
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = "user@example.com"
    interaction.client.settings = mock_settings

    await _handle_rsvp_interaction(interaction, "abc123")

    mock_calendar.add_attendees.assert_not_called()
    msg = interaction.response.send_message.call_args.args[0]
    assert "already on the list" in msg.lower()


@pytest.mark.asyncio
async def test_rsvp_button_no_email_stored_opens_modal():
    """RSVP button with no email stored opens the email modal."""
    from src.commands.rsvp import _handle_rsvp_interaction

    interaction = MagicMock()
    interaction.user.id = 12345
    interaction.response = MagicMock()
    interaction.response.send_modal = AsyncMock()

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await _handle_rsvp_interaction(interaction, "abc123")

    interaction.response.send_modal.assert_called_once()
    modal = interaction.response.send_modal.call_args.args[0]
    assert modal._event_id == "abc123"


@pytest.mark.asyncio
async def test_rsvp_button_api_error_shows_error():
    """RSVP button when Google Calendar API is down shows ephemeral error."""
    from src.commands.rsvp import _handle_rsvp_interaction

    interaction = MagicMock()
    interaction.user.id = 12345
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.side_effect = HttpError(
        MagicMock(status=500), b'{"error": "internal"}'
    )
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = "user@example.com"
    interaction.client.settings = mock_settings

    await _handle_rsvp_interaction(interaction, "abc123")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "Could not add" in msg or "try again" in msg.lower()


@pytest.mark.asyncio
async def test_rsvp_modal_valid_email_saves_and_adds():
    """Modal with valid email saves to settings, adds attendee, confirms."""
    from src.commands.rsvp import EmailModal

    interaction = MagicMock()
    interaction.user.id = 12345
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "abc123",
        "summary": "Team Standup",
        "attendees": [],
    }
    mock_calendar.add_attendees.return_value = []
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    modal = EmailModal(event_id="abc123")
    modal.email_input._value = "user@example.com"

    await modal.on_submit(interaction)

    mock_settings.set.assert_called_once_with(
        "12345", "email", "user@example.com"
    )
    mock_calendar.add_attendees.assert_called_once_with(
        "abc123", ["user@example.com"]
    )
    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "Email saved" in msg
    assert "Team Standup" in msg
    assert "✅" in msg


@pytest.mark.asyncio
async def test_rsvp_modal_invalid_email_shows_error():
    """Modal with invalid email shows error hint."""
    from src.commands.rsvp import EmailModal

    interaction = MagicMock()
    interaction.user.id = 12345
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar
    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    modal = EmailModal(event_id="abc123")
    modal.email_input._value = "not-an-email"

    await modal.on_submit(interaction)

    mock_settings.set.assert_not_called()
    mock_calendar.add_attendees.assert_not_called()
    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "Invalid" in msg or "valid" in msg.lower()


@pytest.mark.asyncio
async def test_rsvp_modal_api_error_shows_error():
    """Modal submit when Google Calendar API is down shows ephemeral error."""
    from src.commands.rsvp import EmailModal

    interaction = MagicMock()
    interaction.user.id = 12345
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.side_effect = HttpError(
        MagicMock(status=500), b'{"error": "internal"}'
    )
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    modal = EmailModal(event_id="abc123")
    modal.email_input._value = "user@example.com"

    await modal.on_submit(interaction)

    # Email is saved before API call attempt
    mock_settings.set.assert_called_once_with(
        "12345", "email", "user@example.com"
    )
    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "Could not add" in msg or "try again" in msg.lower()


@pytest.mark.asyncio
async def test_rsvp_view_has_correct_custom_id():
    """RsvpView encodes event_id in button custom_id."""
    from src.commands.rsvp import RsvpView

    view = RsvpView(event_id="abc123")
    assert view.timeout is None
    assert len(view.children) == 1
    button = view.children[0]
    assert button.custom_id == "rsvp:abc123"
    assert button.label == "📅 RSVP"


@pytest.mark.asyncio
async def test_rsvp_view_callback_delegates_to_handler():
    """RsvpView button callback delegates to _handle_rsvp_interaction."""
    from unittest.mock import patch

    from src.commands.rsvp import RsvpView

    interaction = MagicMock()

    with patch("src.commands.rsvp._handle_rsvp_interaction") as mock_handler:
        mock_handler.return_value = None
        view = RsvpView(event_id="abc123")
        button = view.children[0]
        await button.callback(interaction)

    mock_handler.assert_called_once_with(interaction, "abc123")


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
    from src.commands.autocomplete import event_autocomplete
    from src.commands.rsvp import invite

    param = [
        p for p in invite._params.values()
        if p.name == "event_id"
    ][0]
    assert param.autocomplete is not None
    assert param.autocomplete is event_autocomplete
