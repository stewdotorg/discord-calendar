"""DM invite handling — send pending-invite DMs and process DM replies."""

import datetime as dt_mod
import logging
from zoneinfo import ZoneInfo

import discord
from googleapiclient.errors import HttpError

from src.db.queries import SettingsStore
from src.calendar.service import CalendarService
from src.utils import DEFAULT_TIMEZONE, format_datetime_eastern, validate_email

logger = logging.getLogger(__name__)

# ── DM sending ───────────────────────────────────────────────────────────────


async def send_pending_invite_dm(
    user: discord.User,
    event_id: str,
    event_title: str,
    event_start: str,
    event_html_link: str,
    inviter_name: str,
    inviter_id: str,
    settings_store: SettingsStore,
) -> bool:
    """DM a user to ask for their email to complete an invite.

    Stores a pending invite in the database so that when the user replies
    with their email, the bot can add them to the event.

    Returns ``True`` on success, ``False`` if the DM could not be sent
    (e.g. the user has DMs disabled).
    """
    user_id = str(user.id)

    # Resolve receiver's timezone
    tz_str = settings_store.get(user_id, "timezone")
    try:
        tz = ZoneInfo(tz_str) if tz_str else DEFAULT_TIMEZONE
    except (KeyError, ValueError, TypeError):
        tz = DEFAULT_TIMEZONE

    # Format the event date/time in the receiver's timezone
    try:
        start_dt = dt_mod.datetime.fromisoformat(event_start)
    except ValueError:
        start_dt = dt_mod.datetime.now(dt_mod.timezone.utc)
    date_fmt = format_datetime_eastern(start_dt, tz=tz)

    msg = (
        f"👋 **{inviter_name}** invited you to "
        f"**[{event_title}]({event_html_link})** "
        f"({date_fmt}).\n\n"
        f"Reply with your email to join."
    )

    try:
        await user.send(msg)
    except discord.Forbidden:
        logger.warning(
            "Cannot DM user %s (DMs disabled) for pending invite to event %s",
            user_id, event_id,
        )
        return False

    # Store the pending invite
    now_iso = dt_mod.datetime.now(dt_mod.timezone.utc).isoformat()
    settings_store.insert_pending_invite(user_id, event_id, inviter_id, now_iso)
    logger.info(
        "Sent pending-invite DM to user %s for event %s by inviter %s",
        user_id, event_id, inviter_id,
    )
    return True


async def send_pending_invites_to_unresolvable(
    client: discord.Client,
    unresolvable_ids: set[str],
    inviter: discord.User,
    event_id: str,
    event_title: str,
    event_start: str,
    event_html_link: str,
    settings_store: SettingsStore,
) -> None:
    """Send pending-invite DMs to every unresolvable mention.

    Fetches each Discord user by ID and sends them a DM asking for
    their email.  Users that can't be found or can't receive DMs are
    skipped with a warning log.
    """
    for discord_id in unresolvable_ids:
        try:
            user = await client.fetch_user(int(discord_id))
            await send_pending_invite_dm(
                user=user,
                event_id=event_id,
                event_title=event_title,
                event_start=event_start,
                event_html_link=event_html_link,
                inviter_name=inviter.name,
                inviter_id=str(inviter.id),
                settings_store=settings_store,
            )
        except discord.NotFound:
            logger.warning(
                "Could not find Discord user %s for pending invite DM",
                discord_id,
            )
        except Exception:
            logger.warning(
                "Failed to DM user %s for pending invite",
                discord_id, exc_info=True,
            )


# ── DM reply handling ────────────────────────────────────────────────────────


async def handle_dm_reply(
    message: discord.Message,
    settings_store: SettingsStore,
    calendar: CalendarService,
) -> bool:
    """Process a DM reply from a user with a pending invite.

    Returns ``True`` if the message was handled (a pending invite was found
    and processed), ``False`` if there was nothing to do (no pending invite).
    """
    user_id = str(message.author.id)

    pending = settings_store.get_pending_invite(user_id)
    if pending is None:
        return False

    event_id = pending["event_id"]

    # Check if the event still exists
    try:
        event = calendar.get_event(event_id)
    except HttpError:
        logger.warning("Event %s no longer exists for pending invite of user %s", event_id, user_id)
        await message.channel.send(
            "❌ That event no longer exists. The invite has been cancelled."
        )
        settings_store.delete_pending_invite(user_id)
        return True

    event_title = event.get("summary", "Untitled Event")
    event_html_link = event.get("htmlLink", "")

    # Check if user already has an email stored
    stored_email = settings_store.get(user_id, "email")
    if stored_email:
        # Use the stored email, not the reply text
        email = stored_email
    else:
        reply_text = message.content.strip()
        # Check if the reply looks like an email attempt (contains @)
        if "@" not in reply_text:
            # Not an email attempt — silently ignore
            return True
        # Validate email format
        error = validate_email(reply_text)
        if error:
            await message.channel.send(
                "That doesn't look like a valid email. "
                "Try again, e.g. you@example.com."
            )
            return True
        email = reply_text

    # Save the email (only if not already stored)
    if not stored_email:
        settings_store.set(user_id, "email", email)

    # Add the attendee
    try:
        calendar.add_attendees(event_id, [email])
    except HttpError as exc:
        logger.error("Failed to add attendee %s to event %s: %s", user_id, event_id, exc)
        await message.channel.send(
            "❌ Couldn't add you to the event. The calendar returned an error."
        )
        # Still clean up the pending invite — it's been processed
        settings_store.delete_pending_invite(user_id)
        return True

    # Confirm
    response = f"✅ You have been added to **{event_title}**!"
    if event_html_link:
        response += f"\n[Open in Google Calendar]({event_html_link})"
    await message.channel.send(response)

    # Clean up the pending invite
    settings_store.delete_pending_invite(user_id)
    return True
