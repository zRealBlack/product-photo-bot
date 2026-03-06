"""
gemini_generator.py
Uses Google Gemini (Imagen 3) to generate professional white-studio product photos.
"""

import os
import logging
import io
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)


STUDIO_PROMPT = (
    "Generate a high-quality, professional product photography image of {product_name}. "
    "The product must be placed on a pure white seamless background in a professional studio setting. "
    "Use soft, even, diffused studio lighting with no harsh shadows. "
    "The product should be centered, fully visible, sharp, and photo-realistic. "
    "The image should look like it belongs in an e-commerce catalog or brand brochure. "
    "No people, no text, no watermarks. Just the product."
)


def generate_studio_photos(
    product_name: str,
    reference_image_paths: list[str],
    output_dir: str,
    num_photos: int = 3,
) -> list[str]:
    """
    Generate `num_photos` white-studio photos for the product using Gemini.
    Returns list of saved photo paths.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    saved_paths = []

    prompt = STUDIO_PROMPT.format(product_name=product_name)

    # Try models in order of preference
    MODELS = ["imagen-3.0-generate-002", "imagen-3.0-fast-generate-001"]

    for i in range(num_photos):
        generated = False
        for model_name in MODELS:
            try:
                result = client.models.generate_images(
                    model=model_name,
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio="1:1",
                        safety_filter_level="BLOCK_FEW",
                        person_generation="DONT_ALLOW",
                    ),
                )

                if result.generated_images:
                    img_data = result.generated_images[0].image.image_bytes
                    file_path = os.path.join(output_dir, f"photo_{i + 1}.jpg")
                    img = Image.open(io.BytesIO(img_data)).convert("RGB")
                    img.save(file_path, "JPEG", quality=95)
                    saved_paths.append(file_path)
                    logger.info(f"Generated photo {i + 1} using {model_name}: {file_path}")
                    generated = True
                    break  # success, move to next photo

            except Exception as e:
                err_str = str(e)
                if "404" in err_str or "NOT_FOUND" in err_str:
                    logger.warning(f"Model {model_name} not available, trying next...")
                    continue  # try next model
                else:
                    logger.error(f"Gemini error for {product_name} photo {i + 1}: {e}")
                    break  # non-404 error, stop retrying

        if not generated:
            logger.warning(f"No image generated for {product_name} photo {i + 1} (all models failed)")

    return saved_paths
