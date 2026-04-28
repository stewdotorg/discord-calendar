# Discal — PRD

## Problem Statement

Discord communities that run events (standups, game nights, planning sessions) need a shared calendar. Existing bots either use their own local event storage (no Google Calendar integration) or read Discord's native scheduled events (no external calendar). Teams already use Google Calendar — the bot should write to it so events appear in everyone's existing calendar app.

## Solution

Discal — a Discord slash-command bot that reads and writes to a shared Google Calendar. Discord is the UI; Google Calendar is the source of truth.

## User Stories

- As a community member, I can create an event with a title, date, and time, and it appears on the shared Google Calendar.
- As a community member, I can list today's or this week's events.
- As a community member, I can delete an event I don't need anymore.
- As a community member, I can pick an event from a dropdown rather than typing an ID.
- As a community member, I can RSVP to an event with my email and get a Google Calendar invitation on my personal calendar.
- As a community member, I can invite others to an event by their email addresses.
- As a community member, I can set default reminders that fire before events, and override them per-event.
- As a community member, I can configure my timezone so event times display correctly.
- As a server admin, I can set up daily, weekly, or monthly digests that post upcoming events to a channel.
- As a community member, I can edit an event (change title, date, time, duration, description).
- As a community member, I can use natural language like "next tuesday at 3pm" instead of picking a date.
- As a community member, I can type `/cal help` to see all available commands.

## Non-Goals (Deferred)

- Multi-guild support (single server for initial release)
- Per-user calendar authentication (single shared calendar via service account)
- Recurring events
- Free/busy queries
- Creator-only edit/delete permissions (open model)
- Attendee count display in Discord embeds
- Custom date/time display formats (12h/24h, DD/MM vs MM/DD)

## Implementation Decisions

| Decision | Choice |
|---|---|
| Language | Python 3.12+ |
| Discord library | discord.py |
| Google API | google-api-python-client |
| Local storage | SQLite (Docker volume mount) |
| Natural language date parsing | dateparser |
| Scheduler | asyncio background loop |
| Calendar auth | Google service account (JSON key) |
| Calendar config | Hardcoded calendar ID in `.env` |
| Discord intents | None (HTTP-only slash commands) |
| Event selection | Discord autocomplete (live Google Calendar list query) |
| Reminder delivery | Google Calendar native notifications |
| Deploy | Manual (`git pull && docker compose up -d`) |
| Local dev | cloudflared tunnel |

## Architecture

```
discal/
  src/
    bot.py              # Main entry: client setup, command registration, lifecycle
    calendar/
      service.py        # Google Calendar CRUD: create_event(), list_events(), delete_event()
      auth.py           # Service account credential loading
    commands/
      ping.py           # /cal ping
      create.py         # /cal create
      list_events.py    # /cal today, /cal week, /cal list
      delete.py         # /cal delete
      edit.py           # /cal edit
      rsvp.py           # /cal rsvp, /cal invite
      reminders.py      # /cal reminders
      settings.py       # /cal settings (email, reminders, timezone)
      digest.py         # /cal digest
      help.py           # /cal help
    db/
      schema.py         # SQLite tables: user_settings, digest_configs
      queries.py        # CRUD for settings
    scheduler.py        # asyncio loop: channel reminders, digest posting, event cleanup
    utils.py            # autocomplete handlers, timezone formatting, error handling
  tests/
    test_calendar_service.py
    test_commands.py
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example
```

### Deep Module Interfaces

**`calendar/service.py`** — small interface, deep implementation:
```python
class CalendarService:
    def create_event(self, title: str, start: datetime, duration_minutes: int = 60,
                     description: str | None = None, attendees: list[str] | None = None,
                     reminders: list[int] | None = None,
                     creator_discord_id: str | None = None) -> str:
        """Create an event. Returns Google Calendar event ID."""

    def list_events(self, time_min: datetime, time_max: datetime,
                    q: str | None = None, max_results: int = 25) -> list[Event]:
        """List events in a time range."""

    def delete_event(self, event_id: str) -> None:
        """Delete an event. Sends cancellation to attendees."""

    def update_event(self, event_id: str, **kwargs) -> None:
        """Update event fields."""

    def add_attendees(self, event_id: str, emails: list[str]) -> None:
        """Add attendees to an event."""

    def add_reminders(self, event_id: str, minutes: list[int]) -> None:
        """Set reminders on an event."""
```

**`db/queries.py`** — settings persistence:
```python
class SettingsStore:
    def get_user_setting(self, discord_id: str, key: str) -> str | None: ...
    def set_user_setting(self, discord_id: str, key: str, value: str) -> None: ...
    def delete_user_setting(self, discord_id: str, key: str) -> None: ...
    def get_digest_configs(self, guild_id: str) -> list[DigestConfig]: ...
    def set_digest_config(self, config: DigestConfig) -> None: ...
    def delete_digest_config(self, guild_id: str, channel_id: str, period: str) -> None: ...
```

## Test Strategy

- TDD: Red-Green-Refactor for every issue
- Integration tests against a mock Google Calendar server (or test calendar)
- Public interface testing only — no mocking of internal collaborators
- Mock at system boundaries: Discord HTTP interactions, Google Calendar API
- `dateparser` tested with representative natural language strings
- Timezone logic tested with explicit UTC offsets

## MVP Kanban Board (First Night Shift)

| Issue | Title | Depends On |
|---|---|---|
| #1 | `/cal ping` — bot responds "pong" | — |
| #2 | Google Calendar auth — service account connection | #1 |
| #3 | `/cal create` — create event in Google Calendar | #2 |
| #4 | `/cal today` — list today's events | #2 |
| #5 | `/cal delete` — delete event from Google Calendar | #3 |
