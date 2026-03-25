"""
main.py
Telegram Bot — entry point for the Product Photo Bot.

Uses python-telegram-bot v20+ in polling mode.
Simply run: python main.py

Commands:
  /start   — Show welcome message with available commands
  /photos  — Set mode to Photo Pipeline (search images → folders → Dropbox)
  /catalog — Set mode to Catalog PDF (search images → specs → branded PDF)

Flow:
  1. User picks a command (/photos or /catalog)
  2. User sends an Excel file (.xlsx)
  3. Bot processes based on active mode
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
from modules.catalog_builder import build_catalog_pdf

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")

# Estimated seconds per product (search + download + save)
EST_SECONDS_PER_PRODUCT = 8
EST_SECONDS_PER_PRODUCT_CATALOG = 15  # catalog also generates specs


# ─────────────────────────────────────────────
# /start command
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *أهلاً بيك في بوت صور المنتجات!*\n\n"
        "اختار الأمر اللي عايزه وبعدين ابعت ملف Excel:\n\n"
        "📸 /photos — *تحميل صور المنتجات*\n"
        "   بيدور على صور لكل منتج، ينظمهم في فولدرات، ويرفعهم على Dropbox\n\n"
        "📄 /catalog — *كتالوج PDF*\n"
        "   بيعمل كتالوج PDF بتصميم احترافي فيه صور المنتجات والمواصفات مع لوجو ashtry.com\n\n"
        "اختار أمر وابعت الملف! 🚀",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────
# /photos command — set mode
# ─────────────────────────────────────────────
async def photos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "photos"
    await update.message.reply_text(
        "📸 *وضع الصور — Photos Mode*\n\n"
        "ابعتلي ملف Excel (.xlsx) وأنا هـ:\n"
        "🔍 أدور على صور لكل منتج\n"
        "📂 أرتبهم في فولدرات\n"
        "☁️ أرفعهم على Dropbox\n"
        "🔗 أبعتلك اللينك!\n\n"
        "ابعت الملف دلوقتي 👇",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────
# /catalog command — set mode
# ─────────────────────────────────────────────
async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "catalog"
    await update.message.reply_text(
        "📄 *وضع الكتالوج — Catalog Mode*\n\n"
        "ابعتلي ملف Excel (.xlsx) وأنا هـ:\n"
        "🔍 أدور على صور لكل منتج\n"
        "📝 أكتب مواصفات لكل منتج بالذكاء الاصطناعي\n"
        "📄 أعمل كتالوج PDF بتصميم احترافي مع لوجو ashtry.com\n"
        "☁️ أرفع الـ PDF على Dropbox\n"
        "📎 أبعتلك الـ PDF هنا!\n\n"
        "ابعت الملف دلوقتي 👇",
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

    # Check which mode is active
    mode = context.user_data.get("mode", None)

    if mode is None:
        await update.message.reply_text(
            "⚠️ *اختار mode الأول!*\n\n"
            "📸 /photos — صور المنتجات + Dropbox\n"
            "📄 /catalog — كتالوج PDF احترافي\n\n"
            "اختار أمر وبعدين ابعت الملف تاني.",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(
        f"📥 استلمت *{filename}*!\n"
        f"الوضع: *{'📸 صور' if mode == 'photos' else '📄 كتالوج'}*\n"
        "هبدأ أشتغل عليه دلوقتي... ⏳",
        parse_mode="Markdown",
    )

    # Clear mode after use so user must pick again for next file
    context.user_data["mode"] = None

    # Run the heavy pipeline in a background task
    if mode == "photos":
        asyncio.create_task(
            photos_pipeline(context.bot, chat_id, doc, filename)
        )
    elif mode == "catalog":
        asyncio.create_task(
            catalog_pipeline(context.bot, chat_id, doc, filename)
        )


# ─────────────────────────────────────────────
# Photos pipeline (existing logic)
# ─────────────────────────────────────────────
async def photos_pipeline(bot: Bot, chat_id: int, doc, filename: str):
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
        last_reported_percent = 0

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
            if (percent_complete % 10 == 0 and percent_complete > 0) or idx == len(products):
                if percent_complete > last_reported_percent:
                    last_reported_percent = percent_complete
                    elapsed = time.time() - start_time
                    remaining = (elapsed / idx) * (len(products) - idx)
                    rem_min = max(1, int(remaining // 60))

                    await send(
                        f"🔄 *تقدم العمل:* {percent_complete}%\n"
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
# Catalog PDF pipeline (NEW)
# ─────────────────────────────────────────────
async def catalog_pipeline(bot: Bot, chat_id: int, doc, filename: str):
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

        # Calculate estimated time (catalog takes longer due to specs)
        est_minutes = max(1, (len(products) * EST_SECONDS_PER_PRODUCT_CATALOG) // 60)
        est_text = f"{est_minutes} دقيقة" if est_minutes < 60 else f"{est_minutes // 60} ساعة و {est_minutes % 60} دقيقة"

        await send(
            f"📊 لقيت *{len(products)} منتج* في *{excel_name}*\n"
            f"⏱ الوقت المتوقع: *{est_text}* تقريباً\n\n"
            f"📄 هبدأ أجهز الكتالوج... 🎨"
        )

        catalog_products = []
        failed = []
        start_time = time.time()
        last_reported_percent = 0

        # ── Step 3: Process each product (photos + specs) ──
        for idx, product in enumerate(products, start=1):
            serial = product["serial_code"]
            brand = product["brand"]
            model = product["model_name"]
            section = product["section_name"]
            product_display = f"{brand} {model}".strip()

            logger.info(f"[Catalog {idx}/{len(products)}] {serial}: {product_display}")

            product_temp = os.path.join(temp_session, f"img_{serial}")

            # Search + download first photo and generate specs concurrently
            photos_task = asyncio.to_thread(get_reference_images, brand, model, product_temp)
            specs_task = asyncio.to_thread(generate_product_specs, brand, model, product.get("category", ""))

            photos, ai_result = await asyncio.gather(photos_task, specs_task)

            # Use the first photo for the catalog
            photo_path = photos[0] if photos else None

            catalog_products.append({
                "serial_code": serial,
                "clean_name": ai_result.get("clean_name", product_display),
                "model_name": model,
                "section_name": section,
                "specs": ai_result.get("specs", ""),
                "colors": ai_result.get("colors", ""),
                "photo_path": photo_path,
            })

            if not photos:
                failed.append(serial)

            # Send progress update every 10%
            percent_complete = int((idx / len(products)) * 100)
            if (percent_complete % 10 == 0 and percent_complete > 0) or idx == len(products):
                if percent_complete > last_reported_percent:
                    last_reported_percent = percent_complete
                    elapsed = time.time() - start_time
                    remaining = (elapsed / idx) * (len(products) - idx)
                    rem_min = max(1, int(remaining // 60))

                    await send(
                        f"🔄 *تقدم العمل:* {percent_complete}%\n"
                        f"📦 خلصت *{idx}/{len(products)}* منتج...\n"
                        f"⏱ الوقت المتبقي تقريباً: *{rem_min} دقيقة*"
                    )

        # ── Step 4: Build PDF catalog ──
        await send("📄 بأعمل الكتالوج PDF... 🎨")

        from datetime import datetime
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        pdf_title = f"Ashtry Catalog [{today_date}]"
        pdf_filename = f"{pdf_title}.pdf"
        pdf_path = os.path.join(temp_session, pdf_filename)

        await asyncio.to_thread(
            build_catalog_pdf, pdf_title, excel_name, catalog_products, pdf_path
        )

        # ── Step 5: Send PDF directly to user via Telegram ──
        success_count = len(products) - len(failed)

        try:
            with open(pdf_path, "rb") as pdf_file:
                await bot.send_document(
                    chat_id=chat_id,
                    document=pdf_file,
                    filename=pdf_filename,
                    caption=f"📄 *كتالوج {excel_name}*\n{len(catalog_products)} منتج",
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.error(f"Could not send PDF via Telegram: {e}")
            await send(f"❌ مقدرتش أبعت الـ PDF: {str(e)[:200]}")
            return

        # ── Step 6: Send final message ──
        elapsed_total = time.time() - start_time
        elapsed_min = int(elapsed_total // 60)
        elapsed_sec = int(elapsed_total % 60)

        await send(
            f"✅ *الكتالوج جاهز!* 🎉\n\n"
            f"📊 *{success_count}* منتج في الكتالوج\n"
            f"⏱ الوقت: {elapsed_min} دقيقة و {elapsed_sec} ثانية"
        )

        if failed:
            await send(
                f"⚠️ {len(failed)} منتج ملقيتلهمش صور (موجودين في الكتالوج بدون صورة):\n"
                + "\n".join(f"• {s}" for s in failed)
            )

    except Exception as e:
        logger.exception(f"Catalog pipeline error: {e}")
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
    app.add_handler(CommandHandler("photos", photos_command))
    app.add_handler(CommandHandler("catalog", catalog_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Text fallback: any text that is not a command acts as /start
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))

    logger.info("🤖 Product Photo Bot is running (Photos + Catalog modes)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
