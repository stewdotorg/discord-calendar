#!/usr/bin/env python3
"""One-time OAuth2 setup for Discal.

Run this once from your local machine to authorize the bot to access
Google Calendar on behalf of a dedicated Google account.

Prerequisites:
- A Google Cloud OAuth 2.0 Client ID (Desktop app type)
- Client secret saved as client-secret.json in the project root

What it does:
1. Opens your browser for Google consent
2. Catches the OAuth redirect via a temporary local HTTP server
3. Saves the refresh token to .env as GOOGLE_REFRESH_TOKEN
4. The bot uses this refresh token for all Calendar API calls going forward
"""

import json
import os
import sys
from pathlib import Path

import google_auth_oauthlib.flow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]
REDIRECT_PORT = 0  # random available port
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
CLIENT_SECRET_PATH = Path(__file__).resolve().parent.parent / "client-secret.json"


def main() -> None:
    if not CLIENT_SECRET_PATH.is_file():
        sys.exit(
            f"❌ Client secret not found at {CLIENT_SECRET_PATH}\n"
            "   Create an OAuth 2.0 Client ID (Desktop app) in Google Cloud Console\n"
            "   and download the JSON as client-secret.json in the project root."
        )

    # Load client config (handle both "web" and "installed" key formats)
    client_config = json.loads(CLIENT_SECRET_PATH.read_text())
    client_type = "web" if "web" in client_config else "installed"

    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(
        client_config,
        SCOPES,
    )
    # Force redirect_uri to localhost with a random port
    flow.redirect_uri = "http://localhost:0"

    print("Opening browser for Google Calendar authorization...")
    creds = flow.run_local_server(
        port=REDIRECT_PORT,
        authorization_prompt_message=(
            "Please visit this URL to authorize Discal:\n{url}"
        ),
        success_message="""
✅ Authorization complete! The refresh token has been saved.

You can now close this window and start the bot.
        """.strip(),
        open_browser=True,
    )

    refresh_token = creds.refresh_token
    if not refresh_token:
        sys.exit(
            "❌ No refresh token received. Make sure the OAuth client\n"
            "   is configured as a 'Desktop' application type."
        )

    # Update .env with the refresh token
    env_text = ENV_PATH.read_text() if ENV_PATH.is_file() else ""
    lines = env_text.splitlines(keepends=True)
    new_lines = []
    found = False
    for line in lines:
        if line.startswith("GOOGLE_REFRESH_TOKEN="):
            new_lines.append(f"GOOGLE_REFRESH_TOKEN={refresh_token}\n")
            found = True
        elif line.startswith("GOOGLE_SERVICE_ACCOUNT_FILE="):
            # Comment out the old service account key
            new_lines.append(f"# {line}")
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"\n# Google Calendar (OAuth2)\n")
        new_lines.append(f"GOOGLE_REFRESH_TOKEN={refresh_token}\n")

    # Also replace the CLIENT_SECRET_FILE env var
    final_lines = []
    client_secret_found = False
    for line in new_lines:
        if line.startswith("GOOGLE_CLIENT_SECRET_FILE="):
            final_lines.append("GOOGLE_CLIENT_SECRET_FILE=./client-secret.json\n")
            client_secret_found = True
        else:
            final_lines.append(line)
    if not client_secret_found:
        # Insert after the Google Calendar section header
        inserted = False
        result = []
        for line in final_lines:
            result.append(line)
            if not inserted and "Google Calendar" in line:
                result.append("GOOGLE_CLIENT_SECRET_FILE=./client-secret.json\n")
                inserted = True
        final_lines = result if inserted else final_lines

    ENV_PATH.write_text("".join(final_lines))
    print(f"✅ Refresh token saved to {ENV_PATH}")


if __name__ == "__main__":
    main()
