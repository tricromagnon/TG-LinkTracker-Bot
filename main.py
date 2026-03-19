import re
import os
from urllib.parse import urlparse, parse_qs
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN not set")

# Regex to extract URLs
URL_REGEX = re.compile(r"(https?://\S+)")

# Valid YouTube domains
YOUTUBE_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be"
}

def is_youtube_with_si(url: str) -> bool:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if domain not in YOUTUBE_DOMAINS:
            return False

        query_params = parse_qs(parsed.query)

        # Check if 'si' parameter exists
        return "si" in query_params

    except Exception:
        return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    urls = URL_REGEX.findall(text)

    # Check if any URL matches criteria
    for url in urls:
        if is_youtube_with_si(url):
            await update.message.reply_text("Your YouTube link contains an 'si=' tracking code, please edit the message and remove the si=XXXXXXXX section of the URL or your post will be deleted.")
            return  # only reply once per message


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
 	
