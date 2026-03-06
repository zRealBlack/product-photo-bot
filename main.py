"""
main.py
Telegram Bot — entry point for the Product Photo Bot.

Uses python-telegram-bot v20+ in polling mode.
Simply run: python main.py

Flow:
1. User sends an Excel file (.xlsx) to the bot
2. Bot downloads the file
3. Parses all products/sections/serials from the Excel
4. For each product: searches Google Images → downloads up to 3 high-quality photos
5. Saves photos into: ExcelName / Section / SerialCode /
6. Uploads entire folder to Dropbox (inside "Product Photos Bot" folder)
7. Sends progress messages throughout + final Dropbox link at the end
"""

import os
import sys
import uuid
import logging
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

from modules.excel_parser import parse_excel
from modules.image_searcher import get_reference_images
from modules.folder_builder import build_product_folder, move_photos_to_product_folder, cleanup_temp_dir
from modules.drive_uploader import upload_output_folder

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")


# ─────────────────────────────────────────────
# /start command
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to the Product Photo Bot!*\n\n"
        "Send me an Excel file (.xlsx) with your products list and I will:\n"
        "📊 Parse all products\n"
        "🔍 Search Google Images for each product\n"
        "📂 Organise photos into folders by section & serial code\n"
        "☁️ Upload everything to Dropbox\n"
        "🔗 Send you the download link!\n\n"
        "Just send the Excel file to get started!",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────
# Handle incoming documents (Excel files)
# ─────────────────────────────────────────────
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    chat_id = update.effective_chat.id

    # Only accept Excel files
    filename = doc.file_name or "file"
    if not (filename.endswith(".xlsx") or filename.endswith(".xls")):
        await update.message.reply_text(
            "⚠️ Please send an Excel file (.xlsx or .xls)."
        )
        return

    await update.message.reply_text(
        f"📥 Received *{filename}*!\n"
        "Starting to process your products... I'll keep you updated! ⏳",
        parse_mode="Markdown",
    )

    # Run the heavy pipeline in a background thread so the bot stays responsive
    asyncio.create_task(
        process_pipeline(context.bot, chat_id, doc, filename)
    )


# ─────────────────────────────────────────────
# Full processing pipeline (async)
# ─────────────────────────────────────────────
async def process_pipeline(bot: Bot, chat_id: int, doc, filename: str):
    temp_session = os.path.join(TEMP_DIR, uuid.uuid4().hex)
    Path(temp_session).mkdir(parents=True, exist_ok=True)
    excel_path = os.path.join(temp_session, filename)

    async def send(text: str):
        """Helper to send a message to the user."""
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    try:
        # ── Step 1: Download the Excel ──
        tg_file = await bot.get_file(doc.file_id)
        await tg_file.download_to_drive(excel_path)
        logger.info(f"Downloaded Excel to: {excel_path}")

        # ── Step 2: Parse Excel ──
        parsed = parse_excel(excel_path)
        excel_name = parsed["excel_name"]
        products = parsed["products"]

        if not products:
            await send("❌ No products found in the file. Please check the format.")
            return

        await send(
            f"📊 Found *{len(products)} products* in *{excel_name}*.\n"
            f"Generating studio photos now... 🎨"
        )

        failed = []

        # ── Step 3: Process each product ──
        for idx, product in enumerate(products, start=1):
            serial = product["serial_code"]
            brand = product["brand"]
            model = product["model_name"]
            section = product["section_name"]
            product_display = f"{brand} {model}".strip()

            logger.info(f"[{idx}/{len(products)}] {serial}: {product_display}")

            # Send progress every 5 products or for the first one
            if idx == 1 or idx % 5 == 0:
                await send(
                    f"⚙️ `[{serial}]` {product_display[:45]}\n"
                    f"→ Processing {idx}/{len(products)}"
                )

            # Build product output folder
            product_folder = build_product_folder(OUTPUT_DIR, excel_name, section, serial)
            product_temp = os.path.join(temp_session, f"img_{serial}")

            # Search + download product images directly
            await send(f"🔍 `[{serial}]` Searching for images...")
            photos = await asyncio.to_thread(
                get_reference_images, brand, model, product_temp
            )

            if photos:
                move_photos_to_product_folder(photos, product_folder)
                logger.info(f"✅ {serial} — {len(photos)} photos saved")
            else:
                logger.warning(f"⚠️ {serial} — No photos found")
                failed.append(serial)

        # ── Step 4: Upload to Dropbox ──
        success_count = len(products) - len(failed)
        excel_output_folder = os.path.join(OUTPUT_DIR, excel_name)

        if not os.path.exists(excel_output_folder) or success_count == 0:
            await send(
                f"⚠️ *No photos were generated* for *{excel_name}*.\n"
                f"This usually means the Gemini API key doesn't have access to Imagen.\n"
                f"Check your GEMINI_API_KEY has Imagen access in Google AI Studio."
            )
            return

        await send("☁️ Uploading all photos to Dropbox...")
        dropbox_link = await asyncio.to_thread(upload_output_folder, excel_output_folder)

        # ── Step 5: Send final message ──
        await send(
            f"✅ *Done!* Processed *{success_count}* products from *{excel_name}*.\n\n"
            f"📁 *Download your photos here:*\n{dropbox_link}"
        )

        if failed:
            await send(
                f"⚠️ {len(failed)} products had no photos generated:\n"
                + "\n".join(f"• {s}" for s in failed)
            )

    except Exception as e:
        logger.exception(f"Pipeline error: {e}")
        await send(f"❌ *Error:* {str(e)[:300]}\n\nPlease check the file and try again.")

    finally:
        cleanup_temp_dir(temp_session)


# ─────────────────────────────────────────────
# Start the bot
# ─────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set! Please add it to your .env file.")
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info("🤖 Product Photo Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
