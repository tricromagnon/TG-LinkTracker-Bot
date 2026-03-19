import re
import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

URL_REGEX = re.compile(r"(https?://\S+)")

PLATFORMS = {
    "youtube": {
        "domains": {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"},
        "tracking_params": ["si"]
    },
    "facebook": {
        "domains": {"facebook.com", "www.facebook.com", "fb.watch", "l.facebook.com"},
        "tracking_params": ["fbclid"]
    },
    "x": {
        "domains": {"twitter.com", "www.twitter.com", "x.com", "www.x.com", "t.co"},
        "tracking_params": ["t", "s", "ref_src", "ref_url"]
    },
    "instagram": {
        "domains": {"instagram.com", "www.instagram.com"},
        "tracking_params": ["igshid", "igsh"]
    }
}


def extract_urls(text: str):
    return URL_REGEX.findall(text)


def find_offending_urls(text: str):
    urls = extract_urls(text)
    results = []

    for url in urls:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        query = parse_qs(parsed.query)

        for platform, data in PLATFORMS.items():
            if domain in data["domains"]:
                for param in data["tracking_params"]:
                    if param in query:
                        offending = f"{param}={query[param][0]}"
                        # remove only that param
                        query_copy = query.copy()
                        query_copy.pop(param)

                        clean_query = urlencode(query_copy, doseq=True)
                        cleaned_url = urlunparse(parsed._replace(query=clean_query))

                        results.append((offending, cleaned_url))
                        break  # only first offending param per URL

    return results


async def process_message(message, context: ContextTypes.DEFAULT_TYPE):
    if not message or not message.text:
        return

    offending = find_offending_urls(message.text)
    user_name = message.from_user.full_name

    # CASE 1: Offending links exist
    if offending:
        lines = []
        for off, cleaned in offending:
            lines.append(
                f"Tracking section '<b>{off}</b>' found.\n"
                f"Cleaned URL: <a href=\"{cleaned}\">{cleaned}</a>"
            )

        reply_text = (
            "Please edit your comment to remove the tracking parameters:\n\n"
            + "\n\n".join(lines) + "\n\nFailure to do so may result in your message being deleted."
        )

        await message.reply_text(
            reply_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    # CASE 2: Message is clean AND was edited
    elif message.edit_date:
        await message.reply_text(
            f"Thank you {user_name} for removing the trackers."
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_message(update.message, context)


async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_message(update.edited_message, context)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.UpdateType.EDITED_MESSAGE, handle_edited_message))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
