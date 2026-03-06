"""
image_searcher.py
Searches Google Custom Search for product reference images and downloads them.
"""

import os
import requests
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX")


def search_product_images(query: str, num_images: int = 3) -> list[str]:
    """
    Search Google Images for the product and return a list of image URLs.
    """
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_SEARCH_API_KEY,
        "cx": GOOGLE_SEARCH_CX,
        "q": query,
        "searchType": "image",
        "num": num_images,
        "imgType": "photo",
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


def download_images(image_urls: list[str], save_dir: str) -> list[str]:
    """
    Download images from URLs to save_dir.
    Returns list of local file paths for successfully downloaded images.
    """
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    saved_paths = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    for i, url in enumerate(image_urls):
        try:
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()

            # Determine extension from content type
            content_type = response.headers.get("content-type", "image/jpeg")
            ext = "jpg" if "jpeg" in content_type else content_type.split("/")[-1].split(";")[0]
            ext = ext if ext in ("jpg", "jpeg", "png", "webp") else "jpg"

            file_path = os.path.join(save_dir, f"ref_{i + 1}.{ext}")
            with open(file_path, "wb") as f:
                f.write(response.content)
            saved_paths.append(file_path)
            logger.info(f"Downloaded reference image: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to download image from {url}: {e}")

    return saved_paths


def get_reference_images(brand: str, model_name: str, save_dir: str) -> list[str]:
    """
    Full pipeline: search + download reference images for a product.
    Returns list of local file paths.
    """
    query = f"{brand} {model_name}"
    logger.info(f"Searching images for: {query}")
    urls = search_product_images(query, num_images=3)

    if not urls:
        logger.warning(f"No images found for: {query}")
        return []

    return download_images(urls, save_dir)
