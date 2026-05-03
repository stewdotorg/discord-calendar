"""Google credential loading.

Supports two modes:
- **OAuth2 user credentials** (preferred): refresh token from a one-time
  consent flow.  Enables attendee management.
- **Service account** (legacy): JSON key file.  Cannot manage attendees
  due to Google API restrictions.
"""

import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

_USER_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


class CredentialsError(Exception):
    """Raised when credentials cannot be loaded."""


def _load_user_credentials(refresh_token: str) -> UserCredentials:
    """Load OAuth2 user credentials from the refresh token + client secret.

    Reads the OAuth client ID and secret from client-secret.json, then
    exchanges the stored refresh token for a fresh access token.

    Returns:
        google.oauth2.credentials.Credentials

    Raises:
        CredentialsError: If the client secret file is missing or the
            token cannot be refreshed.
    """
    client_secret_path = os.environ.get("GOOGLE_CLIENT_SECRET_FILE", "./client-secret.json")

    if not os.path.isfile(client_secret_path):
        raise CredentialsError(
            f"OAuth client secret file not found: {client_secret_path}"
        )

    try:
        with open(client_secret_path) as f:
            client_config = json.load(f)
    except (json.JSONDecodeError, ValueError) as exc:
        raise CredentialsError(f"Failed to load client secret: {exc}") from exc

    # Handle both "web" and "installed" client config formats
    client_type = "web" if "web" in client_config else "installed"
    cfg = client_config[client_type]

    creds = UserCredentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=cfg["token_uri"],
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scopes=cfg.get("scopes", _USER_SCOPES),
    )

    # Refresh the access token (needed once on startup)
    try:
        creds.refresh(Request())
    except Exception as exc:
        raise CredentialsError(
            f"Failed to refresh OAuth token: {exc}\n"
            "The refresh token may have expired or been revoked.\n"
            "Re-run scripts/setup_oauth.py to re-authorize."
        ) from exc

    return creds


def load_credentials(key_path: str = "") -> (
    UserCredentials | ServiceAccountCredentials
):
    """Load Google credentials, preferring OAuth2 user mode.

    If GOOGLE_REFRESH_TOKEN is set in the environment, loads OAuth2 user
    credentials.  Otherwise falls back to the service account key file
    specified by ``key_path``.

    Args:
        key_path: Filesystem path to the service account JSON key (legacy).

    Returns:
        google.oauth2.credentials.Credentials or
        google.oauth2.service_account.Credentials

    Raises:
        CredentialsError: If neither OAuth2 nor service account
            credentials can be loaded.
    """
    # --- OAuth2 user credentials (preferred) ---
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
    if refresh_token:
        return _load_user_credentials(refresh_token)

    # --- Service account (legacy fallback) ---
    if not key_path:
        key_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")

    if not key_path:
        raise CredentialsError(
            "No Google credentials configured.\n"
            "Set GOOGLE_REFRESH_TOKEN for OAuth2 (recommended) or\n"
            "GOOGLE_SERVICE_ACCOUNT_FILE for service account (legacy)."
        )

    if not os.path.isfile(key_path):
        raise CredentialsError(
            f"Service account key file not found: {key_path}"
        )

    try:
        with open(key_path) as f:
            raw = json.load(f)
    except (json.JSONDecodeError, ValueError) as exc:
        raise CredentialsError(f"Failed to load service account key: {exc}") from exc

    return ServiceAccountCredentials.from_service_account_info(raw)
