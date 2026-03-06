"""
gemini_generator.py
Uses Google Gemini (Imagen 3) to generate professional white-studio product photos.
"""

import os
import logging
import base64
from pathlib import Path
import google.generativeai as genai
from PIL import Image
import io

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


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

    # Use Imagen 3 for generation
    try:
        imagen_model = genai.ImageGenerationModel("imagen-3.0-generate-002")
    except Exception:
        logger.warning("Imagen 3 model not available, falling back to imagen-3.0-fast-generate-001")
        imagen_model = genai.ImageGenerationModel("imagen-3.0-fast-generate-001")

    # Build the prompt — include reference image context if available
    full_prompt = prompt
    if reference_image_paths:
        full_prompt = (
            f"Using the provided reference photo as a style guide for the product appearance, "
            f"{prompt}"
        )

    # Prepare reference image for context (use first reference only)
    reference_part = None
    if reference_image_paths:
        try:
            with open(reference_image_paths[0], "rb") as f:
                img_bytes = f.read()
            reference_part = {
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(img_bytes).decode("utf-8"),
                }
            }
        except Exception as e:
            logger.warning(f"Could not load reference image: {e}")

    for i in range(num_photos):
        try:
            # Generate with Imagen
            result = imagen_model.generate_images(
                prompt=full_prompt,
                number_of_images=1,
                aspect_ratio="1:1",
                safety_filter_level="block_few",
                person_generation="dont_allow",
            )

            if result.images:
                img_data = result.images[0]._image_bytes
                file_path = os.path.join(output_dir, f"photo_{i + 1}.jpg")

                # Convert to RGB JPEG and save
                img = Image.open(io.BytesIO(img_data)).convert("RGB")
                img.save(file_path, "JPEG", quality=95)
                saved_paths.append(file_path)
                logger.info(f"Generated photo {i + 1}: {file_path}")
            else:
                logger.warning(f"No image returned for photo {i + 1} of {product_name}")

        except Exception as e:
            logger.error(f"Gemini generation failed for {product_name} photo {i + 1}: {e}")

    return saved_paths
