"""
drive_uploader.py (Dropbox, OAuth2 refresh token)
Uploads the output folder to Dropbox and returns a shareable link.

Authentication uses OAuth2 refresh token which NEVER EXPIRES.
Set these Railway env vars:
  DROPBOX_APP_KEY       — from your Dropbox app settings
  DROPBOX_APP_SECRET    — from your Dropbox app settings
  DROPBOX_REFRESH_TOKEN — generated once via setup_dropbox.py
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_FOLDER = "/Product Photos Bot"


def _get_dbx():
    """Build an authenticated Dropbox client using refresh token (permanent)."""
    import dropbox

    app_key     = os.getenv("DROPBOX_APP_KEY", "")
    app_secret  = os.getenv("DROPBOX_APP_SECRET", "")
    refresh_tok = os.getenv("DROPBOX_REFRESH_TOKEN", "")

    if app_key and app_secret and refresh_tok:
        # Permanent OAuth2: refresh token never expires
        return dropbox.Dropbox(
            oauth2_refresh_token=refresh_tok,
            app_key=app_key,
            app_secret=app_secret,
        )
    # Fallback: short-lived access token (for quick testing only)
    access_tok = os.getenv("DROPBOX_ACCESS_TOKEN", "")
    if access_tok:
        logger.warning("Using short-lived DROPBOX_ACCESS_TOKEN — will expire in hours!")
        return dropbox.Dropbox(access_tok)

    raise ValueError(
        "Dropbox credentials not set. Add DROPBOX_APP_KEY, DROPBOX_APP_SECRET, "
        "and DROPBOX_REFRESH_TOKEN to your environment variables."
    )


def _upload_file(dbx, local_path: str, dropbox_path: str):
    """Upload a single file to Dropbox, overwriting if it exists."""
    import dropbox as dbx_module
    with open(local_path, "rb") as f:
        data = f.read()
    dbx.files_upload(data, dropbox_path, mode=dbx_module.files.WriteMode.overwrite)
    logger.info(f"Uploaded: {dropbox_path}")


def _upload_folder_recursive(dbx, local_folder: str, dropbox_parent: str) -> str:
    """Recursively upload all files and subfolders to Dropbox."""
    folder_name = os.path.basename(local_folder)
    dropbox_folder = f"{dropbox_parent}/{folder_name}"

    for entry in sorted(Path(local_folder).iterdir()):
        if entry.is_dir():
            _upload_folder_recursive(dbx, str(entry), dropbox_folder)
        elif entry.is_file():
            _upload_file(dbx, str(entry), f"{dropbox_folder}/{entry.name}")

    return dropbox_folder


def upload_output_folder(local_folder: str) -> str:
    """
    Upload the entire output folder to Dropbox inside 'Product Photos Bot'.
    Returns a shareable Dropbox link.
    """
    import dropbox

    dbx = _get_dbx()
    dropbox_path = _upload_folder_recursive(dbx, local_folder, ROOT_FOLDER)

    # Create shared link (or reuse existing one)
    try:
        link_meta = dbx.sharing_create_shared_link_with_settings(dropbox_path)
        return link_meta.url
    except dropbox.exceptions.ApiError as e:
        if "shared_link_already_exists" in str(e):
            links = dbx.sharing_list_shared_links(path=dropbox_path).links
            if links:
                return links[0].url
        raise
