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


# ── /cal invite add command ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_add_with_multiple_emails():
    """Invite add adds multiple comma-separated emails as attendees."""
    from src.commands.rsvp import invite_add

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

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await invite_add.callback(
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
async def test_invite_add_with_single_email():
    """Invite add works with a single email."""
    from src.commands.rsvp import invite_add

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "alice@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await invite_add.callback(
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
async def test_invite_add_with_mentions():
    """Invite add resolves @mentions to stored emails."""
    from src.commands.rsvp import invite_add

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "bob@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    def mock_get(discord_id, key):
        if discord_id == "123456789":
            return "bob@example.com"
        return None

    mock_settings = MagicMock()
    mock_settings.get = mock_get
    interaction.client.settings = mock_settings

    await invite_add.callback(
        interaction,
        event_id="evt1",
        emails="<@123456789>",
    )

    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["bob@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invited" in content
    assert "bob@example.com" in content


@pytest.mark.asyncio
async def test_invite_add_mixed_mentions_and_emails():
    """Invite add handles a mix of @mentions and raw emails."""
    from src.commands.rsvp import invite_add

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

    def mock_get(discord_id, key):
        if discord_id == "123456789":
            return "bob@example.com"
        return None

    mock_settings = MagicMock()
    mock_settings.get = mock_get
    interaction.client.settings = mock_settings

    await invite_add.callback(
        interaction,
        event_id="evt1",
        emails="<@123456789>, alice@example.com",
    )

    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["bob@example.com", "alice@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invited" in content
    assert "2" in content


@pytest.mark.asyncio
async def test_invite_add_unresolvable_mention_shows_warning():
    """Invite add shows a warning for @mentions without stored emails."""
    from src.commands.rsvp import invite_add

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.add_attendees.return_value = [
        {"email": "alice@example.com", "responseStatus": "needsAction"},
    ]
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await invite_add.callback(
        interaction,
        event_id="evt1",
        emails="<@999999>, alice@example.com",
    )

    # Should still invite the resolvable email
    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["alice@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invited" in content
    assert "⚠️" in content
    assert "no email stored" in content.lower()
    assert "<@999999>" in content


@pytest.mark.asyncio
async def test_invite_add_invalid_email():
    """Invite add returns an error message when any email is invalid."""
    from src.commands.rsvp import invite_add

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await invite_add.callback(
        interaction,
        event_id="evt1",
        emails="good@example.com, not-an-email",
    )

    mock_calendar.add_attendees.assert_not_called()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Invalid" in content or "invalid" in content.lower()


@pytest.mark.asyncio
async def test_invite_add_calendar_not_configured():
    """Invite add responds with an error when calendar is not configured."""
    from src.commands.rsvp import invite_add

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await invite_add.callback(interaction, event_id="evt1", emails="alice@example.com")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_invite_add_handles_api_error():
    """Invite add returns a user-friendly message on API errors."""
    from src.commands.rsvp import invite_add

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

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await invite_add.callback(interaction, event_id="evt1", emails="alice@example.com")

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "cannot add attendees" in content.lower()


@pytest.mark.asyncio
async def test_invite_add_no_emails():
    """Invite add returns an error when no emails are provided."""
    from src.commands.rsvp import invite_add

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await invite_add.callback(
        interaction,
        event_id="evt1",
        emails=",  ,  ",
    )

    mock_calendar.add_attendees.assert_not_called()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "No email" in content or "no email" in content.lower()


# ── /cal invite me command ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_me_with_stored_email():
    """Invite me adds the caller using their stored email."""
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
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Added" in content
    assert "me@example.com" in content


@pytest.mark.asyncio
async def test_invite_me_no_stored_email():
    """Invite me returns an error when the user has no stored email."""
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
    assert "email-set" in content or "/cal settings" in content


@pytest.mark.asyncio
async def test_invite_me_with_email_override():
    """Invite me uses the provided email override instead of stored email."""
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

    await invite_me.callback(
        interaction, event_id="evt1", email="override@example.com"
    )

    mock_settings.get.assert_not_called()
    mock_calendar.add_attendees.assert_called_once_with(
        "evt1", ["override@example.com"]
    )
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Added" in content
    assert "override@example.com" in content


@pytest.mark.asyncio
async def test_invite_me_calendar_not_configured():
    """Invite me responds with an error when calendar is not configured."""
    from src.commands.rsvp import invite_me

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await invite_me.callback(interaction, event_id="evt1", email=None)

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_invite_me_handles_api_error():
    """Invite me returns a user-friendly message on API errors."""
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


# ── group metadata ──────────────────────────────────────────────────────────


def test_invite_is_a_group():
    """The invite command is a Group with add and me subcommands."""
    from src.commands.rsvp import invite_group

    assert invite_group.name == "invite"
    assert len(invite_group.commands) == 2
    subcommand_names = {cmd.name for cmd in invite_group.commands}
    assert subcommand_names == {"add", "me"}


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
async def test_invite_add_has_autocomplete():
    """The invite add command uses autocomplete on the event_id parameter."""
    from src.commands.delete import delete_event_autocomplete
    from src.commands.rsvp import invite_add

    param = [
        p for p in invite_add._params.values()
        if p.name == "event_id"
    ][0]
    assert param.autocomplete is not None
    assert param.autocomplete is delete_event_autocomplete


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
