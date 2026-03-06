---
description: Telegram Product Photo Bot — full automated pipeline
---

# Product Photo Bot (Telegram)

## Overview
Send an Excel file to the Telegram bot → Bot reads all products → Searches Google for reference images → Gemini generates white-studio photos → Uploads to Google Drive → Sends link back.

## Steps

1. **Get your Telegram Bot Token** from @BotFather (2 min)

2. **Set up remaining APIs** following `setup_guide.md`:
   - Gemini API key
   - Google Custom Search API + Search Engine ID
   - Google Drive Service Account

3. **Create `.env` file** from `.env.example` and fill in all keys

4. **Place `service_account.json`** in the project root

5. **Deploy to Railway:**
   - Push to GitHub
   - Create Railway project → Deploy from GitHub
   - Add all `.env` values as Railway Variables
   - For `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`: paste the full JSON content
   - Railway deploys and starts the bot automatically (polling mode)

6. **Test the bot:**
   - Open Telegram → find your bot by username
   - Send `/start`
   - Send an Excel `.xlsx` file
   - Watch progress messages come in
   - Receive Google Drive link when done ✅

## Expected Telegram Message Flow

```
User: [sends Excel file]

Bot: 📥 Received products.xlsx! Starting to process... ⏳
Bot: 📊 Found 45 products in products. Generating photos... 🎨
Bot: ⚙️ [A1101] PHILIPS Air Fryer 6.2LTR → Processing 1/45
Bot: 🔍 [A1101] Searching for reference images...
Bot: 🎨 [A1101] Generating studio photos...
     ... (progress every 5 products)
Bot: ☁️ Uploading all photos to Google Drive...
Bot: ✅ Done! Processed 45 products from products.
     📁 Download here: https://drive.google.com/drive/folders/xxxx
```

## Output Folder Structure on Google Drive

```
Product Photos Bot/
└── ExcelFileName/                        ← Excel name
    ├── اجهزة كهربائية البيت والمطبخ/    ← Section name
    │   ├── A1101/
    │   │   ├── photo_1.jpg
    │   │   ├── photo_2.jpg
    │   │   └── photo_3.jpg
    │   └── A1102/ ...
    └── ميكروويف/ ...
```
