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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

def _call_openai(prompt: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that generates product specifications in JSON format."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 600
    }
    resp = requests.post(url, headers=headers, json=data, timeout=20)
    resp.raise_for_status()
    # Force UTF-8
    resp.encoding = 'utf-8'
    return resp.json()["choices"][0]["message"]["content"].strip()

def _call_gemini(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 600,
            "responseMimeType": "application/json",
        }
    }
    resp = requests.post(url, json=data, timeout=20)
    resp.raise_for_status()
    resp.encoding = 'utf-8'
    result = resp.json()
    candidates = result.get("candidates", [])
    if candidates:
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if parts:
            text = parts[0].get("text", "").strip()
            # Clean up potential markdown code blocks
            if text.startswith("```json"): text = text[7:]
            if text.startswith("```"): text = text[3:]
            if text.endswith("```"): text = text[:-3]
            return text.strip()
    return ""

def generate_product_specs(brand: str, model: str, category: str = "") -> dict:
    """
    Calls OpenAI (preferred if key set) or Gemini API to get a structured JSON response.
    Returns:
    {
        "clean_name": str,  # The readable English product name
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

    if not OPENAI_API_KEY and not GEMINI_API_KEY:
        logger.warning("No API keys set (neither OPENAI_API_KEY nor GEMINI_API_KEY). Cannot generate specs.")
        return fallback_result

    product_name = f"{brand} {model}".strip()
    if category:
        product_name += f" ({category})"

    prompt = (
        f"Analyze the following product: {product_name}\n\n"
        "Return a valid JSON object with EXACTLY these three keys:\n"
        "1. \"clean_name\": A clean, highly professional, Short product name strictly in ENGLISH (e.g., 'Philips Air Fryer NA322'). Do NOT output Arabic here even if the input contains Arabic.\n"
        "2. \"specs\": A detailed bulleted list of key technical specs and features in plain text. Use hyphens (-) for bullets. No markdown asterisks. Do NOT start the list with 'المواصفات:', 'Specs:', or any title. Just the bullets directly.\n"
        "3. \"colors\": The available color options (e.g., 'Black', 'White', 'Silver') or 'N/A' if unknown.\n\n"
        "Do not include any code block formatting like ```json in the output."
    )

    try:
        if OPENAI_API_KEY:
            text = _call_openai(prompt)
        else:
            text = _call_gemini(prompt)

        if not text:
            logger.warning(f"No text returned from AI for {product_name}")
            return fallback_result

        try:
            parsed_json = json.loads(text)
            
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
            logger.error(f"Failed to parse AI JSON: {je} | Raw: {text}")
            return fallback_result
                
    except Exception as e:
        logger.error(f"Error generating specs for '{product_name}': {e}")
        return fallback_result
