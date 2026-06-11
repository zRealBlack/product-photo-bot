"""
price_finder.py
Uses Serper API + Google Search grounding fallbacks to search for product prices in Egypt.
"""

import os
import json
import time
import logging
import re
import requests
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

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

def search_serper(query: str) -> str:
    """Query Google search results using Serper API targeted to Egypt."""
    if not SERPER_API_KEY:
        return ""
    
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "gl": "eg",  # Target Egypt search results!
        "hl": "ar",  # Arabic/English language preference
        "num": 8
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        
        results = []
        organic = data.get("organic", [])
        for idx, item in enumerate(organic, start=1):
            title = item.get("title", "")
            link = item.get("link", "")
            
            snippet_parts = []
            if item.get("snippet"):
                snippet_parts.append(item.get("snippet"))
            if item.get("priceRange"):
                snippet_parts.append(f"Price Info: {item.get('priceRange')}")
                
            snippet_str = " | ".join(snippet_parts)
            results.append(
                f"Result #{idx}:\n"
                f"Title: {title}\n"
                f"Link: {link}\n"
                f"Snippet: {snippet_str}\n"
            )
            
        return "\n".join(results)
    except Exception as e:
        logger.error(f"Serper search failed for '{query}': {e}")
        return ""

def find_egyptian_prices(brand: str, model: str) -> dict:
    """
    Search for product prices in Egypt.
    Uses Serper API + Gemini for free/fast lookups if SERPER_API_KEY is available.
    Otherwise, falls back to Google Search Grounding.
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
    
    # ── Option A: Serper API + Gemini (Preferred, Free Grounding & No Rate Limits) ──
    if SERPER_API_KEY:
        query = f"{product_name} price in Egypt EGP"
        logger.info(f"Querying Serper for '{query}'...")
        search_text = search_serper(query)
        
        if search_text:
            prompt = (
                f"You are a pricing analyst for the Egyptian market. We did a web search for the product '{product_name}' and got these results:\n\n"
                f"{search_text}\n\n"
                f"Extract the current prices in Egypt (in EGP) on:\n"
                f"1. Amazon Egypt (amazon.eg)\n"
                f"2. Noon Egypt (noon.com)\n"
                f"3. Jumia Egypt (jumia.com.eg)\n"
                f"4. Official brand website in Egypt\n"
                f"5. General market price (e.g. B.Tech, Raya, etc.)\n\n"
                f"Return the output STRICTLY as a JSON object with the following keys:\n"
                f"{{\n"
                f"  \"amazon_eg\": price as float or null,\n"
                f"  \"noon_eg\": price as float or null,\n"
                f"  \"jumia_eg\": price as float or null,\n"
                f"  \"brand_eg\": price as float or null,\n"
                f"  \"general_eg\": price as float or null,\n"
                f"  \"general_source\": string name of the specific store/source where the general price was found or null,\n"
                f"  \"currency\": \"EGP\"\n"
                f"}}\n"
                f"Return ONLY the raw JSON object. Do not include markdown code block formatting."
            )
            
            client = genai.Client(api_key=GEMINI_API_KEY)
            models = ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-flash-latest"]
            
            for model_name in models:
                try:
                    logger.info(f"Extracting prices using model {model_name}...")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    text = response.text.strip()
                    if text.startswith("```json"): text = text[7:]
                    if text.startswith("```"): text = text[3:]
                    if text.endswith("```"): text = text[:-3]
                    text = text.strip()
                    
                    data = json.loads(text)
                    source_val = data.get("general_source")
                    general_source = str(source_val).strip() if source_val else None
                    
                    result = {
                        "amazon_eg": data.get("amazon_eg"),
                        "noon_eg": data.get("noon_eg"),
                        "jumia_eg": data.get("jumia_eg"),
                        "brand_eg": data.get("brand_eg"),
                        "general_eg": data.get("general_eg"),
                        "general_source": general_source,
                        "currency": "EGP"
                    }
                    
                    for key in ["amazon_eg", "noon_eg", "jumia_eg", "brand_eg", "general_eg"]:
                        val = result[key]
                        if val is not None:
                            try:
                                result[key] = float(val)
                            except (ValueError, TypeError):
                                result[key] = None
                                
                    logger.info(f"Serper + Gemini success for '{product_name}': {result}")
                    return result
                except Exception as e:
                    logger.error(f"Failed extracting price with model {model_name}: {e}")
                    continue
            logger.warning("All extraction models failed for Serper output. Falling back to Search Grounding...")

    # ── Option B: Fallback to Gemini Google Search Grounding ──
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
    models = ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-flash-latest"]
    max_retries = 2
    import random

    for attempt in range(max_retries):
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
                if text.startswith("```json"): text = text[7:]
                if text.startswith("```"): text = text[3:]
                if text.endswith("```"): text = text[:-3]
                text = text.strip()

                try:
                    data = json.loads(text)
                    source_val = data.get("general_source")
                    general_source = str(source_val).strip() if source_val else None
                    
                    result = {
                        "amazon_eg": data.get("amazon_eg"),
                        "noon_eg": data.get("noon_eg"),
                        "jumia_eg": data.get("jumia_eg"),
                        "brand_eg": data.get("brand_eg"),
                        "general_eg": data.get("general_eg"),
                        "general_source": general_source,
                        "currency": "EGP"
                    }
                    
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
                    break
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
