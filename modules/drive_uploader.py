"""
drive_uploader.py (now Dropbox-backed)
Uploads the completed output folder to Dropbox, then returns a shareable link.
Uses a simple DROPBOX_ACCESS_TOKEN — no JSON files or service accounts needed.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_FOLDER = "/Product Photos Bot"


def _get_dbx():
    """Return an authenticated Dropbox client."""
    import dropbox
    token = os.getenv("DROPBOX_ACCESS_TOKEN", "")
    if not token:
        raise ValueError("DROPBOX_ACCESS_TOKEN environment variable is not set.")
    return dropbox.Dropbox(token)


def _upload_file(dbx, local_path: str, dropbox_path: str):
    """Upload a single file to Dropbox, overwriting if it exists."""
    import dropbox
    with open(local_path, "rb") as f:
        data = f.read()
    dbx.files_upload(
        data,
        dropbox_path,
        mode=dropbox.files.WriteMode.overwrite,
    )
    logger.info(f"Uploaded: {dropbox_path}")


def _upload_folder_recursive(dbx, local_folder: str, dropbox_parent: str):
    """Recursively upload all files and subfolders to Dropbox."""
    folder_name = os.path.basename(local_folder)
    dropbox_folder = f"{dropbox_parent}/{folder_name}"

    for entry in sorted(Path(local_folder).iterdir()):
        if entry.is_dir():
            _upload_folder_recursive(dbx, str(entry), dropbox_folder)
        elif entry.is_file():
            dest = f"{dropbox_folder}/{entry.name}"
            _upload_file(dbx, str(entry), dest)

    return dropbox_folder


def upload_output_folder(local_folder: str) -> str:
    """
    Upload the entire output folder to Dropbox inside 'Product Photos Bot'.
    Returns a shareable Dropbox link for the uploaded folder.
    """
    import dropbox

    dbx = _get_dbx()

    # Upload recursively into /Product Photos Bot/<ExcelName>/...
    dropbox_path = _upload_folder_recursive(dbx, local_folder, ROOT_FOLDER)

    # Create a shared link
    try:
        link_meta = dbx.sharing_create_shared_link_with_settings(dropbox_path)
        shared_url = link_meta.url
    except dropbox.exceptions.ApiError as e:
        # Link may already exist
        links = dbx.sharing_list_shared_links(path=dropbox_path).links
        if links:
            shared_url = links[0].url
        else:
            raise e

    # Convert to direct download-friendly link (dl=0 → preview, dl=1 → download)
    shared_url = shared_url.replace("?dl=0", "?dl=0")  # keep as folder preview
    logger.info(f"Dropbox shareable link: {shared_url}")
    return shared_url
