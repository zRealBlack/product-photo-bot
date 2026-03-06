"""
image_searcher.py
Searches for product images and downloads them.
Uses Bing Image scraping (no API key needed).
Falls back to Google Custom Search API if available.
"""

import os
import re
import requests
import logging
import io
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)

GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX", "")

MIN_WIDTH = 400
MIN_HEIGHT = 400

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _search_bing(query: str, num_images: int = 8) -> list[str]:
    """Scrape Bing Image search for image URLs (no API key needed)."""
    try:
        url = "https://www.bing.com/images/search"
        params = {"q": query, "first": 1, "count": num_images, "qft": "+filterui:imagesize-large"}
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        # Extract image URLs from the HTML (murl pattern)
        urls = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', resp.text)
        logger.info(f"Bing found {len(urls)} image URLs for '{query}'")
        return urls[:num_images]
    except Exception as e:
        logger.error(f"Bing search failed for '{query}': {e}")
        return []


def _search_google(query: str, num_images: int = 6) -> list[str]:
    """Use Google Custom Search API (requires enabled API + key)."""
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_CX:
        return []
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_SEARCH_API_KEY, "cx": GOOGLE_SEARCH_CX,
            "q": query, "searchType": "image", "num": num_images,
            "imgType": "photo", "imgSize": "large", "safe": "active",
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [item["link"] for item in items]
    except Exception as e:
        logger.warning(f"Google search failed (will use Bing): {e}")
        return []


def _search_images(query: str) -> list[str]:
    """Try Google first (if configured), fall back to Bing scraping."""
    urls = _search_google(query)
    if urls:
        return urls
    return _search_bing(query)


def _download_and_validate(image_urls: list[str], save_dir: str, max_photos: int = 3) -> list[str]:
    """Download images, validate quality (min 400x400), save as JPEG."""
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    saved = []
    photo_num = 1

    for url in image_urls:
        if photo_num > max_photos:
            break
        try:
            resp = requests.get(url, timeout=20, headers=HEADERS)
            if resp.status_code != 200 or len(resp.content) < 5000:
                continue

            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            w, h = img.size
            if w < MIN_WIDTH or h < MIN_HEIGHT:
                logger.debug(f"Skipped small image ({w}x{h})")
                continue

            path = os.path.join(save_dir, f"photo_{photo_num}.jpg")
            img.save(path, "JPEG", quality=95, optimize=True)
            saved.append(path)
            logger.info(f"Saved photo_{photo_num}.jpg ({w}x{h})")
            photo_num += 1
        except Exception as e:
            logger.debug(f"Skipped: {e}")

    return saved


def get_reference_images(brand: str, model_name: str, save_dir: str) -> list[str]:
    """Search for product images and download up to 3 high-quality ones."""
    query = f"{brand} {model_name} product photo"
    logger.info(f"Searching images for: {query}")

    urls = _search_images(query)
    if not urls:
        logger.warning(f"No images found for: {query}")
        return []

    return _download_and_validate(urls, save_dir, max_photos=3)
