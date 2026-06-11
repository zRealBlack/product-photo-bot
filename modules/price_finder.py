"""
price_finder.py
Uses Google Gemini with Google Search grounding to search for product prices in Egypt.
"""

import os
import json
import time
import logging
import re
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Support local brands in Egypt for exact matching
LOCAL_BRANDS_MAP = {
    "فريش": "Fresh",
    "اتصال مصر": "Etisal Egypt",
    "اوكا": "Oka",
    "dsp": "DSP",
    "raf": "RAF"
}

def clean_product_query(brand: str, model: str) -> str:
    brand_clean = brand.strip()
    brand_lower = brand_clean.lower()
    
    # Strip dots/dashes/spaces from the left of the model
    cleaned_model = model.strip().lstrip(".-_ ")
    model_lower = cleaned_model.lower()
    
    # Check if the model already starts with the brand name (case-insensitive, ignoring non-alphanumeric chars)
    clean_brand_cmp = re.sub(r'[^a-zA-Z0-9]', '', brand_lower)
    clean_model_cmp = re.sub(r'[^a-zA-Z0-9]', '', model_lower)
    
    # Local Egyptian brand mapping support
    mapped_english = LOCAL_BRANDS_MAP.get(brand_clean) or LOCAL_BRANDS_MAP.get(brand_lower)
    if mapped_english:
        clean_mapped_cmp = re.sub(r'[^a-zA-Z0-9]', '', mapped_english.lower())
        if clean_mapped_cmp and clean_mapped_cmp in clean_model_cmp:
            return cleaned_model
        return f"{mapped_english} {brand_clean} {cleaned_model}".strip()
        
    if clean_brand_cmp and clean_model_cmp.startswith(clean_brand_cmp):
        return cleaned_model
        
    return f"{brand_clean} {cleaned_model}".strip()

def find_egyptian_prices(brand: str, model: str) -> dict:
    """
    Search for product prices in Egypt using Gemini Search Grounding.
    Returns a dictionary of found prices in EGP:
    {
        "amazon_eg": float or None,
        "noon_eg": float or None,
        "jumia_eg": float or None,
        "brand_eg": float or None,
        "general_eg": float or None,
        "general_source": str or None,
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

    product_name = clean_product_query(brand, model)
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
    
    # We will try gemini-3-flash-preview as the primary, and fallback to newer/older models if needed
    models = ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-flash-latest"]
    
    # Retry parameters for rate limits (429)
    max_retries = 2
    import random

    for attempt in range(max_retries):
        # Randomized exponential backoff to prevent collision lock
        backoff = (2 ** attempt) * 5 + random.uniform(1, 3)
        
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
                    continue
                    
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    logger.warning(f"Gemini API rate limit hit (429) for '{product_name}', backoff sleeping {backoff:.2f}s...")
                    time.sleep(backoff)
                    break # Break inner model loop to retry attempt with backoff
                elif "404" in err_str or "NOT_FOUND" in err_str:
                    logger.warning(f"Model {model_name} not found, trying next model...")
                    continue
                else:
                    logger.error(f"Gemini API error during price search for '{product_name}' using {model_name}: {e}")
                    continue
        else:
            continue
            
    logger.warning(f"All price search attempts failed for '{product_name}'. Returning fallback.")
    return fallback_result

