"""
folder_builder.py
Creates the local output folder structure:
  output/{excel_name}/{section_name}/{serial_code}/photos
"""

import os
import re
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def sanitize_folder_name(name: str) -> str:
    """Remove characters not valid in Windows/Linux folder names."""
    # Replace common invalid chars with underscore
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    # Collapse multiple spaces/underscores
    name = re.sub(r'\s+', " ", name).strip()
    return name


def build_product_folder(
    base_output_dir: str,
    excel_name: str,
    section_name: str,
    serial_code: str,
) -> str:
    """
    Create and return the path:
    base_output_dir / excel_name / section_name / serial_code
    """
    folder_path = os.path.join(
        base_output_dir,
        sanitize_folder_name(excel_name),
        sanitize_folder_name(section_name),
        sanitize_folder_name(serial_code),
    )
    Path(folder_path).mkdir(parents=True, exist_ok=True)
    logger.debug(f"Created folder: {folder_path}")
    return folder_path


def move_photos_to_product_folder(photo_paths: list[str], product_folder: str) -> list[str]:
    """
    Move generated photos into the product folder.
    Returns list of final photo paths.
    """
    final_paths = []
    for src in photo_paths:
        filename = os.path.basename(src)
        dest = os.path.join(product_folder, filename)
        shutil.move(src, dest)
        final_paths.append(dest)
        logger.debug(f"Moved {src} → {dest}")
    return final_paths


def cleanup_temp_dir(temp_dir: str):
    """Remove the temporary working directory after processing."""
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"Cleaned up temp dir: {temp_dir}")
    except Exception as e:
        logger.warning(f"Could not clean up {temp_dir}: {e}")
