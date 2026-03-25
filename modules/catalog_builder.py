"""
catalog_builder.py
Generates a premium branded PDF catalog from product data, grouped by sections.

Uses fpdf2 with TTF font support for Unicode text.
Each product gets a card with photo, clean name, serial code, specs, and colors.
The ashtry.com logo appears on every page header and the cover page.
"""

import os
import logging
from pathlib import Path
from fpdf import FPDF

logger = logging.getLogger(__name__)

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "ashtry_logo.png")

# ── Brand Colors ──
COLOR_PRIMARY = (20, 33, 61)       # Dark navy
COLOR_ACCENT = (229, 56, 59)       # Red accent
COLOR_LIGHT_BG = (245, 245, 248)   # Light gray background
COLOR_WHITE = (255, 255, 255)
COLOR_TEXT = (40, 40, 40)
COLOR_TEXT_LIGHT = (120, 120, 120)


class CatalogPDF(FPDF):
    """Custom FPDF subclass for the ashtry.com product catalog."""

    def __init__(self, catalog_title: str = "Product Catalog"):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.catalog_title = catalog_title
        
        # Enable text shaping for Arabic/complex scripts (requires uharfbuzz)
        try:
            self.set_text_shaping(True)
        except Exception as e:
            logger.warning(f"Could not enable text shaping. Arabic may not render correctly: {e}")

        self._setup_fonts()

    def _setup_fonts(self):
        """Register Unicode-capable fonts for Latin + Arabic text with fallbacks."""
        font_dir = os.path.join(ASSETS_DIR, "fonts")
        
        noto_ar_path = os.path.join(font_dir, "NotoSansArabic-Regular.ttf")
        noto_ar_bold = os.path.join(font_dir, "NotoSansArabic-Bold.ttf")
        
        noto_en_path = os.path.join(font_dir, "NotoSans-Regular.ttf")
        noto_en_bold = os.path.join(font_dir, "NotoSans-Bold.ttf")

        # Load Arabic fonts
        if os.path.exists(noto_ar_path):
            self.add_font("NotoArabic", "", fname=noto_ar_path)
            self.add_font("NotoArabic", "B", fname=noto_ar_bold if os.path.exists(noto_ar_bold) else noto_ar_path)
            self.default_font = "NotoArabic"
            
            # Load English fallback fonts
            if os.path.exists(noto_en_path):
                self.add_font("Noto", "", fname=noto_en_path)
                self.add_font("Noto", "B", fname=noto_en_bold if os.path.exists(noto_en_bold) else noto_en_path)
                
                # FPDF2 will automatically use Noto for any characters missing in NotoArabic (like English letters)
                try:
                    self.set_fallback_fonts(["Noto"])
                except Exception as e:
                    logger.warning(f"Could not set font fallbacks: {e}")
        else:
            logger.warning(f"Arabic font not found at {noto_path}. Text will drop if Arabic.")
            
            # Fallback to whatever is available
            backup_noto = os.path.join(font_dir, "NotoSans-Regular.ttf")
            if os.path.exists(backup_noto):
                self.add_font("Noto", "", fname=backup_noto)
                self.default_font = "Noto"
            else:
                self.default_font = "Helvetica"

    def header(self):
        """Page header with logo and line."""
        if self.page_no() == 1:
            return  # Cover page has its own layout

        # Logo in top-left
        if os.path.exists(LOGO_PATH):
            try:
                self.image(LOGO_PATH, x=10, y=8, w=35)
            except Exception:
                pass

        # Title on the right
        self.set_font(self.default_font, "B", 10)
        self.set_text_color(*COLOR_TEXT_LIGHT)
        self.set_xy(50, 12)
        self.cell(0, 6, self.catalog_title, align="L")

        # Accent line
        self.set_draw_color(*COLOR_ACCENT)
        self.set_line_width(0.6)
        self.line(10, 22, 200, 22)

        self.set_y(26)

    def footer(self):
        """Page footer with page number."""
        self.set_y(-15)
        self.set_font(self.default_font, "", 8)
        self.set_text_color(*COLOR_TEXT_LIGHT)
        self.cell(0, 10, f"ashtry.com  |  Page {self.page_no()}/{{nb}}", align="C")

    def add_cover_page(self, product_count: int, subtitle: str = ""):
        """Create a branded cover page."""
        self.add_page()
        self.alias_nb_pages()

        # Background — solid color block at top
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(0, 0, 210, 140, "F")

        # Logo centered
        if os.path.exists(LOGO_PATH):
            try:
                self.image(LOGO_PATH, x=55, y=30, w=100)
            except Exception:
                pass

        # Title
        self.set_y(95)
        self.set_font(self.default_font, "B", 24)
        self.set_text_color(*COLOR_WHITE)
        self.cell(0, 15, self.catalog_title, align="C", new_x="LMARGIN", new_y="NEXT")

        # Subtitle
        if subtitle:
            self.set_font(self.default_font, "", 16)
            self.set_text_color(200, 200, 220)
            self.cell(0, 10, subtitle, align="C", new_x="LMARGIN", new_y="NEXT")

        # Decorative line
        self.set_draw_color(*COLOR_ACCENT)
        self.set_line_width(1)
        self.line(70, 132, 140, 132)

        # Product count
        self.set_y(160)
        self.set_font(self.default_font, "B", 40)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(0, 20, str(product_count), align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_font(self.default_font, "", 14)
        self.set_text_color(*COLOR_TEXT_LIGHT)
        self.cell(0, 8, "Products", align="C", new_x="LMARGIN", new_y="NEXT")

        # Footer
        self.set_y(250)
        self.set_font(self.default_font, "", 10)
        self.set_text_color(*COLOR_TEXT_LIGHT)
        self.cell(0, 8, "www.ashtry.com", align="C")

    def add_section_header(self, title: str, is_main: bool = False):
        """Add a section header. Main headers are bigger (Tabs), sub-headers are smaller."""
        if self.get_y() > 200:
            self.add_page()
            
        self.set_y(self.get_y() + (12 if is_main else 6))
        
        # Draw section block
        self.set_fill_color(*COLOR_PRIMARY)
        y_start = self.get_y()
        self.rect(10, y_start, 190, 18 if is_main else 12, "F")
        
        # Red accent bar on the left
        self.set_fill_color(*COLOR_ACCENT)
        self.rect(10, y_start, 4, 18 if is_main else 12, "F")
        
        # Text
        self.set_xy(18, y_start + (4 if is_main else 2))
        self.set_font(self.default_font, "B", 16 if is_main else 12)
        self.set_text_color(*COLOR_WHITE)
        self.cell(178, 10 if is_main else 8, title, align="L")
        
        self.set_y(y_start + (22 if is_main else 16))

    def add_product_card(self, serial: str, clean_name: str,
                         specs: str, colors: str, photo_path: str = ""):
        """Add a product card. Automatically handles page breaks."""
        card_height = 80  # increased slightly to fit more specs/colors

        # Check if we need a new page
        if self.get_y() + card_height > 265:
            self.add_page()

        y_start = self.get_y() + 2

        # ── Card background ──
        self.set_fill_color(*COLOR_LIGHT_BG)
        self.rect(10, y_start, 190, card_height, "F")

        # ── Product photo ──
        photo_x = 14
        photo_y = y_start + 4
        photo_w = 60
        photo_h = 60

        if photo_path and os.path.exists(photo_path):
            try:
                # White photo background
                self.set_fill_color(*COLOR_WHITE)
                self.rect(photo_x, photo_y, photo_w, photo_h, "F")
                # Fit image inside the box
                self.image(photo_path, x=photo_x + 2, y=photo_y + 2,
                          w=photo_w - 4, h=photo_h - 4, keep_aspect_ratio=True)
            except Exception as e:
                logger.warning(f"Could not embed photo for {serial}: {e}")
                self._draw_no_photo(photo_x, photo_y, photo_w, photo_h)
        else:
            self._draw_no_photo(photo_x, photo_y, photo_w, photo_h)

        # ── Text area (right side) ──
        text_x = photo_x + photo_w + 6
        text_w = 190 - (text_x - 10) - 4

        # Serial code badge
        self.set_fill_color(*COLOR_ACCENT)
        self.set_xy(text_x, y_start + 4)
        self.set_font(self.default_font, "B", 9)
        self.set_text_color(*COLOR_WHITE)
        badge_w = self.get_string_width(f"  {serial}  ") + 4
        self.cell(badge_w, 7, f"  {serial}  ", fill=True, align="C")

        # Colors label (top right of card)
        if colors and colors.lower() != "n/a" and colors.lower() != "none":
            self.set_xy(190 - self.get_string_width(f"الألوان: {colors}") - 5, y_start + 5)
            self.set_font(self.default_font, "", 8)
            self.set_text_color(*COLOR_TEXT_LIGHT)
            self.cell(0, 5, f"الألوان: {colors}", align="R")

        # Product name
        self.set_xy(text_x, y_start + 13)
        self.set_font(self.default_font, "B", 13)
        self.set_text_color(*COLOR_PRIMARY)
        self.multi_cell(text_w, 7, clean_name, new_x="LEFT", new_y="NEXT")

        # No static Specs header, draw specs directly
        spec_y = self.get_y() + 2

        # Specs lines
        if specs:
            self.set_xy(text_x, self.get_y() + 1)
            self.set_font(self.default_font, "", 8)
            self.set_text_color(*COLOR_TEXT)
            # Truncate specs to fit card
            spec_lines = specs.strip().split("\n")
            
            # max 8 lines of specs
            max_lines = 7
            truncated = "\n".join(spec_lines[:max_lines])
            if len(spec_lines) > max_lines:
                truncated += "\n..."
                
            self.multi_cell(text_w, 4.5, truncated, new_x="LEFT", new_y="NEXT")

        # Move cursor below card
        self.set_y(y_start + card_height + 4)

    def _draw_no_photo(self, x, y, w, h):
        """Draw a 'No Photo' placeholder box."""
        self.set_fill_color(230, 230, 235)
        self.rect(x, y, w, h, "F")
        self.set_xy(x, y + (h / 2) - 5)
        self.set_font(self.default_font, "", 9)
        self.set_text_color(*COLOR_TEXT_LIGHT)
        self.cell(w, 10, "No Photo", align="C")


def build_catalog_pdf(
    catalog_title: str,
    subtitle: str,
    products_data: list,
    output_path: str,
) -> str:
    """
    Build a PDF catalog from product data grouped by section.

    Each item in products_data should have:
    {
        "serial_code": str,
        "clean_name": str,
        "section_name": str,
        "specs": str,
        "colors": str,
        "photo_path": str or None,
    }

    Returns the path to the generated PDF.
    """
    pdf = CatalogPDF(catalog_title=catalog_title)

    # Cover page
    pdf.add_cover_page(product_count=len(products_data), subtitle=subtitle)

    # Group products by Sheet -> Section
    from collections import defaultdict
    sheets = defaultdict(lambda: defaultdict(list))
    for product in products_data:
        sheet = product.get("sheet_name", "عام")
        sec = product.get("section_name", "عام")
        
        sheets[sheet][sec].append(product)

    # Start content pages
    pdf.add_page()

    for sheet_name, sections in sheets.items():
        # Draw the big Main header for the Sheet
        pdf.add_section_header(sheet_name, is_main=True)
        
        for sec_name, sec_products in sections.items():
            # If the section name is the exact same as the sheet name, skip the sub-header to avoid repetition
            if sec_name != sheet_name:
                pdf.add_section_header(f"قسم فرعي: {sec_name}", is_main=False)
            
            for product in sec_products:
                pdf.add_product_card(
                    serial=product.get("serial_code", "N/A"),
                    clean_name=product.get("clean_name", "Unknown Product"),
                    specs=product.get("specs", ""),
                    colors=product.get("colors", ""),
                    photo_path=product.get("photo_path") or "",
                )

    # Ensure output directory exists
    Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)
    pdf.output(output_path)
    logger.info(f"Catalog PDF generated: {output_path} ({len(products_data)} products)")
    return output_path
