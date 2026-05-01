"""Tests for slash command handlers."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.commands.ping import ping


@pytest.mark.asyncio
async def test_ping_responds_pong_ephemerally():
    """The /cal ping command responds with 'pong' as an ephemeral message."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    await ping.callback(interaction)

    interaction.response.send_message.assert_called_once_with(
        "pong", ephemeral=True
    )


@pytest.mark.asyncio
async def test_ping_command_has_correct_metadata():
    """The ping command is named 'ping' with appropriate description."""
    assert ping.name == "ping"
    assert ping.description == "Ping the bot"


# ── /cal today ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_today_command_lists_events():
    """The /cal today command responds with an embed listing today's events."""
    from src.commands.list_events import today

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    # Mock the calendar service on the client
    mock_calendar = MagicMock()
    mock_calendar.list_events.return_value = [
        {
            "summary": "Team Sync",
            "start": {"dateTime": "2026-04-28T10:00:00-04:00"},
            "end": {"dateTime": "2026-04-28T11:00:00-04:00"},
            "htmlLink": "https://calendar.google.com/event?eid=evt1",
        }
    ]
    interaction.client.calendar = mock_calendar

    with patch("src.commands.list_events.get_today_eastern_range") as mock_range:
        tmin = datetime.datetime(2026, 4, 28, 4, 0, 0, tzinfo=datetime.timezone.utc)
        tmax = datetime.datetime(2026, 4, 29, 4, 0, 0, tzinfo=datetime.timezone.utc)
        mock_range.return_value = (tmin, tmax)

        with patch("src.commands.list_events.format_events_embed") as mock_fmt:
            mock_embed = MagicMock()
            mock_fmt.return_value = mock_embed

            await today.callback(interaction)

            mock_calendar.list_events.assert_called_once_with(
                time_min=tmin, time_max=tmax, q=None
            )

            interaction.response.send_message.assert_called_once_with(
                embed=mock_embed
            )


@pytest.mark.asyncio
async def test_today_command_calendar_not_configured():
    """The /cal today command responds with an error when calendar is not configured."""
    from src.commands.list_events import today

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await today.callback(interaction)

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "not configured" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_today_command_has_correct_metadata():
    """The today command is named 'today' under the 'cal' group."""
    from src.commands.list_events import today

    assert today.name == "today"
    assert today.description == "List today's events"


# ── /cal help ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_help_command_responds_ephemeral_embed():
    """The /cal help command responds with an ephemeral embed listing commands."""
    from src.commands.help import help_cmd

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    await help_cmd.callback(interaction)

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    _, kwargs = call_args
    assert kwargs["ephemeral"] is True
    assert kwargs["embed"] is not None


@pytest.mark.asyncio
async def test_help_embed_contains_all_commands():
    """The help embed includes ping, create, today, delete, and help."""
    from src.commands.help import help_cmd

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    await help_cmd.callback(interaction)

    call_args = interaction.response.send_message.call_args
    embed = call_args[1]["embed"]

    # All five commands should appear as fields
    field_names = [field.name for field in embed.fields]
    assert "/cal ping" in field_names
    assert "/cal create" in field_names
    assert "/cal today" in field_names
    assert "/cal delete" in field_names
    assert "/cal help" in field_names
    assert len(embed.fields) >= 5


@pytest.mark.asyncio
async def test_help_embed_each_field_has_description_and_example():
    """Each help field contains a description and a usage example."""
    from src.commands.help import help_cmd

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    await help_cmd.callback(interaction)

    call_args = interaction.response.send_message.call_args
    embed = call_args[1]["embed"]

    for field in embed.fields:
        assert field.value, f"Field '{field.name}' has no value"
        # Should contain both a description line and an example line
        assert "Example:" in field.value, (
            f"Field '{field.name}' missing 'Example:' label"
        )


@pytest.mark.asyncio
async def test_help_command_has_correct_metadata():
    """The help command is named 'help' under the 'cal' group."""
    from src.commands.help import help_cmd

    assert help_cmd.name == "help"
    assert help_cmd.description == "Show all available calendar commands"


# ── /cal week ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_week_command_lists_events_for_next_7_days():
    """The /cal week command lists events from today through the next 7 days."""
    from src.commands.list_events import week

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.list_events.return_value = [
        {
            "summary": "Team Sync",
            "start": {"dateTime": "2026-05-01T10:00:00-04:00"},
            "end": {"dateTime": "2026-05-01T11:00:00-04:00"},
            "htmlLink": "https://calendar.google.com/event?eid=evt1",
        }
    ]
    interaction.client.calendar = mock_calendar

    tmin = datetime.datetime(2026, 5, 1, 4, 0, 0, tzinfo=datetime.timezone.utc)
    tmax = datetime.datetime(2026, 5, 8, 4, 0, 0, tzinfo=datetime.timezone.utc)

    with patch("src.commands.list_events.get_today_eastern_range") as mock_today_range:
        mock_today_range.return_value = (tmin, tmin + datetime.timedelta(days=1))

        with patch("src.commands.list_events.format_events_embed") as mock_fmt:
            mock_embed = MagicMock()
            mock_fmt.return_value = mock_embed

            await week.callback(interaction)

            mock_calendar.list_events.assert_called_once_with(
                time_min=tmin, time_max=tmax, q=None
            )

            interaction.response.send_message.assert_called_once_with(
                embed=mock_embed
            )


