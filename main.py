"""
main.py
Telegram Bot — entry point for the Product Photo Bot.

Uses python-telegram-bot v20+ in polling mode.
Simply run: python main.py

Flow:
1. User sends an Excel file (.xlsx) to the bot
2. Bot downloads the file
3. Parses all products/sections/serials from the Excel
4. For each product: searches images → downloads up to 3 high-quality photos
5. Saves photos into: ExcelName / Section / SerialCode /
6. Uploads entire folder to Dropbox (inside "Product Photos Bot" folder)
7. Sends progress messages throughout + final Dropbox link at the end
"""

import os
import sys
import uuid
import logging
import asyncio
import time
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
from modules.spec_generator import generate_product_specs

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")

# Estimated seconds per product (search + download + save)
EST_SECONDS_PER_PRODUCT = 8


# ─────────────────────────────────────────────
# /start command
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *أهلاً بيك في بوت صور المنتجات!*\n\n"
        "ابعتلي ملف Excel (.xlsx) فيه المنتجات وأنا هـ:\n"
        "📊 أقرأ كل المنتجات من الملف\n"
        "🔍 أدور على صور لكل منتج\n"
        "📂 أرتبهم في فولدرات\n"
        "☁️ أرفعهم على Dropbox\n"
        "🔗 أبعتلك اللينك!\n\n"
        "ابعت الملف وأنا هبدأ 🚀",
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
            "⚠️ ابعت ملف Excel (.xlsx أو .xls) بس."
        )
        return

    await update.message.reply_text(
        f"📥 استلمت *{filename}*!\n"
        "هبدأ أشتغل عليه دلوقتي... ⏳",
        parse_mode="Markdown",
    )

    # Run the heavy pipeline in a background task
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
            await send("❌ مفيش منتجات في الملف. راجع الفورمات وابعته تاني.")
            return

        # Calculate estimated time
        est_minutes = max(1, (len(products) * EST_SECONDS_PER_PRODUCT) // 60)
        est_text = f"{est_minutes} دقيقة" if est_minutes < 60 else f"{est_minutes // 60} ساعة و {est_minutes % 60} دقيقة"

        await send(
            f"📊 لقيت *{len(products)} منتج* في *{excel_name}*\n"
            f"⏱ الوقت المتوقع: *{est_text}* تقريباً\n\n"
            f"هبدأ دلوقتي... 🔄"
        )

        failed = []
        start_time = time.time()

        # ── Step 3: Process each product ──
        for idx, product in enumerate(products, start=1):
            serial = product["serial_code"]
            brand = product["brand"]
            model = product["model_name"]
            section = product["section_name"]
            product_display = f"{brand} {model}".strip()

            logger.info(f"[{idx}/{len(products)}] {serial}: {product_display}")

            # Build product output folder
            product_folder = build_product_folder(OUTPUT_DIR, excel_name, section, serial)
            product_temp = os.path.join(temp_session, f"img_{serial}")

            # Search + download photos and generate specs concurrently
            photos_task = asyncio.to_thread(get_reference_images, brand, model, product_temp)
            specs_task = asyncio.to_thread(generate_product_specs, brand, model, product.get("category", ""))
            
            photos, ai_specs = await asyncio.gather(photos_task, specs_task)

            if photos:
                move_photos_to_product_folder(photos, product_folder)
                
                # Create the specs text file
                specs_text = (
                    f"كود الصنف: {serial}\n"
                    f"الماركة: {brand}\n"
                    f"الموديل: {model}\n"
                    f"القسم: {section}\n"
                )
                if product.get("category"):
                    specs_text += f"الفئة: {product['category']}\n"
                    
                if ai_specs:
                    specs_text += f"\n--- المواصفات الفنية ---\n{ai_specs}\n"
                
                # Save as UTF-8 so Arabic renders correctly
                specs_path = os.path.join(product_folder, "مواصفات.txt")
                with open(specs_path, "w", encoding="utf-8") as f:
                    f.write(specs_text)
                
                logger.info(f"✅ {serial} — {len(photos)} photos saved & specs created")
            else:
                logger.warning(f"⚠️ {serial} — No photos found")
                failed.append(serial)

            # Send progress update every 10%
            percent_complete = int((idx / len(products)) * 100)
            # Only trigger on exact 10% increments (10, 20, 30...) or if it's the very last product
            if (percent_complete % 10 == 0 and percent_complete > 0) or idx == len(products):
                # Ensure we only send one message per 10% block
                # Using a dummy attribute on `context.chat_data` would be better, but we don't have context here.
                # Since idx loop is synchronous, we can just track the last reported percentage natively:
                if not hasattr(process_pipeline, "last_reported_percent"):
                    process_pipeline.last_reported_percent = {}
                
                chat_progress = process_pipeline.last_reported_percent.get(chat_id, 0)
                
                if percent_complete > chat_progress:
                    process_pipeline.last_reported_percent[chat_id] = percent_complete
                    elapsed = time.time() - start_time
                    remaining = (elapsed / idx) * (len(products) - idx)
                    rem_min = max(1, int(remaining // 60))
                    
                    await send(
                        f"🔄 **تقدم العمل:** {percent_complete}%\n"
                        f"📦 خلصت *{idx}/{len(products)}* منتج...\n"
                        f"⏱ الوقت المتبقي تقريباً: *{rem_min} دقيقة*"
                    )

        # ── Step 4: Upload to Dropbox ──
        success_count = len(products) - len(failed)
        excel_output_folder = os.path.join(OUTPUT_DIR, excel_name)

        if not os.path.exists(excel_output_folder) or success_count == 0:
            await send(
                f"⚠️ *مقدرتش ألاقي صور* لـ *{excel_name}*\n"
                f"ممكن يكون في مشكلة في أسماء المنتجات."
            )
            return

        await send("☁️ بارفع الصور على Dropbox...")
        dropbox_link = await asyncio.to_thread(upload_output_folder, excel_output_folder)

        # ── Step 5: Send final message ──
        elapsed_total = time.time() - start_time
        elapsed_min = int(elapsed_total // 60)
        elapsed_sec = int(elapsed_total % 60)

        await send(
            f"✅ *تم!* اشتغلت على *{success_count}* منتج من *{excel_name}*\n"
            f"⏱ الوقت: {elapsed_min} دقيقة و {elapsed_sec} ثانية\n\n"
            f"📁 *حمّل الصور من هنا:*\n{dropbox_link}"
        )

        if failed:
            await send(
                f"⚠️ {len(failed)} منتج ملقيتلهمش صور:\n"
                + "\n".join(f"• {s}" for s in failed)
            )

    except Exception as e:
        logger.exception(f"Pipeline error: {e}")
        await send(f"❌ *حصل مشكلة:* {str(e)[:300]}\n\nراجع الملف وابعته تاني.")

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
