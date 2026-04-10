#!/usr/bin/env python3
"""
One-time OAuth authorization for Google Drive.

Run this locally (not in Docker) to generate credentials/token.json.
The token contains a refresh token that the app uses to authenticate
without needing a browser.

Prerequisites:
  1. Go to Google Cloud Console > APIs & Services > Credentials
  2. Create an OAuth 2.0 Client ID (type: Desktop App)
  3. Download the JSON and save as credentials/client_secret.json

Usage:
  python scripts/authorize_gdrive.py
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive"]
CLIENT_SECRETS = os.getenv("GDRIVE_CLIENT_SECRETS_PATH", "credentials/client_secret.json")
TOKEN_PATH = os.getenv("GDRIVE_TOKEN_PATH", "credentials/token.json")


def main():
    if not os.path.exists(CLIENT_SECRETS):
        print(f"ERROR: Client secrets file not found at {CLIENT_SECRETS}")
        print()
        print("To create one:")
        print("  1. Go to https://console.cloud.google.com/apis/credentials")
        print("  2. Click '+ CREATE CREDENTIALS' > 'OAuth client ID'")
        print("  3. Application type: 'Desktop app'")
        print("  4. Download JSON and save as credentials/client_secret.json")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": SCOPES,
    }

    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"Token saved to {TOKEN_PATH}")
    print("This token will be auto-refreshed by the app. You only need to run this once.")


if __name__ == "__main__":
    main()