@pytest.mark.asyncio
async def test_week_command_calendar_not_configured():
    """The /cal week command responds with an error when calendar is not configured."""
    from src.commands.list_events import week

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await week.callback(interaction)

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "not configured" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_week_command_has_correct_metadata():
    """The week command is named 'week' under the 'cal' group."""
    from src.commands.list_events import week

    assert week.name == "week"
    assert week.description == "List events for the next 7 days"


# ── /cal list ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_command_lists_events_for_date_range():
    """The /cal list command lists events in the given date range."""
    from src.commands.list_events import list_events

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.list_events.return_value = [
        {
            "summary": "Team Sync",
            "start": {"dateTime": "2026-05-01T10:00:00-04:00"},
            "end": {"dateTime": "2026-05-01T11:00:00-04:00"},
            "htmlLink": "https://calendar.google.com/event?eid=evt1",
        }
    ]
    interaction.client.calendar = mock_calendar

    tmin = datetime.datetime(2026, 5, 1, 4, 0, 0, tzinfo=datetime.timezone.utc)
    tmax = datetime.datetime(2026, 5, 5, 4, 0, 0, tzinfo=datetime.timezone.utc)

    with patch("src.commands.list_events.parse_date_eastern") as mock_parse:
        mock_parse.side_effect = [tmin, tmax]

        with patch("src.commands.list_events.format_events_embed") as mock_fmt:
            mock_embed = MagicMock()
            mock_fmt.return_value = mock_embed

            await list_events.callback(interaction, from_="2026-05-01", to="2026-05-05")

            mock_calendar.list_events.assert_called_once_with(
                time_min=tmin, time_max=tmax, q=None
            )

            interaction.response.send_message.assert_called_once_with(
                embed=mock_embed
            )


@pytest.mark.asyncio
async def test_list_command_with_search_keyword():
    """The /cal list command passes the search keyword to list_events."""
    from src.commands.list_events import list_events

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.list_events.return_value = []
    interaction.client.calendar = mock_calendar

    tmin = datetime.datetime(2026, 5, 1, 4, 0, 0, tzinfo=datetime.timezone.utc)
    tmax = datetime.datetime(2026, 5, 5, 4, 0, 0, tzinfo=datetime.timezone.utc)

    with patch("src.commands.list_events.parse_date_eastern") as mock_parse:
        mock_parse.side_effect = [tmin, tmax]

        with patch("src.commands.list_events.format_events_embed") as mock_fmt:
            mock_embed = MagicMock()
            mock_fmt.return_value = mock_embed

            await list_events.callback(
                interaction, from_="2026-05-01", to="2026-05-05", search="standup"
            )

            mock_calendar.list_events.assert_called_once_with(
                time_min=tmin, time_max=tmax, q="standup"
            )


@pytest.mark.asyncio
async def test_list_command_calendar_not_configured():
    """The /cal list command responds with an error when calendar is not configured."""
    from src.commands.list_events import list_events

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await list_events.callback(interaction, from_="2026-05-01", to="2026-05-05")

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "not configured" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_list_command_invalid_date_returns_error():
    """The /cal list command returns a clear error for invalid date formats."""
    from src.commands.list_events import list_events

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar

    with patch("src.commands.list_events.parse_date_eastern") as mock_parse:
        mock_parse.side_effect = ValueError("Invalid date format")

        await list_events.callback(interaction, from_="not-a-date", to="2026-05-05")

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "Invalid date" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_list_command_has_correct_metadata():
    """The list command is named 'list' under the 'cal' group."""
    from src.commands.list_events import list_events

    assert list_events.name == "list"
    assert list_events.description == "List events in a date range"


@pytest.mark.asyncio
async def test_list_command_no_search_passes_none():
    """The /cal list command doesn't pass search when not provided."""
    from src.commands.list_events import list_events

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.list_events.return_value = []
    interaction.client.calendar = mock_calendar

    tmin = datetime.datetime(2026, 5, 1, 4, 0, 0, tzinfo=datetime.timezone.utc)
    tmax = datetime.datetime(2026, 5, 5, 4, 0, 0, tzinfo=datetime.timezone.utc)

    with patch("src.commands.list_events.parse_date_eastern") as mock_parse:
        mock_parse.side_effect = [tmin, tmax]

        with patch("src.commands.list_events.format_events_embed") as mock_fmt:
            mock_fmt.return_value = MagicMock()

            await list_events.callback(interaction, from_="2026-05-01", to="2026-05-05")

            call_kwargs = mock_calendar.list_events.call_args.kwargs
            assert call_kwargs["q"] is None


