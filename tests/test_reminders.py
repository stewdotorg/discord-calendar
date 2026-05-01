"""Tests for /cal reminders and /cal reminders-defaults commands."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from googleapiclient.errors import HttpError


# ── parse_minutes ────────────────────────────────────────────────────────────


def test_parse_minutes_single_value():
    """parse_minutes returns a list with a single integer."""
    from src.utils import parse_minutes

    result = parse_minutes("10")
    assert result == [10]


def test_parse_minutes_multiple_values():
    """parse_minutes handles comma-separated values."""
    from src.utils import parse_minutes

    result = parse_minutes("10,30")
    assert result == [10, 30]


def test_parse_minutes_with_spaces():
    """parse_minutes trims whitespace around values."""
    from src.utils import parse_minutes

    result = parse_minutes("10, 30")
    assert result == [10, 30]


def test_parse_minutes_empty_raises():
    """parse_minutes raises ValueError for empty strings."""
    from src.utils import parse_minutes

    with pytest.raises(ValueError):
        parse_minutes("")


def test_parse_minutes_non_numeric_raises():
    """parse_minutes raises ValueError for non-integer values."""
    from src.utils import parse_minutes

    with pytest.raises(ValueError):
        parse_minutes("abc")


def test_parse_minutes_negative_raises():
    """parse_minutes raises ValueError for negative values."""
    from src.utils import parse_minutes

    with pytest.raises(ValueError):
        parse_minutes("-5")


# ── _format_reminders_list ──────────────────────────────────────────────────


def test_format_reminders_single():
    """_format_reminders_list formats a single reminder."""
    from src.commands.reminders import _format_reminders_list

    result = _format_reminders_list([10])
    assert result == "10 min before"


def test_format_reminders_multiple():
    """_format_reminders_list formats multiple reminders."""
    from src.commands.reminders import _format_reminders_list

    result = _format_reminders_list([10, 30])
    assert result == "10 min, 30 min before"


def test_format_reminders_empty():
    """_format_reminders_list returns an empty string for an empty list."""
    from src.commands.reminders import _format_reminders_list

    result = _format_reminders_list([])
    assert result == ""


# ── /cal reminders set ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reminders_set_single_value():
    """The /cal reminders set command calls add_reminders with a single value."""
    from src.commands.reminders import reminders_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.add_reminders.return_value = {
        "useDefault": False,
        "overrides": [{"method": "popup", "minutes": 10}],
    }
    interaction.client.calendar = mock_calendar

    await reminders_set.callback(interaction, event_id="evt1", minutes="10")

    mock_calendar.add_reminders.assert_called_once_with("evt1", [10])
    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "✅ Reminders set" in msg
    assert "10 min before" in msg


@pytest.mark.asyncio
async def test_reminders_set_multiple_values():
    """The /cal reminders set command handles comma-separated minutes."""
    from src.commands.reminders import reminders_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.add_reminders.return_value = {
        "useDefault": False,
        "overrides": [
            {"method": "popup", "minutes": 10},
            {"method": "popup", "minutes": 30},
        ],
    }
    interaction.client.calendar = mock_calendar

    await reminders_set.callback(interaction, event_id="evt1", minutes="10,30")

    mock_calendar.add_reminders.assert_called_once_with("evt1", [10, 30])
    msg = interaction.response.send_message.call_args.args[0]
    assert "✅ Reminders set" in msg
    assert "10 min, 30 min before" in msg


@pytest.mark.asyncio
async def test_reminders_set_calendar_not_configured():
    """The /cal reminders set command responds with an error when calendar is None."""
    from src.commands.reminders import reminders_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await reminders_set.callback(interaction, event_id="evt1", minutes="10")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not configured" in msg.lower()
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_reminders_set_invalid_minutes():
    """The /cal reminders set command returns an error for invalid minutes."""
    from src.commands.reminders import reminders_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = MagicMock()

    await reminders_set.callback(interaction, event_id="evt1", minutes="abc")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "Invalid" in msg or "invalid" in msg.lower()
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_reminders_set_api_error():
    """The /cal reminders set command returns a user-friendly error on API failure."""
    from src.commands.reminders import reminders_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 404
    mock_calendar.add_reminders.side_effect = HttpError(
        http_resp, b'{"error": "not found"}'
    )
    interaction.client.calendar = mock_calendar

    await reminders_set.callback(interaction, event_id="nonexistent", minutes="10")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not found" in msg.lower()


# ── /cal reminders show ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reminders_show_with_reminders():
    """The /cal reminders show command displays reminders when set."""
    from src.commands.reminders import reminders_show

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "evt1",
        "summary": "Team Sync",
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 10},
                {"method": "popup", "minutes": 30},
            ],
        },
    }
    interaction.client.calendar = mock_calendar

    await reminders_show.callback(interaction, event_id="evt1")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "📋 Reminders" in msg
    assert "10 min, 30 min before" in msg
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_reminders_show_no_reminders():
    """The /cal reminders show command shows 'No reminders set' when useDefault."""
    from src.commands.reminders import reminders_show

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "evt1",
        "summary": "Team Sync",
        "reminders": {"useDefault": True},
    }
    interaction.client.calendar = mock_calendar

    await reminders_show.callback(interaction, event_id="evt1")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "No reminders" in msg


@pytest.mark.asyncio
async def test_reminders_show_no_overrides():
    """The /cal reminders show command shows 'No reminders set' when no overrides."""
    from src.commands.reminders import reminders_show

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "evt1",
        "summary": "Team Sync",
        "reminders": {"useDefault": False, "overrides": []},
    }
    interaction.client.calendar = mock_calendar

    await reminders_show.callback(interaction, event_id="evt1")

    msg = interaction.response.send_message.call_args.args[0]
    assert "No reminders" in msg


@pytest.mark.asyncio
async def test_reminders_show_calendar_not_configured():
    """The /cal reminders show command responds with an error when calendar is None."""
    from src.commands.reminders import reminders_show

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await reminders_show.callback(interaction, event_id="evt1")

    signal = interaction.response.send_message.call_args
    assert "not configured" in signal.args[0].lower()
    assert signal.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_reminders_show_api_error():
    """The /cal reminders show command returns a user-friendly error on API failure."""
    from src.commands.reminders import reminders_show

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 404
    mock_calendar.get_event.side_effect = HttpError(
        http_resp, b'{"error": "not found"}'
    )
    interaction.client.calendar = mock_calendar

    await reminders_show.callback(interaction, event_id="nonexistent")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not found" in msg.lower()


# ── /cal reminders-defaults set ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reminders_defaults_set_stores_and_confirms():
    """The /cal reminders-defaults set command stores default and confirms."""
    from src.commands.reminders import reminders_defaults_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await reminders_defaults_set.callback(interaction, minutes="10,30")

    mock_settings.set.assert_called_once_with("12345", "default_reminders", "10,30")
    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "✅ Default reminders" in msg
    assert "10 min, 30 min before" in msg
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_reminders_defaults_set_invalid_minutes():
    """The /cal reminders-defaults set command rejects invalid minutes."""
    from src.commands.reminders import reminders_defaults_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await reminders_defaults_set.callback(interaction, minutes="abc")

    mock_settings.set.assert_not_called()
    msg = interaction.response.send_message.call_args.args[0]
    assert "Invalid" in msg or "invalid" in msg.lower()
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_reminders_defaults_set_single_value():
    """The /cal reminders-defaults set command stores a single value."""
    from src.commands.reminders import reminders_defaults_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await reminders_defaults_set.callback(interaction, minutes="5")

    mock_settings.set.assert_called_once_with("12345", "default_reminders", "5")
    msg = interaction.response.send_message.call_args.args[0]
    assert "✅ Default reminders" in msg
    assert "5 min before" in msg


# ── /cal reminders-defaults show ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reminders_defaults_show_displays_stored():
    """The /cal reminders-defaults show command displays stored defaults."""
    from src.commands.reminders import reminders_defaults_show

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    mock_settings.get.return_value = "10,30"
    interaction.client.settings = mock_settings

    await reminders_defaults_show.callback(interaction)

    mock_settings.get.assert_called_once_with("12345", "default_reminders")
    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "📋 Default reminders" in msg
    assert "10 min, 30 min before" in msg
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_reminders_defaults_show_no_default():
    """The /cal reminders-defaults show command shows message when no default."""
    from src.commands.reminders import reminders_defaults_show

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await reminders_defaults_show.callback(interaction)

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "No default reminders" in msg
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


# ── create with default reminders ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_applies_default_reminders_when_set():
    """The /cal create command applies default reminders after creating an event."""
    from src.commands.create import create

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    mock_calendar.create_event.return_value = {
        "id": "evt_001",
        "htmlLink": "https://calendar.google.com/event?eid=evt_001",
    }
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = "10,30"
    interaction.client.settings = mock_settings

    await create.callback(
        interaction,
        title="Team Sync",
        when="2026-05-01 14:00",
        duration=30,
        description=None,
    )

    # create_event should be called
    mock_calendar.create_event.assert_called_once()
    # add_reminders should be called with the default minutes
    mock_calendar.add_reminders.assert_called_once_with("evt_001", [10, 30])
    # Response should still contain event info
    response_text = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Team Sync" in response_text


@pytest.mark.asyncio
async def test_create_skips_default_reminders_when_not_set():
    """The /cal create command does not call add_reminders when no default is set."""
    from src.commands.create import create

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    mock_calendar.create_event.return_value = {
        "id": "evt_002",
        "htmlLink": "https://calendar.google.com/event?eid=evt_002",
    }
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await create.callback(
        interaction,
        title="Quick Sync",
        when="2026-05-02 09:00",
    )

    mock_calendar.create_event.assert_called_once()
    mock_calendar.add_reminders.assert_not_called()


@pytest.mark.asyncio
async def test_create_handles_add_reminders_error_gracefully():
    """The /cal create command still shows the event confirmation even when
    add_reminders fails."""
    from src.commands.create import create

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 12345

    mock_calendar = MagicMock()
    mock_calendar.create_event.return_value = {
        "id": "evt_003",
        "htmlLink": "https://calendar.google.com/event?eid=evt_003",
    }
    http_resp = MagicMock()
    http_resp.status = 403
    mock_calendar.add_reminders.side_effect = HttpError(
        http_resp, b'{"error": "forbidden"}'
    )
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = "10"
    interaction.client.settings = mock_settings

    await create.callback(
        interaction,
        title="Test Event",
        when="2026-05-01 12:00",
    )

    mock_calendar.create_event.assert_called_once()
    mock_calendar.add_reminders.assert_called_once()
    # Confirmation should still be shown
    response_text = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Test Event" in response_text


# ── metadata ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reminders_set_has_correct_metadata():
    """The reminders set command has correct metadata."""
    from src.commands.reminders import reminders_set

    assert reminders_set.name == "set"
    assert "reminder" in reminders_set.description.lower()


@pytest.mark.asyncio
async def test_reminders_show_has_correct_metadata():
    """The reminders show command has correct metadata."""
    from src.commands.reminders import reminders_show

    assert reminders_show.name == "show"


@pytest.mark.asyncio
async def test_reminders_group_has_correct_name():
    """The reminders group is named 'reminders'."""
    from src.commands.reminders import reminders_group

    assert reminders_group.name == "reminders"


@pytest.mark.asyncio
async def test_reminders_defaults_group_has_correct_name():
    """The reminders-defaults group is named 'reminders-defaults'."""
    from src.commands.reminders import reminders_defaults_group

    assert reminders_defaults_group.name == "reminders-defaults"


@pytest.mark.asyncio
async def test_reminders_defaults_set_has_correct_metadata():
    """The reminders-defaults set command has correct metadata."""
    from src.commands.reminders import reminders_defaults_set

    assert reminders_defaults_set.name == "set"
    assert "reminder" in reminders_defaults_set.description.lower()


@pytest.mark.asyncio
async def test_reminders_defaults_show_has_correct_metadata():
    """The reminders-defaults show command has correct metadata."""
    from src.commands.reminders import reminders_defaults_show

    assert reminders_defaults_show.name == "show"
