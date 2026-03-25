"""
spec_generator.py
Uses the free Gemini API to generate professional product specifications, 
available colors, and a cleaned-up readable product name.
"""

import os
import json
import requests
import logging

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def generate_product_specs(brand: str, model: str, category: str = "") -> dict:
    """
    Calls Gemini API to get a structured JSON response.
    Returns:
    {
        "clean_name": str,  # The readable product name
        "specs": str,       # Bulleted list of specs
        "colors": str       # Available colors or "N/A"
    }
    Fallback returns the original brand/model and empty specs.
    """
    fallback_result = {
        "clean_name": f"{brand} {model}".strip(),
        "specs": "",
        "colors": ""
    }

    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set. Cannot generate specs via AI.")
        return fallback_result

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    product_name = f"{brand} {model}".strip()
    if category:
        product_name += f" ({category})"

    prompt = (
        f"Analyze the following product: {product_name}\n\n"
        "Return a valid JSON object with EXACTLY these three keys:\n"
        "1. \"clean_name\": A clean, readable name for the product (e.g., 'Philips Air Fryer' instead of 'PHILIPS.Airfryer 20W HD9200 bla bla').\n"
        "2. \"specs\": A detailed bulleted list of key technical specs and features in plain text. Use hyphens (-) for bullets. No markdown asterisks.\n"
        "3. \"colors\": The available color options (e.g., 'Black', 'White', 'Silver') or 'N/A' if unknown.\n\n"
        "Do not include any code block formatting like ```json in the output, just the raw JSON."
    )

    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 600,
            # We can optionally force JSON response MIME type but prompting usually works well enough
        }
    }

    try:
        resp = requests.post(url, json=data, timeout=20)
        resp.raise_for_status()
        
        # Force UTF-8 encoding
        resp.encoding = 'utf-8'
        result = resp.json()
        
        candidates = result.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts:
                text = parts[0].get("text", "").strip()
                
                # Clean up potential markdown code blocks around the JSON
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                
                text = text.strip()
                
                try:
                    parsed_json = json.loads(text)
                    
                    # Ensure all keys exist
                    clean_name = parsed_json.get("clean_name", fallback_result["clean_name"])
                    specs = parsed_json.get("specs", "")
                    colors = parsed_json.get("colors", "")
                    
                    # Clean up random markdown that AI might still inject
                    specs = specs.replace("**", "")
                    
                    return {
                        "clean_name": clean_name,
                        "specs": specs,
                        "colors": colors
                    }
                except json.JSONDecodeError as je:
                    logger.error(f"Failed to parse Gemini JSON: {je} | Raw: {text}")
                    return fallback_result
                
        logger.warning(f"No valid candidates in Gemini response for {product_name}")
        return fallback_result
    except Exception as e:
        logger.error(f"Error generating specs via Gemini for '{product_name}': {e}")
        return fallback_result
