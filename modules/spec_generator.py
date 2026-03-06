"""
spec_generator.py
Uses the free Gemini Text API to generate professional product specifications in Arabic.
"""

import os
import requests
import logging

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def generate_product_specs(brand: str, model: str, category: str = "") -> str:
    """
    Calls Gemini API to generate professional Arabic product specifications.
    Returns the specifications as a string, or an empty string if it fails.
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set. Cannot generate specs via AI.")
        return ""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    product_name = f"{brand} {model}".strip()
    if category:
        product_name += f" ({category})"

    prompt = (
        f"Write comprehensive and detailed technical specifications and features for the following product: {product_name}\n\n"
        "Requirements:\n"
        "1. Write in clear, professional English.\n"
        "2. Provide a detailed bulleted list of key features and technical specs.\n"
        "3. Do not include any introductions or conclusions, just the specifications directly.\n"
        "4. Do not use Markdown asterisks (**), just plain text bullets (-)."
    )

    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 600,
        }
    }

    try:
        resp = requests.post(url, json=data, timeout=20)
        resp.raise_for_status()
        
        # Force UTF-8 encoding to prevent Windows charmap errors
        resp.encoding = 'utf-8'
        result = resp.json()
        
        # Extract text from the Gemini response structure
        candidates = result.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts:
                text = parts[0].get("text", "").strip()
                # Clean up any potential markdown formatting the user doesn't want
                text = text.replace("**", "")  # Remove bold markdown
                return text
                
        logger.warning(f"Failed to parse Gemini response for {product_name}")
        return ""
    except Exception as e:
        logger.error(f"Error generating specs via Gemini for '{product_name}': {e}")
        return ""
