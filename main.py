import re
import os
import json
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

URL_REGEX = re.compile(r"(https?://\S+)")

STORAGE_FILE = "bot_replies.json"

# Load / save persistent storage
def load_data():
    try:
        with open(STORAGE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f)

BOT_REPLIES = load_data()

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


def find_offending_urls(text: str):
    urls = URL_REGEX.findall(text)
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
                        query_copy = query.copy()
                        query_copy.pop(param)

                        clean_query = urlencode(query_copy, doseq=True)
                        cleaned_url = urlunparse(parsed._replace(query=clean_query))

                        results.append((offending, cleaned_url))
                        break

    return results


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    offending = find_offending_urls(update.message.text)

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

        bot_msg = await update.message.reply_text(
            reply_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        # Store mapping
        chat_id = str(update.message.chat_id)
        msg_id = str(update.message.message_id)

        BOT_REPLIES.setdefault(chat_id, {})[msg_id] = bot_msg.message_id
        save_data(BOT_REPLIES)


async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.edited_message or not update.edited_message.text:
        return

    chat_id = str(update.edited_message.chat_id)
    msg_id = str(update.edited_message.message_id)
    user_name = update.edited_message.from_user.full_name

    offending = find_offending_urls(update.edited_message.text)

    print("EDIT DETECTED", chat_id, msg_id, "OFFENDING:", offending)

    if chat_id in BOT_REPLIES and msg_id in BOT_REPLIES[chat_id]:
        bot_msg_id = BOT_REPLIES[chat_id][msg_id]

        # If NO offending params remain → edit bot message
        if not offending:
            try:
                await context.bot.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=bot_msg_id,
                    text=f"Thank you {user_name} for removing the trackers."
                )

                # remove mapping
                del BOT_REPLIES[chat_id][msg_id]
                save_data(BOT_REPLIES)

            except Exception as e:
                print("EDIT FAILED:", e)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # NEW messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # EDITED messages (IMPORTANT)
    app.add_handler(MessageHandler(filters.TEXT & filters.UpdateType.EDITED_MESSAGE, handle_edited_message))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
