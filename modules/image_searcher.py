"""
image_searcher.py
Searches Google Custom Search for product images and downloads them.
Saves high-quality JPG/PNG files directly to the product folder — no AI needed.
"""

import os
import requests
import logging
from pathlib import Path
from PIL import Image
import io

logger = logging.getLogger(__name__)

GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX")

# Minimum dimensions to accept an image (filter out tiny thumbnails)
MIN_WIDTH = 400
MIN_HEIGHT = 400


def search_product_images(query: str, num_images: int = 5) -> list[str]:
    """
    Search Google Images for the product and return image URLs.
    Requests large images to maximize quality.
    """
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_SEARCH_API_KEY,
        "cx": GOOGLE_SEARCH_CX,
        "q": query,
        "searchType": "image",
        "num": num_images,
        "imgType": "photo",
        "imgSize": "large",      # prefer large images
        "safe": "active",
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])
        return [item["link"] for item in items]
    except Exception as e:
        logger.error(f"Google search failed for '{query}': {e}")
        return []


def download_images(image_urls: list[str], save_dir: str, max_photos: int = 3) -> list[str]:
    """
    Download and validate images. Saves as JPEG (high quality).
    Skips images that are too small or fail to open.
    Returns list of saved file paths.
    """
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    saved_paths = []
    photo_num = 1

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    for url in image_urls:
        if photo_num > max_photos:
            break
        try:
            resp = requests.get(url, timeout=20, headers=headers)
            resp.raise_for_status()

            # Open with Pillow to validate and get dimensions
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            w, h = img.size

            if w < MIN_WIDTH or h < MIN_HEIGHT:
                logger.info(f"Skipped small image ({w}x{h}): {url}")
                continue

            # Save as high-quality JPEG
            file_path = os.path.join(save_dir, f"photo_{photo_num}.jpg")
            img.save(file_path, "JPEG", quality=95, optimize=True)
            saved_paths.append(file_path)
            logger.info(f"Saved photo_{photo_num}.jpg ({w}x{h}): {url}")
            photo_num += 1

        except Exception as e:
            logger.warning(f"Skipped image from {url}: {e}")

    return saved_paths


def get_reference_images(brand: str, model_name: str, save_dir: str) -> list[str]:
    """
    Search for product images and download up to 3 high-quality ones.
    Returns list of local file paths.
    """
    query = f"{brand} {model_name}"
    logger.info(f"Searching images for: {query}")

    # Search for 6 candidates so we have extras in case some are too small
    urls = search_product_images(query, num_images=6)

    if not urls:
        logger.warning(f"No images found for: {query}")
        return []

    return download_images(urls, save_dir, max_photos=3)
