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
        f"اكتب مواصفات فنية ومميزات للمنتج التالي: {product_name}\n\n"
        "الشروط:\n"
        "1. يجب أن تكون باللغة العربية الواضحة والمفهومة.\n"
        "2. اكتب المواصفات في شكل نقاط (Bullets) منظمة وقصيرة.\n"
        "3. لا تكتب أي مقدمات أو خاتمات، فقط المواصفات مباشرة.\n"
        "4. لا تستخدم أكواد برمجية في الإجابة."
    )

    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 300,
        }
    }

    try:
        resp = requests.post(url, json=data, timeout=20)
        resp.raise_for_status()
        result = resp.json()
        
        # Extract text from the Gemini response structure
        candidates = result.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
                
        logger.warning(f"Failed to parse Gemini response for {product_name}")
        return ""
    except Exception as e:
        logger.error(f"Error generating specs via Gemini for '{product_name}': {e}")
        return ""