# ── /cal email ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_email_set_stores_and_confirms():
    """The /cal email set command stores the email and confirms."""
    from src.commands.settings import email_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await email_set.callback(interaction, email="me@example.com")

    mock_settings.set.assert_called_once_with("12345", "email", "me@example.com")
    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "me@example.com" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_email_set_invalid_email_returns_error():
    """The /cal email set command rejects invalid email formats."""
    from src.commands.settings import email_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await email_set.callback(interaction, email="not-an-email")

    mock_settings.set.assert_not_called()
    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "Invalid email" in call_args[0][0] or "invalid" in call_args[0][0].lower()
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_email_set_rejects_email_without_at():
    """The /cal email set rejects emails missing @."""
    from src.commands.settings import email_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await email_set.callback(interaction, email="noatsign.example.com")

    mock_settings.set.assert_not_called()
    call_args = interaction.response.send_message.call_args
    assert "Invalid" in call_args[0][0] or "invalid" in call_args[0][0].lower()
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_email_set_rejects_email_without_dot():
    """The /cal email set rejects emails missing a dot in the domain."""
    from src.commands.settings import email_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await email_set.callback(interaction, email="user@nodot")

    mock_settings.set.assert_not_called()
    call_args = interaction.response.send_message.call_args
    assert "Invalid" in call_args[0][0] or "invalid" in call_args[0][0].lower()
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_email_show_displays_stored_email():
    """The /cal email show command displays the stored email."""
    from src.commands.settings import email_show

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    mock_settings.get.return_value = "me@example.com"
    interaction.client.settings = mock_settings

    await email_show.callback(interaction)

    mock_settings.get.assert_called_once_with("12345", "email")
    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "me@example.com" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_email_show_no_email():
    """The /cal email show command shows a message when no email is set."""
    from src.commands.settings import email_show

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await email_show.callback(interaction)

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "No email" in call_args[0][0] or "not set" in call_args[0][0].lower()
    assert call_args[1]["ephemeral"] is True


# ── /cal timezone ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_timezone_set_stores_and_confirms():
    """The /cal timezone set command stores the timezone and confirms."""
    from src.commands.settings import timezone_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await timezone_set.callback(interaction, timezone="America/Chicago")

    mock_settings.set.assert_called_once_with("12345", "timezone", "America/Chicago")
    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "America/Chicago" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_timezone_set_rejects_invalid_timezone():
    """The /cal timezone set command rejects invalid timezone strings."""
    from src.commands.settings import timezone_set

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    interaction.client.settings = mock_settings

    await timezone_set.callback(interaction, timezone="Not/A_Real_Zone")

    mock_settings.set.assert_not_called()
    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "Invalid timezone" in call_args[0][0] or "invalid" in call_args[0][0].lower()
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_timezone_show_displays_stored_timezone():
    """The /cal timezone show command displays the stored timezone."""
    from src.commands.settings import timezone_show

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    mock_settings.get.return_value = "America/Chicago"
    interaction.client.settings = mock_settings

    await timezone_show.callback(interaction)

    mock_settings.get.assert_called_once_with("12345", "timezone")
    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "America/Chicago" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_timezone_show_default():
    """The /cal timezone show command shows default when none is set."""
    from src.commands.settings import timezone_show

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345

    mock_settings = MagicMock()
    mock_settings.get.return_value = None
    interaction.client.settings = mock_settings

    await timezone_show.callback(interaction)

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "US Eastern" in call_args[0][0] or "default" in call_args[0][0].lower()
    assert call_args[1]["ephemeral"] is True


# ── metadata for email/timezone commands ───────────────────────────────


@pytest.mark.asyncio
async def test_email_set_has_correct_metadata():
    """The email set command has correct metadata."""
    from src.commands.settings import email_set

    assert email_set.name == "set"
    assert "email" in email_set.description.lower()


@pytest.mark.asyncio
async def test_email_show_has_correct_metadata():
    """The email show command has correct metadata."""
    from src.commands.settings import email_show

    assert email_show.name == "show"


@pytest.mark.asyncio
async def test_timezone_set_has_correct_metadata():
    """The timezone set command has correct metadata."""
    from src.commands.settings import timezone_set

    assert timezone_set.name == "set"
    assert "timezone" in timezone_set.description.lower()


@pytest.mark.asyncio
async def test_timezone_show_has_correct_metadata():
    """The timezone show command has correct metadata."""
    from src.commands.settings import timezone_show

    assert timezone_show.name == "show"
