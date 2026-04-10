#!/usr/bin/env python3
"""One-time setup: create Google Drive folder structure for address-normaliser.

Creates folders under the existing 'Falcon Field' shared folder in Google Drive.

Usage:
  python scripts/setup_drive.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

FALCON_FIELD_FOLDER_ID = "1I9e4nu0t_3LxFw6gX5szG8YULTUrnZHx"

TOKEN_PATH = os.getenv("GDRIVE_TOKEN_PATH", "credentials/token.json")

FOLDER_STRUCTURE = {
    "Address Normaliser": {
        "Upload": {},
        "Processing": {},
        "Completed": {
            "Output": {},
            "Logs": {},
        },
        "Archive": {
            "Upload": {},
            "Completed": {},
        },
    },
}

ENV_MAPPING = {
    "Address Normaliser>Upload": "GDRIVE_UPLOAD_FOLDER_ID",
    "Address Normaliser>Processing": "GDRIVE_PROCESSING_FOLDER_ID",
    "Address Normaliser>Completed": "GDRIVE_COMPLETED_FOLDER_ID",
    "Address Normaliser>Archive": "GDRIVE_ARCHIVE_UPLOAD_FOLDER_ID",
    "Address Normaliser>Completed>Output": "GDRIVE_COMPLETED_OUTPUT_FOLDER_ID",
    "Address Normaliser>Completed>Logs": "GDRIVE_COMPLETED_LOGS_FOLDER_ID",
    "Address Normaliser>Archive>Upload": "GDRIVE_ARCHIVE_UPLOAD_UPLOAD_FOLDER_ID",
    "Address Normaliser>Archive>Completed": "GDRIVE_ARCHIVE_COMPLETED_FOLDER_ID",
}


def get_service():
    with open(TOKEN_PATH) as f:
        token_data = json.load(f)
    creds = Credentials.from_authorized_user_info(token_data)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_data["token"] = creds.token
        with open(TOKEN_PATH, "w") as f:
            json.dump(token_data, f, indent=2)
    return build("drive", "v3", credentials=creds)


def create_folder(service, name, parent_id):
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def create_structure(service, structure, parent_id, prefix="", env_vars=None):
    if env_vars is None:
        env_vars = {}

    for name, children in structure.items():
        folder_id = create_folder(service, name, parent_id)
        path = f"{prefix}>{name}" if prefix else name
        print(f"  Created: {path} -> {folder_id}")

        if path in ENV_MAPPING:
            env_vars[ENV_MAPPING[path]] = folder_id

        if children:
            create_structure(service, children, folder_id, path, env_vars)

    return env_vars


def main():
    print("Setting up Google Drive folders for Address Normaliser...")
    print(f"Parent folder: Falcon Field ({FALCON_FIELD_FOLDER_ID})")

    service = get_service()
    env_vars = create_structure(service, FOLDER_STRUCTURE, FALCON_FIELD_FOLDER_ID)

    print("\n--- Add these to your .env file ---\n")
    for key, value in sorted(env_vars.items()):
        print(f"{key}={value}")

    print("\nDone! Copy the above into your .env file.")


if __name__ == "__main__":
    main()
