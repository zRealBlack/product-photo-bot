"""
price_finder.py
Uses Google Gemini with Google Search grounding to search for product prices in Egypt.
"""

import os
import json
import time
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def find_egyptian_prices(brand: str, model: str) -> dict:
    """
    Search for product prices in Egypt using Gemini Search Grounding.
    Returns a dictionary of found prices in EGP:
    {
        "amazon_eg": float or None,
        "noon_eg": float or None,
        "jumia_eg": float or None,
        "brand_eg": float or None,
        "currency": "EGP"
    }
    """
    fallback_result = {
        "amazon_eg": None,
        "noon_eg": None,
        "jumia_eg": None,
        "brand_eg": None,
        "general_eg": None,
        "general_source": None,
        "currency": "EGP"
    }

    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set. Cannot search prices.")
        return fallback_result

    product_name = f"{brand} {model}".strip()
    prompt = (
        f"Find the current price of the product '{product_name}' in Egypt in EGP (Egyptian Pounds) on the following websites/sources:\n"
        f"1. Amazon Egypt (amazon.eg)\n"
        f"2. Noon Egypt (noon.com)\n"
        f"3. Jumia Egypt (jumia.com.eg)\n"
        f"4. The official brand website in Egypt (e.g., Samsung Egypt for Samsung products, Apple official resellers/agents for Apple, etc.)\n"
        f"5. The general latest listed or market price for this product in Egypt (from any other Egyptian retailer/store or general market pricing if not listed on the sites above)\n\n"
        f"Return the output strictly as a JSON object with the following keys:\n"
        f"{{\n"
        f"  \"amazon_eg\": price as float or null,\n"
        f"  \"noon_eg\": price as float or null,\n"
        f"  \"jumia_eg\": price as float or null,\n"
        f"  \"brand_eg\": price as float or null,\n"
        f"  \"general_eg\": price as float or null,\n"
        f"  \"general_source\": string name of the specific store/source where the general price was found (e.g., 'Raya Shop', 'B.TECH', 'El Shennawy') or null,\n"
        f"  \"currency\": \"EGP\"\n"
        f"}}\n"
        f"Provide only the raw JSON. Do not include markdown code block formatting."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # We will try gemini-2.5-flash as the primary, and fallback if needed
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    
    # Retry parameters for rate limits (429)
    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        for model_name in models:
            try:
                logger.info(f"Searching prices for '{product_name}' using model {model_name} (attempt {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[{"google_search": {}}],
                        temperature=0.0,
                    )
                )
                
                text = response.text.strip()
                # Clean up any potential markdown code blocks
                if text.startswith("```json"): text = text[7:]
                if text.startswith("```"): text = text[3:]
                if text.endswith("```"): text = text[:-3]
                text = text.strip()

                try:
                    data = json.loads(text)
                    
                    # Extract general source name safely
                    source_val = data.get("general_source")
                    general_source = str(source_val).strip() if source_val else None
                    
                    # Standardize keys
                    result = {
                        "amazon_eg": data.get("amazon_eg"),
                        "noon_eg": data.get("noon_eg"),
                        "jumia_eg": data.get("jumia_eg"),
                        "brand_eg": data.get("brand_eg"),
                        "general_eg": data.get("general_eg"),
                        "general_source": general_source,
                        "currency": "EGP"
                    }
                    
                    # Convert values to float if they are numeric, otherwise None
                    for key in ["amazon_eg", "noon_eg", "jumia_eg", "brand_eg", "general_eg"]:
                        val = result[key]
                        if val is not None:
                            try:
                                result[key] = float(val)
                            except (ValueError, TypeError):
                                result[key] = None
                                
                    logger.info(f"Price search success for '{product_name}': {result}")
                    return result
                except json.JSONDecodeError as je:
                    logger.error(f"Failed to parse Gemini JSON output for '{product_name}': {je} | Raw output: {text}")
                    # Try to extract floats using regex if JSON fails
                    # but fallback to next model or retry
                    
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    logger.warning(f"Gemini API rate limit hit (429) for '{product_name}', retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    break # Break inner model loop to retry attempt with delay
                elif "404" in err_str or "NOT_FOUND" in err_str:
                    logger.warning(f"Model {model_name} not found, trying next model...")
                    continue
                else:
                    logger.error(f"Gemini API error during price search for '{product_name}' using {model_name}: {e}")
                    # Try next model in the list
                    continue
        else:
            # If all models failed or we hit a non-429 error
            continue
            
    logger.warning(f"All price search attempts failed for '{product_name}'. Returning fallback.")
    return fallback_result
