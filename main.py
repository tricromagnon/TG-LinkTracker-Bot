import re
import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
DELETE_MODE = os.getenv("DELETE_MESSAGES", "0").lower() in ["1", "true"]

print("STARTING BOT...")
print("TOKEN:", "SET" if TOKEN else "MISSING")
print("DELETE_MODE:", DELETE_MODE)

# Regex to find URLs
URL_REGEX = re.compile(r"(https?://\S+)")

# Platforms and their tracking query strings
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

# ---------- Helper functions ----------
def clean_url(url: str):
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    query = parse_qs(parsed.query)

    removed_params = []

    for data in PLATFORMS.values():
        if domain in data["domains"]:
            for param in data["tracking_params"]:
                if param in query:
                    removed_params.append(f"{param}={query[param][0]}")
                    query.pop(param)

    clean_query = urlencode(query, doseq=True)
    cleaned_url = urlunparse(parsed._replace(query=clean_query))
    return cleaned_url, removed_params

def clean_message_text(text: str):
    urls = URL_REGEX.findall(text)
    offending_found = []
    new_text = text

    for url in urls:
        cleaned_url, removed = clean_url(url)
        if removed:
            offending_found.extend(removed)
            new_text = new_text.replace(url, cleaned_url)

    return new_text, offending_found

# ---------- Handler ----------
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message or update.edited_message
        if not message or not message.text:
            return

        chat_id = message.chat_id
        msg_id = message.message_id
        user_name = message.from_user.full_name

        print(f"Processing message from {user_name}: {message.text}")

        cleaned_text, offending = clean_message_text(message.text)

        if offending:
            print(f"Found tracking parameters: {offending}")

            if DELETE_MODE:
                # ---------- DELETE & REPOST MODE ----------
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    print("Original message deleted")
                except Exception as e:
                    print("Delete failed:", e)

                repost_text = f"{user_name} wrote '{cleaned_text}'\n\n" \
                              f"<i>(This bot had to repost their comment due to tracking links)</i>"
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=repost_text,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    print("Reposted cleaned message")
                except Exception as e:
                    print("Repost failed:", e)

            else:
                # ---------- EDIT/REPLY MODE ----------
                lines = []
                for off, cleaned_url in zip(offending, [cleaned_text]*len(offending)):
                    lines.append(
                        f"Tracking section '<b>{off}</b>' found.\n"
                        f"Suggested cleaned URL: <a href=\"{cleaned_text}\">{cleaned_text}</a>"
                    )
                reply_text = (
                    "Please edit your comment to remove the tracking parameters:\n\n"
                    + "\n\n".join(lines) + "\n\nFailure to do so may result in your message being deleted."
                )
                try:
                    await message.reply_text(
                        reply_text,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    print("Sent suggestion reply")
                except Exception as e:
                    print("Reply failed:", e)

    except Exception as e:
        print("Handler error:", e)

# ---------- Error handler ----------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("GLOBAL ERROR:", context.error)

# ---------- Main ----------
def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN not set")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, handle_messages))
    app.add_error_handler(error_handler)

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
