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
    "x": {  # Twitter/X
        "domains": {"twitter.com", "www.twitter.com", "x.com", "www.x.com", "t.co"},
        "tracking_params": ["t", "s", "ref_src", "ref_url"]
    },
    "instagram": {
        "domains": {"instagram.com", "www.instagram.com"},
        "tracking_params": ["igshid", "igsh"]
    }
}

# Mapping: {user_message_id: bot_message_id}
BOT_REPLIES = {}

def clean_url(url: str, tracking_params: list[str]) -> list[tuple[str, str]]:
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

def find_offending_urls(text: str) -> list[tuple[str, str]]:
    urls = URL_REGEX.findall(text)
    results = []
    for url in urls:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        for platform, data in PLATFORMS.items():
            if domain in data["domains"]:
                offending_info = clean_url(url, data["tracking_params"])
                results.extend(offending_info)
    return results

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    offending = find_offending_urls(update.message.text)
    if offending:
        reply_lines = [
            f"Tracking section '<b>{off}</b>' found. Cleaned URL: "
            f"<a href=\"{cleaned}\">{cleaned}</a>"
            for cleaned, off in offending
        ]
        reply_text = "Please edit your comment to remove the tracking parameters:\n\n" + "\n".join(reply_lines) + "\n\nFailure to do so may result in your message being deleted."
        bot_msg = await update.message.reply_text(reply_text, parse_mode="HTML", disable_web_page_preview=True)
        
        # store mapping per chat
        chat_id = update.message.chat_id
        BOT_REPLIES.setdefault(chat_id, {})[update.message.message_id] = bot_msg.message_id

async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.edited_message or not update.edited_message.text:
        return

    chat_id = update.edited_message.chat_id
    user_msg_id = update.edited_message.message_id

    # Re-scan edited message for any offending parameters
    offending = find_offending_urls(update.edited_message.text)

    # If no offending parameters remain, delete bot message
    if chat_id in BOT_REPLIES and user_msg_id in BOT_REPLIES[chat_id]:
        bot_msg_id = BOT_REPLIES[chat_id][user_msg_id]
        if not offending:
            try:
                # Delete the bot reply
                await context.bot.delete_message(chat_id=chat_id, message_id=bot_msg_id)
                # Remove from mapping
                del BOT_REPLIES[chat_id][user_msg_id]
            except Exception as e:
                # Could log the exception for debugging
                print(f"Failed to delete bot message: {e}")
                
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # New messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # Edited messages
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & filters.TEXT, handle_edited_message))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
