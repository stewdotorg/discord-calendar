# MVP GitHub Issues — Phase 4 Ready

Create each issue below on `stewdotorg/discord-calendar` with label `ready-for-agent`.

---

## Issue #1: `/cal ping` — bot responds "pong"

**Depends on:** nothing

**Tracer Bullet:** Prove Discord connectivity end-to-end: register a slash command, handle the interaction, respond.

**Acceptance Criteria:**
- `/cal ping` registers as a global slash command
- Running `/cal ping` in Discord returns ephemeral message "pong"
- Bot starts up, connects to Discord, and logs "Ready"

**Technical Notes:**
- Use discord.py `app_commands.CommandTree`
- No Google Calendar dependency yet
- No database dependency yet
- Interactions Endpoint URL must be reachable (use cloudflared tunnel for local dev)
- Verify Ed25519 signature on incoming interactions per Discord docs

**Files Likely Touched:**
- `src/bot.py` — Discord client, command registration
- `src/commands/ping.py` — ping command handler
- `.env.example` — DISCORD_TOKEN, GUILD_ID
- `requirements.txt` — discord.py

**Test Approach:**
- Integration test: start bot, send mock interaction, assert response
- Mock Discord HTTP layer at boundary
- Test Ed25519 verification with known key pairs

---

## Issue #2: Google Calendar auth — service account connection

**Depends on:** #1 (need bot running to verify auth at startup)

**Tracer Bullet:** Bot loads service account credentials and verifies it can reach the target calendar.

**Acceptance Criteria:**
- Bot loads service account JSON key from path specified in `.env`
- On startup, bot calls `calendar.calendarList.get(calendarId=...)` to verify access
- On success: logs "Calendar connected: {summary}"
- On failure: logs clear error message and exits
- `.env.example` documents `GOOGLE_SERVICE_ACCOUNT_FILE` and `GOOGLE_CALENDAR_ID`

**Technical Notes:**
- Use `google-auth` + `google-api-python-client`
- Service account JSON key file path from `.env`
- Calendar ID from `.env`
- The target calendar must already be shared with the service account email
- Write `src/calendar/auth.py` and `src/calendar/service.py` (stub with at least `verify_access()`)

**Files Likely Touched:**
- `src/calendar/auth.py` — credential loading
- `src/calendar/service.py` — CalendarService class with `verify_access()`
- `src/bot.py` — call verify_access on startup
- `.env.example` — GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_CALENDAR_ID
- `requirements.txt` — google-auth, google-api-python-client

**Test Approach:**
- Unit test: mock Google API client, assert verify_access returns True
- Unit test: assert missing credentials raises clear error
- Integration test against a real test calendar (optional for this issue)

---

## Issue #3: `/cal create` — create event in Google Calendar

**Depends on:** #2 (needs working CalendarService)

**Tracer Bullet:** User runs `/cal create`, event appears in Google Calendar. Proves the Discord → Calendar pipeline.

**Acceptance Criteria:**
- `/cal create title:"Team Sync" date:2026-05-01 time:14:00` creates a Google Calendar event
- Optional `duration:` argument (default 60 minutes if unset)
- Optional `description:` argument
- Bot responds with confirmation including event date/time and a link to the Google Calendar event
- Events are created in the configured calendar
- Discord user ID written to `extendedProperties.private.createdBy`

**Technical Notes:**
- Discord slash command options: `title` (str, required), `date` (str, required), `time` (str, required), `duration` (int, optional, default 60), `description` (str, optional)
- `CalendarService.create_event()` implementation
- Return Google Calendar event ID and htmlLink
- Handle API errors with specific messages (permission denied, calendar not found, rate limited)

**Files Likely Touched:**
- `src/calendar/service.py` — implement `create_event()`
- `src/commands/create.py` — command handler
- `src/utils.py` — error formatting helpers

**Test Approach:**
- Integration test: create event against test calendar, assert it exists, then clean up
- Unit test: mock CalendarService, assert correct API call structure
- Test: duration defaults to 60 when not provided
- Test: error response when API call fails

---

## Issue #4: `/cal today` — list today's events

**Depends on:** #2 (needs working CalendarService)

**Tracer Bullet:** User runs `/cal today`, sees today's events from Google Calendar.

**Acceptance Criteria:**
- `/cal today` lists all events occurring today in the shared calendar
- Response is a Discord embed with: title, start time (in user's timezone, falling back to US Eastern, then UTC), duration
- If no events today: "No events scheduled for today."
- Events ordered by start time
- Each event shows its Google Calendar link

**Technical Notes:**
- Use `CalendarService.list_events()` with timeMin = start of today, timeMax = end of today
- Timezone handling: use server default (US Eastern per design) for now — per-user timezone is a later issue
- Discord embed for formatted output per digest format decision
- Implement autocomplete infrastructure for future use (not used by `/cal today` itself, but sets pattern)

**Files Likely Touched:**
- `src/calendar/service.py` — implement `list_events()`
- `src/commands/list_events.py` — today/week/list command handlers
- `src/utils.py` — Discord embed formatting, UTC → US Eastern conversion

**Test Approach:**
- Integration test: create event via API, call list_events, assert event appears
- Unit test: mock list_events return, assert embed formatting
- Test: empty result returns "No events" message
- Test: events ordered correctly

---

## Issue #5: `/cal delete` — delete event from Google Calendar

**Depends on:** #3 (needs events to exist for testing + autocomplete picks from existing events)

**Tracer Bullet:** User picks an event and deletes it. Event vanishes from Google Calendar.

**Acceptance Criteria:**
- `/cal delete <event>` shows autocomplete of upcoming events (Discord autocomplete callback queries Google Calendar live)
- Selecting an event deletes it from Google Calendar
- Bot confirms deletion with event title and date
- If deletion fails: specific error message ("Event not found", "Calendar is unavailable")
- Google Calendar sends cancellation emails to any attendees automatically

**Technical Notes:**
- Implement Discord `@app_commands.autocomplete` decorator
- Autocomplete handler calls `CalendarService.list_events()` and filters by user's typed substring
- Autocomplete must respond within 3 seconds (list call should be fast)
- `CalendarService.delete_event()` implementation
- Silent delete — no confirmation prompt (open model)

**Files Likely Touched:**
- `src/calendar/service.py` — implement `delete_event()`
- `src/commands/delete.py` — command handler + autocomplete
- `src/utils.py` — autocomplete result formatting

**Test Approach:**
- Integration test: create event, delete it, assert it's gone
- Unit test: mock autocomplete list, assert correct events shown
- Unit test: mock delete failure, assert error message format
- Test: autocomplete truncates long event titles
