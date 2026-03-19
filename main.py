import re
import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

# Regex to extract URLs
URL_REGEX = re.compile(r"(https?://\S+)")

# Domains and their tracking parameters
PLATFORMS = {
    "youtube": {
        "domains": {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"},
        "tracking_params": ["si"]
    },
    "facebook": {
        "domains": {"facebook.com", "www.facebook.com", "fb.watch", "l.facebook.com"},
        "tracking_params": ["fbclid"]
    },
    "x": {  # Twitter/X
        "domains": {"twitter.com", "www.twitter.com", "x.com", "www.x.com", "t.co"},
        "tracking_params": ["t", "s", "ref_src", "ref_url"]
    },
    "instagram": {
        "domains": {"instagram.com", "www.instagram.com"},
        "tracking_params": ["igshid", "igsh"]
    }
}

def clean_url(url: str, tracking_params: list[str]) -> list[tuple[str, str]]:
    """
    Returns list of tuples: (cleaned_url, offending_param=VALUE) for first offending param per URL.
    """
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    for param in tracking_params:
        if param in query:
            offending = f"{param}={query[param][0]}"
            query.pop(param)
            clean_query = urlencode(query, doseq=True)
            cleaned_url = urlunparse(parsed._replace(query=clean_query))
            return [(cleaned_url, offending)]
    return []

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    urls = URL_REGEX.findall(text)
    messages = []

    for url in urls:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        for platform, data in PLATFORMS.items():
            if domain in data["domains"]:
                offending_info = clean_url(url, data["tracking_params"])
                for cleaned_url, offending in offending_info:
                    messages.append((offending, cleaned_url))

    if messages:
        # Build one reply message
        reply_lines = []
        for offending, cleaned_url in messages:
            reply_lines.append(
                f"Tracking section '<b>{offending}</b>' found. Cleaned URL: "
                f"<a href=\"{cleaned_url}\">{cleaned_url}</a>"
            )

        reply_text = "Please edit your comment to remove the tracking parameters:\n\n" + "\n".join(reply_lines) + "\n\nFailure to do so may result in your message being deleted."
        await update.message.reply_text(reply_text, parse_mode="HTML", disable_web_page_preview=True)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
