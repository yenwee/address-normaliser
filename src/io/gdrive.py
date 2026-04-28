import os
import json
import time
import ssl
from datetime import datetime, timezone, timedelta

MYT = timezone(timedelta(hours=8))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from src.config import (
    GDRIVE_TOKEN_PATH,
    GDRIVE_UPLOAD_FOLDER_ID,
    GDRIVE_PROCESSING_FOLDER_ID,
    GDRIVE_COMPLETED_FOLDER_ID,
    GDRIVE_COMPLETED_OUTPUT_FOLDER_ID,
    GDRIVE_COMPLETED_LOGS_FOLDER_ID,
    GDRIVE_ARCHIVE_UPLOAD_FOLDER_ID,
    EXCEL_MIMETYPES,
)

SCOPES = ["https://www.googleapis.com/auth/drive"]

_service = None
_creds = None
_last_token_refresh = None

TOKEN_REFRESH_INTERVAL_SECONDS = 3600 * 24
DRIVE_RETRY_ATTEMPTS = 5


def _get_service():
    global _service, _creds, _last_token_refresh

    now = time.time()
    needs_refresh = (
        _service is None
        or _creds is None
        or (_last_token_refresh and now - _last_token_refresh > TOKEN_REFRESH_INTERVAL_SECONDS)
    )

    if needs_refresh:
        _creds = _load_credentials()
        _service = build("drive", "v3", credentials=_creds)
        _last_token_refresh = now

    return _service


def _reset_service():
    global _service, _creds, _last_token_refresh
    _service = None
    _creds = None
    _last_token_refresh = None


def _is_retryable(exc):
    if isinstance(exc, HttpError):
        return exc.resp.status in {408, 429, 500, 502, 503, 504}
    return isinstance(exc, (BrokenPipeError, TimeoutError, ConnectionError, OSError, ssl.SSLError))


def _execute_with_retry(request_factory):
    last_exc = None
    for attempt in range(1, DRIVE_RETRY_ATTEMPTS + 1):
        try:
            return request_factory().execute()
        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc) or attempt == DRIVE_RETRY_ATTEMPTS:
                raise
            _reset_service()
            time.sleep(min(60, 2**attempt))
    raise last_exc


def _load_credentials():
    if not os.path.exists(GDRIVE_TOKEN_PATH):
        raise FileNotFoundError(
            f"OAuth token not found at {GDRIVE_TOKEN_PATH}. "
            "Run 'python scripts/authorize_gdrive.py' first."
        )

    creds = Credentials.from_authorized_user_file(GDRIVE_TOKEN_PATH, SCOPES)

    if creds.refresh_token:
        for attempt in range(1, DRIVE_RETRY_ATTEMPTS + 1):
            try:
                creds.refresh(Request())
                break
            except Exception as exc:
                if not _is_retryable(exc) or attempt == DRIVE_RETRY_ATTEMPTS:
                    raise
                time.sleep(min(60, 2**attempt))
        _save_token(creds)

    return creds


def _save_token(creds):
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }
    os.makedirs(os.path.dirname(GDRIVE_TOKEN_PATH), exist_ok=True)
    with open(GDRIVE_TOKEN_PATH, "w") as f:
        json.dump(token_data, f, indent=2)


def list_upload_folder():
    mime_query = " or ".join([f"mimeType='{m}'" for m in EXCEL_MIMETYPES])
    query = f"'{GDRIVE_UPLOAD_FOLDER_ID}' in parents and ({mime_query}) and trashed=false"

    results = _execute_with_retry(
        lambda: _get_service().files().list(
            q=query,
            fields="files(id, name, createdTime, lastModifyingUser)",
            orderBy="createdTime",
        )
    )

    return results.get("files", [])


def move_file(file_id, target_folder_id):
    file = _execute_with_retry(lambda: _get_service().files().get(fileId=file_id, fields="parents"))
    previous_parents = ",".join(file.get("parents", []))

    _execute_with_retry(
        lambda: _get_service().files().update(
            fileId=file_id,
            addParents=target_folder_id,
            removeParents=previous_parents,
            fields="id, parents",
        )
    )


def move_to_processing(file_id):
    move_file(file_id, GDRIVE_PROCESSING_FOLDER_ID)


def move_to_archive(file_id):
    move_file(file_id, GDRIVE_ARCHIVE_UPLOAD_FOLDER_ID)


def download_file(file_id, local_path):
    service = _get_service()
    request = service.files().get_media(fileId=file_id)

    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    with open(local_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    return local_path


def upload_file(local_path, folder_id, filename=None):
    name = filename or os.path.basename(local_path)

    file_metadata = {
        "name": name,
        "parents": [folder_id],
    }

    media = MediaFileUpload(local_path)
    uploaded = _execute_with_retry(
        lambda: _get_service().files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
        )
    )

    return uploaded.get("id")


def find_file_in_folder(filename, folder_id):
    query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
    results = _execute_with_retry(lambda: _get_service().files().list(q=query, fields="files(id)", pageSize=1))
    files = results.get("files", [])
    return files[0]["id"] if files else None


def upload_or_replace_file(local_path, folder_id, filename=None):
    name = filename or os.path.basename(local_path)
    existing_id = find_file_in_folder(name, folder_id)

    if existing_id:
        media = MediaFileUpload(local_path)
        _execute_with_retry(lambda: _get_service().files().update(fileId=existing_id, media_body=media, fields="id"))
        return existing_id

    return upload_file(local_path, folder_id, filename=name)


def _ensure_subfolder(name, parent_folder_id):
    existing = find_file_in_folder(name, parent_folder_id)
    if existing:
        return existing
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_folder_id],
    }
    folder = _execute_with_retry(lambda: _get_service().files().create(body=metadata, fields="id"))
    return folder.get("id")


def upload_results(result_path, stats, original_filename):
    output_folder_id = GDRIVE_COMPLETED_OUTPUT_FOLDER_ID or _ensure_subfolder("Output", GDRIVE_COMPLETED_FOLDER_ID)
    logs_folder_id = GDRIVE_COMPLETED_LOGS_FOLDER_ID or _ensure_subfolder("Logs", GDRIVE_COMPLETED_FOLDER_ID)

    status_content = _build_status_text(stats, original_filename, os.path.basename(result_path))
    base, _ = os.path.splitext(result_path)
    status_path = f"{base}_status.txt"
    with open(status_path, "w") as f:
        f.write(status_content)

    upload_or_replace_file(result_path, output_folder_id)
    upload_or_replace_file(status_path, logs_folder_id)


def _build_status_text(stats, input_filename, result_filename):
    completed_at = datetime.now(MYT).strftime("%d %b %Y, %I:%M %p")

    lines = [
        f"Job: {input_filename}",
        f"Completed: {completed_at}",
        f"",
        f"Total Records: {stats.get('total', 0):,}",
        f"Processed: {stats.get('processed', 0):,}",
        f"No Address Found: {stats.get('no_address', 0):,}",
        f"Low Confidence: {stats.get('low_confidence', 0):,}",
        f"",
        f"Result File: {result_filename}",
    ]
    return "\n".join(lines)
