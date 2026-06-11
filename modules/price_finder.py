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

import re

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def clean_product_query(brand: str, model: str) -> str:
    brand_lower = brand.lower().strip()
    model_lower = model.lower().strip()
    
    # Strip dots/dashes/spaces from the left of the model
    cleaned_model = model.strip().lstrip(".-_ ")
    
    # If the model already starts with the brand name (case-insensitive, ignoring non-alphanumeric chars)
    clean_brand_cmp = re.sub(r'[^a-zA-Z0-9]', '', brand_lower)
    clean_model_cmp = re.sub(r'[^a-zA-Z0-9]', '', model_lower)
    
    if clean_brand_cmp and clean_model_cmp.startswith(clean_brand_cmp):
        return cleaned_model
        
    return f"{brand} {cleaned_model}".strip()

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
        "amazon_eg_link": None,
        "noon_eg_link": None,
        "jumia_eg_link": None,
        "brand_eg_link": None,
        "general_eg_link": None,
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
    
    # We will try gemini-3.5-flash as the primary, and fallback to gemini-flash-latest
    models = ["gemini-3.5-flash", "gemini-flash-latest"]
    
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
                    
                    # Parse grounding links
                    links = {
                        "amazon_eg": None,
                        "noon_eg": None,
                        "jumia_eg": None,
                        "brand_eg": None,
                        "general_eg": None
                    }
                    
                    cand = response.candidates[0]
                    if hasattr(cand, "grounding_metadata") and cand.grounding_metadata:
                        gm = cand.grounding_metadata
                        chunks = gm.grounding_chunks or []
                        supports = gm.grounding_supports or []
                        
                        # 1st pass: scan chunks for direct domain matches
                        for chunk in chunks:
                            if chunk.web and chunk.web.uri:
                                uri = chunk.web.uri
                                uri_lower = uri.lower()
                                title_lower = (chunk.web.title or "").lower()
                                
                                if "amazon" in uri_lower or "amazon" in title_lower:
                                    if not links["amazon_eg"]: links["amazon_eg"] = uri
                                elif "noon" in uri_lower or "noon" in title_lower:
                                    if not links["noon_eg"]: links["noon_eg"] = uri
                                elif "jumia" in uri_lower or "jumia" in title_lower:
                                    if not links["jumia_eg"]: links["jumia_eg"] = uri
                                elif brand.lower() in uri_lower or brand.lower() in title_lower:
                                    if not links["brand_eg"]: links["brand_eg"] = uri
                                    
                        # 2nd pass: check support segments to resolve remaining links by single platform mentions
                        for sup in supports:
                            seg_text = sup.segment.text.lower()
                            chunk_indices = sup.grounding_chunk_indices or []
                            if not chunk_indices:
                                continue
                            
                            chunk_idx = chunk_indices[0]
                            if chunk_idx < len(chunks):
                                uri = chunks[chunk_idx].web.uri
                                if not uri:
                                    continue
                                
                                # Check single platform mentions to avoid false matches
                                platforms_in_seg = [p for p in ["amazon", "noon", "jumia"] if p in seg_text]
                                if len(platforms_in_seg) == 1:
                                    plat = platforms_in_seg[0]
                                    if plat == "amazon" and not links["amazon_eg"]:
                                        links["amazon_eg"] = uri
                                    elif plat == "noon" and not links["noon_eg"]:
                                        links["noon_eg"] = uri
                                    elif plat == "jumia" and not links["jumia_eg"]:
                                        links["jumia_eg"] = uri
                                        
                                if ("brand" in seg_text or "official" in seg_text) and not links["brand_eg"]:
                                    links["brand_eg"] = uri
                                    
                        # 3rd pass: resolve general market price link
                        for chunk in chunks:
                            if chunk.web and chunk.web.uri:
                                uri = chunk.web.uri
                                uri_lower = uri.lower()
                                # If general source is specified, check if it's in the link
                                if general_source:
                                    clean_src = re.sub(r'[^a-z0-9]', '', general_source.lower())
                                    if clean_src and clean_src in uri_lower.replace(".", "").replace("-", ""):
                                        links["general_eg"] = uri
                                        break
                        
                        # Fallback for general link if not found yet (take any chunk not matched to main 3 platforms)
                        if not links["general_eg"]:
                            for chunk in chunks:
                                if chunk.web and chunk.web.uri:
                                    uri = chunk.web.uri
                                    uri_lower = uri.lower()
                                    is_major = any(dom in uri_lower for dom in ["amazon.eg", "noon.com", "jumia.com"])
                                    if not is_major:
                                        links["general_eg"] = uri
                                        break

                    # Standardize keys
                    result = {
                        "amazon_eg": data.get("amazon_eg"),
                        "noon_eg": data.get("noon_eg"),
                        "jumia_eg": data.get("jumia_eg"),
                        "brand_eg": data.get("brand_eg"),
                        "general_eg": data.get("general_eg"),
                        "general_source": general_source,
                        "amazon_eg_link": links["amazon_eg"],
                        "noon_eg_link": links["noon_eg"],
                        "jumia_eg_link": links["jumia_eg"],
                        "brand_eg_link": links["brand_eg"],
                        "general_eg_link": links["general_eg"],
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
