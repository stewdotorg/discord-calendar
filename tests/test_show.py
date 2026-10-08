"""Tests for /cal show — re-advertise an existing event."""

from unittest.mock import AsyncMock, MagicMock

import httplib2
import pytest
from googleapiclient.errors import HttpError

from src.commands.rsvp import RsvpView
from src.commands.show import show
from src.views import PostToChannelView


def _interaction(event: dict | None = None, error: HttpError | None = None):
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    if error is not None:
        mock_calendar.get_event.side_effect = error
    else:
        mock_calendar.get_event.return_value = event
    interaction.client.calendar = mock_calendar

    mock_settings = MagicMock()
    mock_settings.get.return_value = None  # default timezone (Eastern)
    interaction.client.settings = mock_settings
    return interaction


_EVENT = {
    "id": "evt1",
    "summary": "Team Sync",
    "start": {"dateTime": "2026-05-01T14:00:00-04:00"},
    "end": {"dateTime": "2026-05-01T14:30:00-04:00"},
    "htmlLink": "https://calendar.google.com/event?eid=evt1",
    "description": "Weekly standup",
}


@pytest.mark.asyncio
async def test_show_renders_current_event_details():
    """show renders the same details block /cal create posts, from live data."""
    interaction = _interaction(_EVENT)

    await show.callback(interaction, event_id="evt1")

    interaction.client.calendar.get_event.assert_called_once_with("evt1")
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert content == (
        "**Team Sync**\n"
        "📅 May 1, 2026 at 2:00 PM ET  (30 min)\n"
        "[Open in Google Calendar](https://calendar.google.com/event?eid=evt1)\n"
        "📝 Weekly standup"
    )


@pytest.mark.asyncio
async def test_show_offers_post_to_channel_with_rsvp_button():
    """show is ephemeral with a Post-to-channel button that posts with RSVP."""
    interaction = _interaction(_EVENT)

    await show.callback(interaction, event_id="evt1")

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    view = interaction.edit_original_response.call_args.kwargs["view"]
    assert isinstance(view, PostToChannelView)
    assert isinstance(view._posted_view, RsvpView)
    assert view._posted_view._event_id == "evt1"
    assert view._post_content.startswith("**Team Sync**")


@pytest.mark.asyncio
async def test_show_without_description_omits_description_line():
    """show omits the 📝 line when the event has no description."""
    event = {k: v for k, v in _EVENT.items() if k != "description"}
    interaction = _interaction(event)

    await show.callback(interaction, event_id="evt1")

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "📝" not in content


@pytest.mark.asyncio
async def test_show_all_day_event():
    """show renders all-day events (date only) without a time or duration."""
    event = {
        "id": "evt2",
        "summary": "Offsite",
        "start": {"date": "2026-05-01"},
        "end": {"date": "2026-05-02"},
        "htmlLink": "https://calendar.google.com/event?eid=evt2",
    }
    interaction = _interaction(event)

    await show.callback(interaction, event_id="evt2")

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "📅 May 1, 2026 (all day)" in content


@pytest.mark.asyncio
async def test_show_event_not_found():
    """show reports a missing event and offers no RSVP post."""
    resp = httplib2.Response({"status": 404})
    interaction = _interaction(error=HttpError(resp, b"not found"))

    await show.callback(interaction, event_id="gone")

    kwargs = interaction.edit_original_response.call_args.kwargs
    assert "not found" in kwargs["content"].lower()
    assert kwargs["view"]._posted_view is None


@pytest.mark.asyncio
async def test_show_calendar_not_configured():
    """show reports a missing calendar without deferring."""
    interaction = _interaction(_EVENT)
    interaction.client.calendar = None

    await show.callback(interaction, event_id="evt1")

    interaction.response.send_message.assert_awaited_once()
    assert "not configured" in interaction.response.send_message.call_args.args[0]
