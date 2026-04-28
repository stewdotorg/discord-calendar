"""Google service account credential loading."""

import json
import os

from google.oauth2.service_account import Credentials


class CredentialsError(Exception):
    """Raised when service account credentials cannot be loaded."""


def load_credentials(key_path: str) -> Credentials:
    """Load Google service account credentials from a JSON key file.

    Args:
        key_path: Filesystem path to the service account JSON key.

    Returns:
        google.oauth2.service_account.Credentials

    Raises:
        CredentialsError: If the file is missing, unreadable, or invalid.
    """
    if not os.path.isfile(key_path):
        raise CredentialsError(f"Service account key file not found: {key_path}")

    try:
        with open(key_path, "r") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, ValueError) as exc:
        raise CredentialsError(f"Failed to load credentials: {exc}") from exc

    return Credentials.from_service_account_info(raw)
