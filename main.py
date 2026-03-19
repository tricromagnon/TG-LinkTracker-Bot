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
            data = json.load(f)
            print("Loaded storage:", data)
            return data
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


# ---------- NEW MESSAGE ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    print("NEW MESSAGE:", update.message.text)

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

        # store mapping
        chat_id = str(update.message.chat_id)
        msg_id = str(update.message.message_id)

        BOT_REPLIES.setdefault(chat_id, {})[msg_id] = bot_msg.message_id
        save_data(BOT_REPLIES)

        print("Stored mapping:", chat_id, msg_id, "->", bot_msg.message_id)


# ---------- EDITED MESSAGE ----------
async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("EDIT HANDLER TRIGGERED")

    if not update.edited_message or not update.edited_message.text:
        print("No edited message text")
        return

    chat_id = str(update.edited_message.chat_id)
    msg_id = str(update.edited_message.message_id)
    user_name = update.edited_message.from_user.full_name

    print("EDIT TEXT:", update.edited_message.text)

    offending = find_offending_urls(update.edited_message.text)

    print("OFFENDING AFTER EDIT:", offending)
    print("CURRENT STORAGE:", BOT_REPLIES)

    if chat_id in BOT_REPLIES and msg_id in BOT_REPLIES[chat_id]:
        bot_msg_id = BOT_REPLIES[chat_id][msg_id]

        if not offending:
            try:
                await context.bot.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=bot_msg_id,
                    text=f"Thank you {user_name} for removing the trackers."
                )

                print("Edited bot message successfully")

                del BOT_REPLIES[chat_id][msg_id]
                save_data(BOT_REPLIES)

            except Exception as e:
                print("EDIT FAILED:", e)


# ---------- MAIN ----------
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
