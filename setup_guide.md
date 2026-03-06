# 🛠️ Setup Guide — Product Photo Bot (Telegram)

Follow these steps in order. Total time: ~20-30 minutes.

---

## Step 1 — Get Your Telegram Bot Token ⚡ (2 minutes)

1. Open Telegram → search for **@BotFather**
2. Send `/newbot`
3. Enter a name for your bot, e.g.: `Product Photos Bot`
4. Enter a username (must end in `bot`), e.g.: `product_photos_xyz_bot`
5. BotFather will reply with your token, for example:
   ```
   123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
6. Copy it → save as `TELEGRAM_BOT_TOKEN` in your `.env` file

---

## Step 2 — Get a Gemini API Key (5 minutes)

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **"Create API Key"**
3. Copy it → save as `GEMINI_API_KEY` in your `.env`

> The bot uses **Imagen 3** (`imagen-3.0-generate-002`) for photo generation.
> If your account doesn't have access, it auto-falls back to `imagen-3.0-fast-generate-001`.

---

## Step 3 — Google Custom Search API (10 minutes)

This lets the bot search Google Images for product reference photos.

### 3.1 Enable the API & get a key
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (name it anything, e.g. "photo-bot")
3. Search **"Custom Search API"** → Enable it
4. Go to **Credentials → Create Credentials → API Key**
5. Copy it → save as `GOOGLE_SEARCH_API_KEY` in your `.env`

### 3.2 Create a Custom Search Engine
1. Go to [programmablesearchengine.google.com](https://programmablesearchengine.google.com)
2. Click **Add** → Create new search engine
3. Under **Sites to search** → select **"Search the entire web"**
4. In Settings → enable **Image search**
5. Copy the **Search Engine ID (cx)** → save as `GOOGLE_SEARCH_CX` in your `.env`

---

## Step 4 — Google Drive Service Account (10 minutes)

This lets the bot upload folders to Google Drive automatically.

1. Go back to [console.cloud.google.com](https://console.cloud.google.com) (same project)
2. Search **"Google Drive API"** → Enable it
3. Go to **IAM & Admin → Service Accounts → Create Service Account**
   - Name it: `photo-bot-drive`
   - Click **Done**
4. Click on the new service account → **Keys → Add Key → Create New Key → JSON**
5. A file called `service_account.json` will download automatically
6. **Place this file in the project root folder** (same folder as `main.py`)

> The bot will create a **"Product Photos Bot"** folder in this service account's Drive.
> To access the files yourself, go to drive.google.com, open the shared link the bot sends.

---

## Step 5 — Create Your `.env` File

Copy `.env.example` → rename to `.env` → fill in all values:

```env
TELEGRAM_BOT_TOKEN=123456789:AAHxxxxxxxxx...
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxx
GOOGLE_SEARCH_API_KEY=AIzaSyxxxxxxxxxxxxxxxx
GOOGLE_SEARCH_CX=xxxxxxxxxxxxxxxxx
GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON=service_account.json
```

---

## Step 6 — Deploy to Railway (5 minutes)

### 6.1 Push to GitHub
```bash
git init
git add .
git commit -m "Telegram product photo bot"
git remote add origin https://github.com/YOUR_USERNAME/product-photo-bot.git
git push -u origin main
```

### 6.2 Deploy
1. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub**
2. Select your repository
3. Go to **Variables** tab → add all your `.env` values:
   - `TELEGRAM_BOT_TOKEN`
   - `GEMINI_API_KEY`
   - `GOOGLE_SEARCH_API_KEY`
   - `GOOGLE_SEARCH_CX`
   - `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON` → paste the **full content** of `service_account.json` as the value
4. Railway will build and start the bot automatically

---

## Step 7 — Test It! ✅

1. Open Telegram → search for your bot by its username
2. Send `/start`
3. Send your Excel `.xlsx` file
4. Watch for progress messages!
5. Receive your Google Drive link 🎉

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Bot not responding | Check Railway logs; verify `TELEGRAM_BOT_TOKEN` |
| No images found | Check `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_CX` |
| Gemini error | Verify `GEMINI_API_KEY` has Imagen access |
| Drive upload fails | Check service account JSON is valid and Drive API is enabled |
| No products found | Check Excel format matches: serial in col A, model in col D |
