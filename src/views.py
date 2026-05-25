"""UI components — PostToChannelView for ephemeral-to-public republishing.

PostToChannelView attaches a "Post to channel" button to ephemeral command
responses. When clicked, the bot republishes the same content + embeds as
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
    post_content : str | None
        Optional override for the content of the posted message. If
        provided, this replaces the ephemeral message's content in the
        public copy. Used to strip action lines ("✅ Event created!")
        that only make sense in the ephemeral confirmation.
    """

    def __init__(
        self,
        posted_view: discord.ui.View | None = None,
        post_content: str | None = None,
    ) -> None:
        super().__init__(timeout=300)  # 5 minutes to decide
        self._posted_view = posted_view
        self._post_content = post_content

    @discord.ui.button(
        label="Post to channel",
        style=discord.ButtonStyle.secondary,
        emoji="📢",
    )
    async def post(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Republish the ephemeral message as a public channel message."""
        message = interaction.message

        if message is None:
            await interaction.response.defer()
            return

        kwargs: dict = {}
        if self._post_content is not None:
            if self._post_content:
                kwargs["content"] = self._post_content
        elif message.content:
            kwargs["content"] = message.content
        if message.embeds:
            kwargs["embeds"] = message.embeds
        if self._posted_view is not None:
            kwargs["view"] = self._posted_view

        # Respond to the button click with the public message.
        # Uses send_message (not channel.send) so no bot-member permission needed.
        try:
            await interaction.response.send_message(**kwargs)
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning(
                "Failed to republish ephemeral message to channel: %s", exc
            )
            await interaction.response.defer()
            return

        # Update the original ephemeral message to disable the button.
        button.disabled = True
        button.label = "✓ Posted"
        try:
            await interaction.followup.edit_message(
                message_id=message.id, view=self
            )
        except discord.HTTPException:
            logger.warning("Could not edit PostToChannel message (likely deleted)")
