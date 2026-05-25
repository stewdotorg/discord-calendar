"""UI components — PostToChannelView for ephemeral-to-public republishing.

PostToChannelView attaches a "Post to channel" button to ephemeral command
responses.  When clicked, the bot republishes the same content + embeds as
a normal public message and disables the button.
"""

import logging

import discord

logger = logging.getLogger(__name__)


class PostToChannelView(discord.ui.View):
    """View with a single "Post to channel" button.

    When clicked, the bot reads the original ephemeral message's content and
    embeds and republishes them as a non-ephemeral message in the same channel.
    The button is then disabled and relabelled "✓ Posted".

    Parameters
    ----------
    posted_view : discord.ui.View | None
        An optional View to attach to the posted public message (e.g. an
        RsvpView so the RSVP button appears only on the public copy, not
        the ephemeral confirmation).
    """

    def __init__(self, posted_view: discord.ui.View | None = None) -> None:
        super().__init__(timeout=300)  # 5 minutes to decide
        self._posted_view = posted_view

    @discord.ui.button(
        label="Post to channel",
        style=discord.ButtonStyle.secondary,
        emoji="📢",
    )
    async def post(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Republish the ephemeral message as a public channel message."""
        # Build kwargs for channel.send from the original message
        kwargs: dict = {}

        if interaction.message is None:
            # Message was deleted – nothing to republish.  Still disable the
            # button so the user knows the action was handled.
            button.disabled = True
            button.label = "✓ Posted"
            try:
                await interaction.response.edit_message(view=self)
            except discord.HTTPException:
                logger.warning(
                    "Could not edit PostToChannel message (likely deleted)"
                )
            return

        if interaction.message.content:
            kwargs["content"] = interaction.message.content
        if interaction.message.embeds:
            kwargs["embeds"] = interaction.message.embeds
        if self._posted_view is not None:
            kwargs["view"] = self._posted_view

        try:
            await interaction.channel.send(**kwargs)
        except (discord.Forbidden, discord.HTTPException) as exc:
            # Permission errors or HTTP failures — log but don't crash.
            logger.warning(
                "Failed to republish ephemeral message to channel: %s", exc
            )

        # Disable the button regardless of whether the post succeeded,
        # so the user doesn't keep clicking.
        button.disabled = True
        button.label = "✓ Posted"
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            logger.warning(
                "Could not edit PostToChannel message after post (likely deleted)"
            )
