"""
drive_uploader.py
Uploads the completed output folder to Google Drive inside a dedicated
"Product Photos Bot" folder, then returns a shareable link.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Any
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

ROOT_FOLDER_NAME = "Product Photos Bot"
SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_drive_service():
    """
    Builds Google Drive credentials from individual env vars (most reliable on Railway).
    Falls back to a JSON file path if GDRIVE_PRIVATE_KEY is not set.
    """
    import json as _json

    private_key = os.getenv("GDRIVE_PRIVATE_KEY", "")

    if private_key:
        # Individual env vars mode (Railway) — no JSON encoding issues
        # Railway may strip leading/trailing whitespace or convert \\n → \n already
        # Ensure the private key has real newlines (not literal \n string)
        if "\\n" in private_key and "\n" not in private_key:
            private_key = private_key.replace("\\n", "\n")

        info = {
            "type": "service_account",
            "project_id": os.getenv("GDRIVE_PROJECT_ID", ""),
            "private_key_id": os.getenv("GDRIVE_PRIVATE_KEY_ID", ""),
            "private_key": private_key,
            "client_email": os.getenv("GDRIVE_CLIENT_EMAIL", ""),
            "client_id": os.getenv("GDRIVE_CLIENT_ID", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv("GDRIVE_CLIENT_X509_CERT_URL", ""),
        }
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        # Fallback: JSON file path (local dev)
        sa_file = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "service_account.json")
        credentials = service_account.Credentials.from_service_account_file(sa_file, scopes=SCOPES)

    return build("drive", "v3", credentials=credentials)


def _get_or_create_folder(service, name: str, parent_id: Optional[str] = None) -> str:
    """Get a folder by name under parent_id, or create it if not found."""
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    # Create the folder
    metadata: dict[str, Any] = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    logger.info(f"Created Drive folder: {name} (id={folder['id']})")
    return folder["id"]


def _upload_file(service, local_path: str, parent_id: str) -> str:
    """Upload a single file to Drive under parent_id. Returns file id."""
    filename = os.path.basename(local_path)
    media = MediaFileUpload(local_path, resumable=True)
    metadata = {"name": filename, "parents": [parent_id]}
    file = service.files().create(body=metadata, media_body=media, fields="id").execute()
    return file["id"]


def _upload_folder_recursive(service, local_folder: str, parent_drive_id: str):
    """Recursively upload all files and subfolders."""
    folder_name = os.path.basename(local_folder)
    drive_folder_id = _get_or_create_folder(service, folder_name, parent_drive_id)

    for entry in sorted(Path(local_folder).iterdir()):
        if entry.is_dir():
            _upload_folder_recursive(service, str(entry), drive_folder_id)
        elif entry.is_file():
            _upload_file(service, str(entry), drive_folder_id)
            logger.info(f"Uploaded: {entry.name}")

    return drive_folder_id


def _make_public(service, file_id: str):
    """Make a Drive file/folder publicly accessible with a link."""
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()


def upload_output_folder(local_folder: str) -> str:
    """
    Upload the entire output folder to Google Drive inside 'Product Photos Bot'.
    Returns the shareable Google Drive link for the uploaded Excel-named folder.
    """
    service = _get_drive_service()

    # Ensure the root bot folder exists
    root_id = _get_or_create_folder(service, ROOT_FOLDER_NAME)
    logger.info(f"Root Drive folder '{ROOT_FOLDER_NAME}' id={root_id}")

    # Upload the entire output subtree
    top_folder_id = _upload_folder_recursive(service, local_folder, root_id)

    # Make it publicly accessible
    _make_public(service, top_folder_id)

    link = f"https://drive.google.com/drive/folders/{top_folder_id}?usp=sharing"
    logger.info(f"Shareable link: {link}")
    return link
