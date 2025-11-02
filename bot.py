import os
import re
import yt_dlp
import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found! Set it in Render environment variables.")

WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-service-name.onrender.com/webhook
if not WEBHOOK_URL:
    raise ValueError("❌ WEBHOOK_URL not found! Set it in Render environment variables.")

PORT = int(os.environ.get("PORT", "10000"))

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def safe_filename(title: str) -> str:
    if not title:
        return "video"
    title = re.sub(r"[^\w\s-]", "", title)
    return title.strip().replace(" ", "_")[:50]


def readable_size(size):
    if not size or size <= 0:
        return "?"
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

# -----------------------------------------------------------------------------
# Telegram bot logic
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
app_fastapi = FastAPI()
request = HTTPXRequest(connection_pool_size=20)
application = Application.builder().token(BOT_TOKEN).request(request).build()

@app_fastapi.on_event("startup")
async def on_startup():
    # Set Telegram webhook to point to Render URL
    await application.bot.set_webhook(url=WEBHOOK_URL)
    logging.info(f"🌐 Webhook set to: {WEBHOOK_URL}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📥 Send me a video URL to download.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await update.message.reply_text("⏳ Fetching video details...")

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = [
            f
            for f in info.get("formats", [])
            if f.get("vcodec") != "none" and f.get("acodec") != "none" and f.get("ext") == "mp4"
        ]

        if not formats:
            await update.message.reply_text("⚠️ No downloadable formats found.")
            return

        buttons = []
        for f in formats[-4:]:
            size = f.get("filesize") or f.get("filesize_approx") or 0
            size_str = readable_size(size)
            q = f.get("format_note") or f.get("height", "Unknown")
            label = f"{q}p ({size_str})"
            buttons.append([InlineKeyboardButton(label, callback_data=f["format_id"])])

        context.user_data["video_info"] = info
        await update.message.reply_text(
            f"🎬 *{info.get('title', 'Unknown Title')}*\n\nSelect quality to download:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown",
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching video info:\n`{str(e)}`", parse_mode="Markdown")

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    format_id = query.data
    info = context.user_data.get("video_info")

    if not info:
        await query.message.reply_text("⚠️ Session expired. Please send the link again.")
        return

    url = info["webpage_url"]
    title = info.get("title", "video")
    safe_title = safe_filename(title)
    await query.edit_message_text(f"⬇️ Downloading *{title}* ...", parse_mode="Markdown")

    ydl_opts = {
        "format": format_id,
        "outtmpl": f"{safe_title}.%(ext)s",
        "quiet": True,
        "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(result)

        with open(file_path, "rb") as f:
            await query.message.reply_video(video=f, caption=f"✅ Downloaded: {title}")

        try:
            os.remove(file_path)
        except Exception:
            pass

    except Exception as e:
        await query.message.reply_text(f"❌ Download failed:\n`{str(e)}`", parse_mode="Markdown")

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
application.add_handler(CallbackQueryHandler(download_callback))

# -----------------------------------------------------------------------------
# FastAPI endpoint for Telegram webhook
# -----------------------------------------------------------------------------
@app_fastapi.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

# -----------------------------------------------------------------------------
# Run with uvicorn
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    application.run_polling()
