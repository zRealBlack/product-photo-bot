import os
import logging
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

logger = logging.getLogger(__name__)

def add_text_to_image(image_path: str, price: str, qty: str) -> str:
    """
    Adds a bottom banner to the image with the price and quantity in Arabic.
    Returns the path to the modified image.
    """
    if not price and not qty:
        return image_path
        
    try:
        img = Image.open(image_path).convert("RGB")
        width, height = img.size
        
        # Banner height
        banner_height = int(height * 0.15)
        if banner_height < 60:
            banner_height = 60
            
        # Create new image with extra space at the bottom
        new_img = Image.new("RGB", (width, height + banner_height), "white")
        new_img.paste(img, (0, 0))
        
        draw = ImageDraw.Draw(new_img)
        
        # Try to load an Arabic-supporting font
        font_path = "C:\\Windows\\Fonts\\tahoma.ttf"
        font_size = int(banner_height * 0.4)
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            # Fallback if tahoma is not found
            font = ImageFont.load_default()
            logger.warning("Could not load Tahoma font, using default font.")

        # Prepare text
        text_parts = []
        if price:
            text_parts.append(f"السعر: {price}")
        if qty:
            text_parts.append(f"الكمية المتاحة: {qty}")
            
        raw_text = "  |  ".join(text_parts)
        
        # Reshape for Arabic
        reshaped_text = arabic_reshaper.reshape(raw_text)
        bidi_text = get_display(reshaped_text)
        
        # Calculate text position (centered in the banner)
        # Using textbbox instead of deprecated textsize
        bbox = draw.textbbox((0, 0), bidi_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (width - text_width) // 2
        y = height + (banner_height - text_height) // 2 - bbox[1] # Adjusting for descent
        
        # Draw text (black on white banner)
        draw.text((x, y), bidi_text, fill="black", font=font)
        
        # Save back to the same path
        new_img.save(image_path, "JPEG", quality=95)
        logger.info(f"Added price/qty overlay to {image_path}")
        return image_path
        
    except Exception as e:
        logger.error(f"Failed to add text to image {image_path}: {e}")
        return image_path
