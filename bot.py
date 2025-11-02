import os
import re
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

# 🔹 Load token securely from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found! Please set it in Render environment variables.")

# 🔹 Safe filename generator (to prevent “File name too long” errors)
def safe_filename(title: str) -> str:
    if not title:
        return "video"
    # Remove emojis, symbols, etc.
    title = re.sub(r"[^\w\s-]", "", title)
    # Replace spaces with underscores and truncate to 50 chars
    return title.strip().replace(" ", "_")[:50]


# 🔹 Convert bytes to readable sizes
def readable_size(size):
    if not size or size <= 0:
        return "?"
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


# 🔹 /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📥 Send me a video URL (Facebook, Instagram, YouTube, etc.) to download.")


# 🔹 Handle URLs sent by user
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

        # Show last few formats (usually best quality)
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


# 🔹 Handle quality button clicks (download phase)
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    format_id = query.data
    info = context.user_data.get("video_info")

    if not info:
        await query.message.reply_text("⚠️ Session expired. Please send the video link again.")
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

        # Send video to user
        with open(file_path, "rb") as f:
            await query.message.reply_video(video=f, caption=f"✅ Downloaded: {title}")

        # Optional cleanup
        try:
            os.remove(file_path)
        except Exception:
            pass

    except Exception as e:
        await query.message.reply_text(f"❌ Download failed:\n`{str(e)}`", parse_mode="Markdown")


# 🔹 Main entry
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(download_callback))

    print("🤖 Bot is running (polling mode)...")
    app.run_polling()


if __name__ == "__main__":
    main()
