# Commands

## Command → file map

All commands register on the `cal` group (defined in `src/commands/list_events.py`). `src/bot.py` imports each module for its registration side effect, so a new command module must be imported there.

| Command | File | Notes |
|---|---|---|
| `/cal ping` | `src/commands/ping.py` | Connectivity check |
| `/cal create` | `src/commands/create.py` | NLP `when` (incl. ranges like `2-4pm`), optional `invite:`, applies default reminders |
| `/cal show` | `src/commands/show.py` | Current event details + Post-to-channel (posts with RSVP button). For re-advertising. |
| `/cal edit` | `src/commands/edit.py` | Patch title/when/duration/description |
| `/cal delete` | `src/commands/delete.py` | |
| `/cal today`, `/cal week`, `/cal list` | `src/commands/list_events.py` | |
| `/cal invite` | `src/commands/rsvp.py` | Mixed `me` / @mention / email, space- or comma-separated (`split_invitees`) |
| `/cal settings set|show` | `src/commands/settings.py` | `setting:` choice of `email` / `timezone` |
| `/cal reminders set|show`, `/cal reminders-defaults set|show` | `src/commands/reminders.py` | |
| `/cal help` | `src/commands/help.py` | Static `_COMMANDS` list. Update it when adding a command (`test_commands.py` checks it). |

Event pickers (`event:` option) use `event_autocomplete` in `src/commands/autocomplete.py`, which looks ahead `AUTOCOMPLETE_LOOKAHEAD_DAYS`.

## Interaction patterns

- **Ephemeral first, then "Post to channel".** Commands reply ephemerally with `PostToChannelView`. `post_content` overrides what gets posted, so action lines like "✅ Event created!" and warnings stay private. `posted_view` attaches a view (e.g. `RsvpView`) only to the public copy.
- **RSVP button** ("📅 Email me a calendar invite", `custom_id="rsvp:<event_id>"`). With an email on file, it adds the user directly. Without one, it opens `EmailModal`, which saves the email and adds them.
- **DM email flow.** When an @mentioned invitee has no email, `send_pending_invites_to_unresolvable` DMs them and stores a pending invite. `DiscalClient.on_message` → `handle_dm_reply` saves the replied email and adds them. Requires `DISCORD_ENABLE_MESSAGE_CONTENT=true`.

## Gotchas

- **RSVP clicks are handled twice.** A live `RsvpView` callback and `DiscalClient.on_interaction` both handle `rsvp:` clicks on posts made since the last restart, so the second response logs `Interaction has already been acknowledged` (40060). The user still sees the right result. The fix is a single path (e.g. a `discord.ui.DynamicItem`).
- **Mentions must be standalone tokens.** `_MENTION_PATTERN` is anchored (`^<@!?\d+>$`). Always split input with `split_invitees` before resolving.
- **Discord client caches command schemas.** If changed commands don't appear, kick and re-invite the bot (see [deploying](deploying.md)).
