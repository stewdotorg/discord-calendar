"""Tests for the Discord bot client setup."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot import DiscalClient
from src.commands.ping import ping


def test_bot_has_command_tree():
    """The DiscalClient initializes with an app_commands.CommandTree."""
    client = DiscalClient()
    assert client.tree is not None
    assert isinstance(client.tree, discord.app_commands.CommandTree)


def test_bot_has_no_message_content_intent():
    """The bot uses default intents only — no privileged intents needed."""
    client = DiscalClient()
    assert not client.intents.message_content
    assert not client.intents.members
    assert not client.intents.presences


@pytest.mark.asyncio
async def test_setup_hook_registers_ping_and_syncs():
    """setup_hook registers the ping command, syncs the command tree,
    and initialises the calendar."""
    client = DiscalClient()

    client.tree.add_command = MagicMock()
    client.tree.sync = AsyncMock()
    client._init_calendar = MagicMock(return_value=None)

    await client.setup_hook()

    client.tree.add_command.assert_called_once_with(ping)
    client.tree.sync.assert_called_once()
    client._init_calendar.assert_called_once()


# ── _init_calendar ───────────────────────────────────────────────────────────


class TestInitCalendar:
    """Tests for the DiscalClient._init_calendar method."""

    def test_returns_none_when_env_vars_unset(self, monkeypatch):
        """_init_calendar returns None when calendar env vars are empty."""
        monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
        monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)

        client = DiscalClient()
        result = client._init_calendar()

        assert result is None

    def test_returns_service_on_success(self, monkeypatch, tmp_path):
        """_init_calendar returns a CalendarService when auth succeeds."""
        key_file = tmp_path / "key.json"
        key_file.write_text(
            '{"type": "service_account", "project_id": "p",'
            ' "client_email": "x@x.iam.gserviceaccount.com",'
            ' "token_uri": "https://oauth2.googleapis.com/token",'
            ' "private_key": "-----BEGIN PRIVATE KEY-----\\n'
            'MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQDRPTiNfUy3C1hp\\n'
            'U29KCrCIKpXNi9QlC+yGoqe4YYshM2KU98iZd1VzUmSzl3z9l3fJDwpL+I0Mzy3j\\n'
            'sqkZuK2o+l8UTmnRUUCtYMWEkUBatSqCefMLETRbZKj5WAxLgfmfHhRIyj3+PQGL\\n'
            'guBd+1GzCGY+53aqgqDGj9e68YULMm1vhN3kMFO/AQCEaNzKMc9XUFRL70xFLOIT\\n'
            'deQnL1mxuDobMv1UDeX8/CUQTlv3Z4gRI0D2AatFs6636D4ARpaXgC+TD0Wgf+5n\\n'
            't+SDIl41Wzfvsme7tuppCNenqZlSry1yikYrAuJv+2+DZivG/E+wGA7d7SCZo/ck\\n'
            'x3+O4r0xAgMBAAECgf8Bowpc08iMHbDdzpfl2kzF2jDTNqbpK6F+EFFtfb+Zlayh\\n'
            'Jg8Xgt291QqoHQPL6imxjzsrpreEdk9UM9DolWMDn2ariaZfJHvub/3Nqv73+XnO\\n'
            'cRDrPvwUTm8GwY5y5JkQBOi+JkCfpDIwShUfm/cELXLnqxMEqtA/hcNWHBobkHn6\\n'
            'QzE5FWilICeaH0WNOngLbYv1pZgamj7y9EeoIL/XP+n57hI8jKi5Oz2LOAJwgRbn\\n'
            'BHsc8SvhMaUz5uNWNbRBefbGNA76yLPd7ZzZRZa0Iw3vNCajeBaMJWqS49qvKjS1\\n'
            'cadX6zp/+T05JQtq65xdUdGVS/urdnzCtJdV8OECgYEA8K1PU1vnkYv76PFBcg62\\n'
            'pIITLZqF+wMNerER0VZNLAmh9jCrzMuRYhnySZ9HdVGefo/ic80wvo4XitFmA+UP\\n'
            'o4xUkAIFSNwVcyE0Ujnn69RaC/iBFvHlIiVF9gdW/1E+McGXNAtk8bW8JJZNi4th\\n'
            'rHR0wPcTuo2ukoY3tNKSrRECgYEA3o+E6HDTiCQ0k6i7NI5QlrHLstGiXVFGZrLB\\n'
            'E5FJ4RDDVIlrOzVTU3E2D8r/YuriK1GKEkRgJTJrcV6PogZf6/wUvxedG+mRXTfh\\n'
            'iJiY8HmoQcNwDGAqOBUlpebs/ve0hRIobkFqXcLNBgB1LO3CxEm+mTK+3UrLbOGe\\n'
            '7LpLjiECgYBuHr4m4+wmWihewtQw/a5vwtxHh2Y6HYFzW8VNRPF2bsnePRK+V34j\\n'
            'pr+HFAu8ECY2vlrcpUviRF1dNMY6jfoD2NdwNJx6Y8ikrtKjtL761mSFCaT2/KLc\\n'
            'ZrWGBoG1vFR6q5slQvli5sY471R3vsRoBbjN+b7bIqx3elXOtHJMIQKBgHb8yBP1\\n'
            'bkJVCP8AsMWSaKeIet0pkuLNNxRk8TDi9lqruaKSrY/EHL55wmuDHjLmXPDH8Ud+\\n'
            '4uBAKo07/xKi0dm6teTMXSS1JRBvddavruSyRjCSqm8TYr8FH1GpOn++MvcKFC+O\\n'
            'La3fHfndeMgCfaSvwITrSnvJJyUZIvxxRT/BAoGAPmRj3AiEv4tBZaiB/FrpPGEo\\n'
            'RPZ21slNoYt//dkTUixnqn8iXP9fxZVfg291R+D1cayx02/IHAANN1bORKieWODv\\n'
            'ln22ArhfMT13kbnqrRZpNTHb+iZKz6Z+wa/BKw2+NJqg7PQpWAAj6VSTlqzGruW9\\n'
            'FiCTRCUWN7nMpNoN4nw=\\n-----END PRIVATE KEY-----\\n"}'
        )

        monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(key_file))
        monkeypatch.setenv("GOOGLE_CALENDAR_ID", "test-cal@group.calendar.google.com")

        with patch("src.bot.CalendarService") as MockSvc:
            mock_service = MagicMock()
            MockSvc.return_value = mock_service

            client = DiscalClient()
            result = client._init_calendar()

            assert result is mock_service
            MockSvc.assert_called_once()
            mock_service.verify_access.assert_called_once()

    def test_exits_on_credential_error(self, monkeypatch):
        """_init_calendar calls sys.exit(1) when credentials cannot be loaded."""
        monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", "/nonexistent/key.json")
        monkeypatch.setenv("GOOGLE_CALENDAR_ID", "test-cal")

        client = DiscalClient()

        with pytest.raises(SystemExit) as exc_info:
            client._init_calendar()

        assert exc_info.value.code == 1

    def test_exits_on_verify_failure(self, monkeypatch, tmp_path):
        """_init_calendar calls sys.exit(1) when verify_access raises RuntimeError."""
        key_file = tmp_path / "key.json"
        key_file.write_text(
            '{"type": "service_account", "project_id": "p",'
            ' "client_email": "x@x.iam.gserviceaccount.com",'
            ' "token_uri": "https://oauth2.googleapis.com/token",'
            ' "private_key": "-----BEGIN PRIVATE KEY-----\\n'
            'MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQDRPTiNfUy3C1hp\\n'
            'U29KCrCIKpXNi9QlC+yGoqe4YYshM2KU98iZd1VzUmSzl3z9l3fJDwpL+I0Mzy3j\\n'
            'sqkZuK2o+l8UTmnRUUCtYMWEkUBatSqCefMLETRbZKj5WAxLgfmfHhRIyj3+PQGL\\n'
            'guBd+1GzCGY+53aqgqDGj9e68YULMm1vhN3kMFO/AQCEaNzKMc9XUFRL70xFLOIT\\n'
            'deQnL1mxuDobMv1UDeX8/CUQTlv3Z4gRI0D2AatFs6636D4ARpaXgC+TD0Wgf+5n\\n'
            't+SDIl41Wzfvsme7tuppCNenqZlSry1yikYrAuJv+2+DZivG/E+wGA7d7SCZo/ck\\n'
            'x3+O4r0xAgMBAAECgf8Bowpc08iMHbDdzpfl2kzF2jDTNqbpK6F+EFFtfb+Zlayh\\n'
            'Jg8Xgt291QqoHQPL6imxjzsrpreEdk9UM9DolWMDn2ariaZfJHvub/3Nqv73+XnO\\n'
            'cRDrPvwUTm8GwY5y5JkQBOi+JkCfpDIwShUfm/cELXLnqxMEqtA/hcNWHBobkHn6\\n'
            'QzE5FWilICeaH0WNOngLbYv1pZgamj7y9EeoIL/XP+n57hI8jKi5Oz2LOAJwgRbn\\n'
            'BHsc8SvhMaUz5uNWNbRBefbGNA76yLPd7ZzZRZa0Iw3vNCajeBaMJWqS49qvKjS1\\n'
            'cadX6zp/+T05JQtq65xdUdGVS/urdnzCtJdV8OECgYEA8K1PU1vnkYv76PFBcg62\\n'
            'pIITLZqF+wMNerER0VZNLAmh9jCrzMuRYhnySZ9HdVGefo/ic80wvo4XitFmA+UP\\n'
            'o4xUkAIFSNwVcyE0Ujnn69RaC/iBFvHlIiVF9gdW/1E+McGXNAtk8bW8JJZNi4th\\n'
            'rHR0wPcTuo2ukoY3tNKSrRECgYEA3o+E6HDTiCQ0k6i7NI5QlrHLstGiXVFGZrLB\\n'
            'E5FJ4RDDVIlrOzVTU3E2D8r/YuriK1GKEkRgJTJrcV6PogZf6/wUvxedG+mRXTfh\\n'
            'iJiY8HmoQcNwDGAqOBUlpebs/ve0hRIobkFqXcLNBgB1LO3CxEm+mTK+3UrLbOGe\\n'
            '7LpLjiECgYBuHr4m4+wmWihewtQw/a5vwtxHh2Y6HYFzW8VNRPF2bsnePRK+V34j\\n'
            'pr+HFAu8ECY2vlrcpUviRF1dNMY6jfoD2NdwNJx6Y8ikrtKjtL761mSFCaT2/KLc\\n'
            'ZrWGBoG1vFR6q5slQvli5sY471R3vsRoBbjN+b7bIqx3elXOtHJMIQKBgHb8yBP1\\n'
            'bkJVCP8AsMWSaKeIet0pkuLNNxRk8TDi9lqruaKSrY/EHL55wmuDHjLmXPDH8Ud+\\n'
            '4uBAKo07/xKi0dm6teTMXSS1JRBvddavruSyRjCSqm8TYr8FH1GpOn++MvcKFC+O\\n'
            'La3fHfndeMgCfaSvwITrSnvJJyUZIvxxRT/BAoGAPmRj3AiEv4tBZaiB/FrpPGEo\\n'
            'RPZ21slNoYt//dkTUixnqn8iXP9fxZVfg291R+D1cayx02/IHAANN1bORKieWODv\\n'
            'ln22ArhfMT13kbnqrRZpNTHb+iZKz6Z+wa/BKw2+NJqg7PQpWAAj6VSTlqzGruW9\\n'
            'FiCTRCUWN7nMpNoN4nw=\\n-----END PRIVATE KEY-----\\n"}'
        )

        monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(key_file))
        monkeypatch.setenv("GOOGLE_CALENDAR_ID", "test-cal")

        with patch("src.bot.CalendarService") as MockSvc:
            mock_service = MagicMock()
            mock_service.verify_access.side_effect = RuntimeError("API error")
            MockSvc.return_value = mock_service

            client = DiscalClient()

            with pytest.raises(SystemExit) as exc_info:
                client._init_calendar()

            assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_on_ready_logs_ready():
    """on_ready logs 'Ready' with the bot's username."""
    client = DiscalClient()

    mock_user = MagicMock()
    mock_user.name = "DiscalBot"

    with patch.object(type(client), "user", new_callable=lambda: property(lambda self: mock_user)):
        with patch.object(logging.getLogger("src.bot"), "info") as mock_log:
            await client.on_ready()
            mock_log.assert_called_once()
            fmt_string, name = mock_log.call_args[0]
            assert fmt_string == "Ready: %s"
            assert name == "DiscalBot"
