import re
import os
import json
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

print("STARTING BOT...")
print("TOKEN:", "SET" if TOKEN else "MISSING")

URL_REGEX = re.compile(r"(https?://\S+)")
STORAGE_FILE = "bot_replies.json"


# ---------- SAFE JSON STORAGE ----------
def load_data():
    try:
        with open(STORAGE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print("LOAD FAILED:", e)
        return {}


def save_data(data):
    try:
        with open(STORAGE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print("SAVE FAILED:", e)


BOT_REPLIES = load_data()


# ---------- PLATFORM CONFIG ----------
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


# ---------- CORE LOGIC ----------
def find_offending_urls(text: str):
    urls = URL_REGEX.findall(text)
    results = []

    for url in urls:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        query = parse_qs(parsed.query)

        for data in PLATFORMS.values():
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


# ---------- HANDLER ----------
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message or update.edited_message

        if message is None:
            return

        if message.text is None:
            return

        is_edit = update.edited_message is not None

        chat_id = str(message.chat_id)
        msg_id = str(message.message_id)
        user_name = message.from_user.full_name

        print("EDIT?", is_edit)
        print("TEXT:", message.text)

        offending = find_offending_urls(message.text)

        print("OFFENDING:", offending)
        print("STORAGE:", BOT_REPLIES)

        # ---------- NEW MESSAGE ----------
        if not is_edit and offending:
            lines = []
            for off, cleaned in offending:
                lines.append(
                    f"Tracking section '<b>{off}</b>' found.\n"
                    f"Cleaned URL: <a href=\"{cleaned}\">{cleaned}</a>"
                )

            reply_text = (
                "Please edit your comment to remove the tracking parameters:\n\n"
                + "\n\n".join(lines) + "\n\n".join(lines) + "\n\nFailure to do so may result in your message being deleted."
            )

            bot_msg = await message.reply_text(
                reply_text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

            BOT_REPLIES.setdefault(chat_id, {})[msg_id] = bot_msg.message_id
            save_data(BOT_REPLIES)

            print("Stored mapping:", chat_id, msg_id)

        # ---------- EDITED MESSAGE ----------
        elif is_edit:
            print("EDIT DETECTED")

            if chat_id in BOT_REPLIES and msg_id in BOT_REPLIES[chat_id]:
                bot_msg_id = BOT_REPLIES[chat_id][msg_id]

                if not offending:
                    try:
                        await context.bot.edit_message_text(
                            chat_id=int(chat_id),
                            message_id=bot_msg_id,
                            text=f"Thank you {user_name} for removing the trackers."
                        )

                        print("EDIT SUCCESS")

                        del BOT_REPLIES[chat_id][msg_id]
                        save_data(BOT_REPLIES)

                    except Exception as e:
                        print("EDIT FAILED:", e)

    except Exception as e:
        print("HANDLER ERROR:", e)


# ---------- ERROR HANDLER ----------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("GLOBAL ERROR:", context.error)


# ---------- MAIN ----------
def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN not set")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.ALL, handle_all_messages))
    app.add_error_handler(error_handler)

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
