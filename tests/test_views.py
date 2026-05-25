"""Tests for PostToChannelView component."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest


# ── PostToChannelView ────────────────────────────────────────────────────────


class TestPostToChannelView:
    """Tests for the PostToChannelView component."""

    def test_button_has_correct_label_and_style(self):
        """The PostToChannelView has a 'Post to channel' button with
        secondary style and 📢 emoji."""
        from src.views import PostToChannelView

        view = PostToChannelView()
        assert len(view.children) == 1
        button = view.children[0]
        assert button.label == "Post to channel"
        assert button.style == discord.ButtonStyle.secondary
        assert button.emoji.name == "📢"

    def test_timeout_is_5_minutes(self):
        """PostToChannelView times out after 300 seconds (5 minutes)."""
        from src.views import PostToChannelView

        view = PostToChannelView()
        assert view.timeout == 300

    @pytest.mark.asyncio
    async def test_post_button_sends_content_to_channel(self):
        """Clicking the Post button sends the original ephemeral message
        content as a public channel message via interaction.response.send_message."""
        from src.views import PostToChannelView

        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.edit_message = AsyncMock()

        # Simulate the original ephemeral message
        mock_message = MagicMock()
        mock_message.content = "✅ Event created!"
        mock_message.embeds = []
        interaction.message = mock_message

        view = PostToChannelView()
        button = view.children[0]
        await button.callback(interaction)

        # Should send content via interaction.response.send_message
        interaction.response.send_message.assert_called_once_with(
            content="✅ Event created!"
        )
        # Button should be disabled
        interaction.followup.edit_message.assert_called_once()
        updated_view = interaction.followup.edit_message.call_args.kwargs["view"]
        assert updated_view.children[0].disabled is True
        assert updated_view.children[0].label == "✓ Posted"

    @pytest.mark.asyncio
    async def test_post_button_sends_embeds_to_channel(self):
        """Clicking the Post button sends embeds from the original message."""
        from src.views import PostToChannelView

        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.edit_message = AsyncMock()

        embed = discord.Embed(title="Today's Events")
        mock_message = MagicMock()
        mock_message.content = ""
        mock_message.embeds = [embed]
        interaction.message = mock_message

        view = PostToChannelView()
        button = view.children[0]
        await button.callback(interaction)

        interaction.response.send_message.assert_called_once_with(embeds=[embed])

    @pytest.mark.asyncio
    async def test_post_button_sends_both_content_and_embeds(self):
        """Post button sends both content and embeds when both are present."""
        from src.views import PostToChannelView

        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.edit_message = AsyncMock()

        embed = discord.Embed(title="Events")
        mock_message = MagicMock()
        mock_message.content = "Here are your events:"
        mock_message.embeds = [embed]
        interaction.message = mock_message

        view = PostToChannelView()
        button = view.children[0]
        await button.callback(interaction)

        interaction.response.send_message.assert_called_once_with(
            content="Here are your events:", embeds=[embed]
        )

    @pytest.mark.asyncio
    async def test_post_button_with_posted_view(self):
        """When constructed with a posted_view, it is attached to the
        public channel message."""
        from src.views import PostToChannelView

        posted_view = discord.ui.View()
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.edit_message = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = "✅ Event created!"
        mock_message.embeds = []
        interaction.message = mock_message

        view = PostToChannelView(posted_view=posted_view)
        button = view.children[0]
        await button.callback(interaction)

        interaction.response.send_message.assert_called_once_with(
            content="✅ Event created!", view=posted_view
        )

    @pytest.mark.asyncio
    async def test_post_content_overrides_message_content(self):
        """When constructed with post_content, the posted message uses
        that content instead of the ephemeral message's content."""
        from src.views import PostToChannelView

        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.edit_message = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = "✅ Event created!\n**Team Sync**\n📅 May 1, 2026"
        mock_message.embeds = []
        interaction.message = mock_message

        view = PostToChannelView(post_content="**Team Sync**\n📅 May 1, 2026")
        button = view.children[0]
        await button.callback(interaction)

        interaction.response.send_message.assert_called_once_with(
            content="**Team Sync**\n📅 May 1, 2026"
        )

    @pytest.mark.asyncio
    async def test_post_content_empty_string_suppresses_content(self):
        """When post_content is an empty string, the posted message has
        no content (only embeds, if any)."""
        from src.views import PostToChannelView

        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.edit_message = AsyncMock()

        embed = discord.Embed(title="Events")
        mock_message = MagicMock()
        mock_message.content = "🗑️ **Test** deleted on May 1, 2026."
        mock_message.embeds = [embed]
        interaction.message = mock_message

        view = PostToChannelView(post_content="")
        button = view.children[0]
        await button.callback(interaction)

        # Content is suppressed, but embeds are preserved
        interaction.response.send_message.assert_called_once_with(embeds=[embed])

    @pytest.mark.asyncio
    async def test_post_button_disable_after_post(self):
        """After posting, the button is disabled and label changes to '✓ Posted'."""
        from src.views import PostToChannelView

        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.edit_message = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = "test"
        mock_message.embeds = []
        interaction.message = mock_message

        view = PostToChannelView()
        button = view.children[0]
        await button.callback(interaction)

        # Button should be disabled in the view passed to edit_message
        edit_kwargs = interaction.followup.edit_message.call_args.kwargs
        updated_view = edit_kwargs["view"]
        assert updated_view.children[0].disabled is True
        assert updated_view.children[0].label == "✓ Posted"

    @pytest.mark.asyncio
    async def test_post_button_handles_message_deleted(self):
        """If the original message was deleted, interaction.message is None
        and the button handles it gracefully."""
        from src.views import PostToChannelView

        interaction = MagicMock()
        interaction.response.defer = AsyncMock()

        # Simulate deleted message — message is None
        interaction.message = None

        view = PostToChannelView()
        button = view.children[0]

        # Should not raise
        await button.callback(interaction)

        # Should NOT try to post (no message to read)
        interaction.response.defer.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_button_handles_permission_error(self):
        """If the bot lacks permission to post in the channel, the error
        is caught gracefully and the button interaction is deferred."""
        from src.views import PostToChannelView

        interaction = MagicMock()
        interaction.response.send_message = AsyncMock(
            side_effect=discord.Forbidden(
                MagicMock(), "Missing permissions"
            )
        )
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.edit_message = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = "test"
        mock_message.embeds = []
        interaction.message = mock_message

        view = PostToChannelView()
        button = view.children[0]

        # Should not raise — catches the error
        await button.callback(interaction)

        # Should defer the interaction gracefully (button not disabled)
        interaction.response.defer.assert_called_once()
        interaction.followup.edit_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_button_handles_http_exception(self):
        """If posting fails with an HTTPException, the error is caught
        gracefully and the button interaction is deferred."""
        from src.views import PostToChannelView

        interaction = MagicMock()
        interaction.response.send_message = AsyncMock(
            side_effect=discord.HTTPException(
                MagicMock(), "Failed"
            )
        )
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.edit_message = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = "test"
        mock_message.embeds = []
        interaction.message = mock_message

        view = PostToChannelView()
        button = view.children[0]

        # Should not raise
        await button.callback(interaction)

        # Should defer the interaction gracefully (button not disabled)
        interaction.response.defer.assert_called_once()
        interaction.followup.edit_message.assert_not_called()
