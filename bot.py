import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_TOKEN = ""  # 🔹 Replace this

# Convert bytes to readable sizes
def readable_size(size):
    if not size or size <= 0:
        return "?"
    for unit in ['B','KB','MB','GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📥 Send me a video URL (Facebook, Instagram, YouTube, etc.) to download.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await update.message.reply_text("⏳ Fetching video details...")

    ydl_opts = {"quiet": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = [
            f for f in info['formats']
            if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('ext') == 'mp4'
        ]

        buttons = []
        for f in formats[-4:]:  # Show last few (usually best)
            size = f.get("filesize") or f.get("filesize_approx") or 0
            size_str = readable_size(size)
            q = f.get('format_note') or f.get('height', 'Unknown')
            label = f"{q}p ({size_str})"
            buttons.append([InlineKeyboardButton(label, callback_data=f['format_id'])])

        context.user_data['video_info'] = info
        await update.message.reply_text(
            f"🎬 *{info.get('title')}*\n\nSelect quality to download:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    format_id = query.data
    info = context.user_data.get('video_info')

    url = info['webpage_url']
    title = info.get('title', 'video')
    await query.edit_message_text(f"⬇️ Downloading *{title}* ...", parse_mode="Markdown")

    ydl_opts = {
        "format": format_id,
        "outtmpl": "%(title)s.%(ext)s",
        "quiet": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(result)

        await query.message.reply_video(
            video=open(file_path, "rb"),
            caption=f"✅ Downloaded: {title}"
        )
    except Exception as e:
        await query.message.reply_text(f"❌ Download failed: {str(e)}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(download_callback))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
