# bot.py
# Elevate Promotion - multi-level SMM bot with payment screenshot approval
# Requires: python-telegram-bot (v22+)
# Replace BOT_TOKEN and ADMIN_ID before running.

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== CONFIG =====
BOT_TOKEN = "8476063027:AAEWh4T6D1wq85-I1_XjoJ4Yedk6wVQSndc"
ADMIN_ID = 5872954068            # <-- replace with your numeric Telegram ID
BOT_NAME = "Elevate Promotion"

# Conversation states
(
    STATE_CATEGORY,
    STATE_SERVICE,
    STATE_PACKAGE,
    STATE_ASK_LINK,
    STATE_PAYMENT_METHOD,
    STATE_AWAIT_SCREENSHOT,
) = range(6)

# Example service structure and packages (you can expand)
SERVICES = {
    "tiktok": {
        "label_en": "TikTok",
        "label_am": "TikTok",
        "sub": {
            "likes": {"label_en": "Likes", "label_am": "Likes", "packages": [
                ("300 Likes", 72.0),
                ("500 Likes", 110.0),
                ("1000 Likes", 224.0),
                ("5000 Likes", 566.25),
            ]},
            "views": {"label_en": "Views", "label_am": "Views", "packages": [
                ("1000 Views", 131.0),
                ("5000 Views", 420.0),
                ("10000 Views", 810.0),
            ]},
            "followers": {"label_en": "Followers", "label_am": "Followers", "packages": [
                ("1000 Followers", 180.0),
                ("5000 Followers", 820.0),
            ]},
        }
    },
    "youtube": {
        "label_en": "YouTube",
        "label_am": "YouTube",
        "sub": {
            "views": {"label_en": "Views", "label_am": "Views", "packages": [
                ("1000 Views", 350.0),
                ("5000 Views", 1486.25),
                ("10000 Views", 2515.0),
            ]},
            "likes": {"label_en": "Likes", "label_am": "Likes", "packages": [
                ("500 Likes", 211.25),
                ("1000 Likes", 389.0),
                ("5000 Likes", 1623.75),
            ]},
            "subscribers": {"label_en": "Subscribers", "label_am": "Subscribers", "packages": [
                ("100 Subs", 100.0),
                ("1000 Subs", 370.0),
            ]},
        }
    },
    "instagram": {
        "label_en": "Instagram",
        "label_am": "Instagram",
        "sub": {
            "likes": {"label_en": "Likes", "label_am": "Likes", "packages": [
                ("500 Likes", 155.12),
                ("1000 Likes", 289.0),
                ("5000 Likes", 1260.0),
            ]},
            "views": {"label_en": "Views", "label_am": "Views", "packages": [
                ("1000 Views", 87.88),
                ("5000 Views", 342.5),
            ]},
        }
    },
    "facebook": {
        "label_en": "Facebook",
        "label_am": "Facebook",
        "sub": {
            "page_likes": {"label_en": "Page Likes", "label_am": "Page Likes", "packages": [
                ("1000 Page Likes", 338.0),
                ("5000 Page Likes", 1625.0),
            ]},
            "post_likes": {"label_en": "Post Likes", "label_am": "Post Likes", "packages": [
                ("500 Post Likes", 175.0),
                ("1000 Post Likes", 338.0),
            ]},
        }
    },
    "telegram": {
        "label_en": "Telegram",
        "label_am": "Telegram",
        "sub": {
            "members": {"label_en": "Members", "label_am": "Members", "packages": [
                ("100 Members", 100.0),
                ("500 Members", 470.0),
                ("1000 Members", 890.0),
            ]},
            "reactions": {"label_en": "Reactions", "label_am": "Reactions", "packages": [
                ("500 Reactions", 110.0),
                ("1000 Reactions", 224.0),
            ]},
        }
    }
}

PAYMENT_METHODS = [
    ("telebirr", "Telebirr"),
    ("cbe", "CBE"),
    ("awash", "Awash"),
    ("abyssinia", "Abyssinia Bank"),
]

# ===== Utility: language-aware texts =====
def t(user_lang, en_text, am_text):
    return am_text if user_lang == "am" else en_text

# ===== Start & language selection =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # default language is English
    context.user_data.setdefault("lang", "en")
    lang = context.user_data["lang"]

    welcome = t(lang,
                f"👋 Welcome to {BOT_NAME}!\nChoose /service to see services or use the menu commands.",
                f"👋 እንኳን ደህና መጡ ወደ {BOT_NAME}!\n/service ኣገልግሎት ለምድመ ስራ ይጠቀሙ።")
    await update.message.reply_text(welcome)

# /language command
async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["English", "አማርኛ"]]
    reply = t(context.user_data.get("lang","en"),
              "Choose language:",
              "ቋንቋ ይምረጡ:")
    await update.message.reply_text(reply, reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))

async def language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text in ["english", "en"]:
        context.user_data["lang"] = "en"
        await update.message.reply_text("Language set to English.", reply_markup=ReplyKeyboardRemove())
    else:
        context.user_data["lang"] = "am"
        await update.message.reply_text("ቋንቋ እዚህ ተቀይሯል — አማርኛ", reply_markup=ReplyKeyboardRemove())

# ===== /service flow: categories =====
async def service_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    # present categories as buttons
    keyboard = []
    row = []
    for key, data in SERVICES.items():
        label = data["label_am"] if lang == "am" else data["label_en"]
        row.append(label)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append(["/start"])
    await update.message.reply_text(t(lang, "Choose a category:", "እባክዎ ምድር ይምረጡ:"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return STATE_CATEGORY

# Helper to find service key from label
def find_service_key_by_label(label, lang):
    for key, data in SERVICES.items():
        lbl = data["label_am"] if lang == "am" else data["label_en"]
        if label == lbl:
            return key
    return None

# ===== Category selected: show sub-services =====
async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    text = update.message.text
    service_key = find_service_key_by_label(text, lang)
    if not service_key:
        await update.message.reply_text(t(lang, "Invalid category. Use /service.", "እባክዎ ልክ ምድር ይምረጡ። /service ይጠቀሙ።"))
        return ConversationHandler.END

    context.user_data["current_service"] = service_key
    sub = SERVICES[service_key]["sub"]
    keyboard = []
    row = []
    for subkey, subdata in sub.items():
        lbl = subdata["label_am"] if lang == "am" else subdata["label_en"]
        row.append(lbl)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append(["/service", "/start"])
    await update.message.reply_text(t(lang, "Choose a service:", "እባክዎ አገልግሎት ይምረጡ።"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return STATE_SERVICE

# helper find subkey
def find_subkey_by_label(service_key, label, lang):
    sub = SERVICES[service_key]["sub"]
    for subkey, subdata in sub.items():
        lbl = subdata["label_am"] if lang == "am" else subdata["label_en"]
        if label == lbl:
            return subkey
    return None

# ===== Sub-service selected: show packages =====
async def service_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    text = update.message.text
    service_key = context.user_data.get("current_service")
    if not service_key:
        await update.message.reply_text(t(lang, "Please choose a category first: /service", "እባክዎ ከሚገኙ ምድራት ይጀምሩ። /service"))
        return ConversationHandler.END

    subkey = find_subkey_by_label(service_key, text, lang)
    if not subkey:
        await update.message.reply_text(t(lang, "Invalid option.", "እባክዎ ልክ የለም።"))
        return ConversationHandler.END

    context.user_data["current_sub"] = subkey
    packages = SERVICES[service_key]["sub"][subkey]["packages"]
    # build package message
    lines = []
    for idx, (title, price) in enumerate(packages, start=1):
        lines.append(f"{idx}. {title} — {price:.2f} ETB")
    lines.append("")
    lines.append(t(lang, "Send the number of the package you want.", "ቁጥሩን የሚፈልጉትን እባክዎ ይላኩ።"))
    await update.message.reply_text("\n".join(lines), reply_markup=ReplyKeyboardMarkup([["/service","/start"]], resize_keyboard=True))
    return STATE_PACKAGE

# ===== Package chosen: ask for link/username =====
async def package_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    text = update.message.text.strip()
    service_key = context.user_data.get("current_service")
    subkey = context.user_data.get("current_sub")
    if not (service_key and subkey):
        await update.message.reply_text(t(lang, "Start with /service", "እባክዎ /service ይጠቀሙ።"))
        return ConversationHandler.END

    packages = SERVICES[service_key]["sub"][subkey]["packages"]
    # expect a number
    try:
        sel = int(text)
        if not (1 <= sel <= len(packages)):
            raise ValueError
    except ValueError:
        await update.message.reply_text(t(lang, "Please send a valid package number.", "እባክዎ ትክክለኛ የጥራት ቁጥር ይላኩ።"))
        return STATE_PACKAGE

    chosen = packages[sel-1]  # (title, price)
    context.user_data["order"] = {
        "service_key": service_key,
        "subkey": subkey,
        "package": chosen[0],
        "price": chosen[1],
    }

    # Ask for link or username depending on platform
    ask_text = ""
    if service_key in ["youtube", "tiktok", "instagram", "facebook"]:
        ask_text = t(lang, "Send the link (URL) of your post/video:", "እባክዎ የሚፈልጉትን ሊንክ ይላኩ።")
    elif service_key == "telegram":
        ask_text = t(lang, "Send your channel/group username (without @):", "እባክዎ የቻናል/ጉሩፕ ዩዘርኔም ይላኩ (without @).")
    else:
        ask_text = t(lang, "Send the link or username for this order:", "እባክዎ ሊንክ ወይም ዩዘርኔም ይላኩ።")

    price = chosen[1]
    summary = t(lang,
                f"Selected: {chosen[0]} — {price:.2f} ETB\n{ask_text}",
                f"የተመረጠ: {chosen[0]} — {price:.2f} ብር\n{ask_text}")
    await update.message.reply_text(summary, reply_markup=ReplyKeyboardMarkup([["/service","/start"]], resize_keyboard=True))
    return STATE_ASK_LINK

# ===== After link provided: present payment methods =====
async def ask_link_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    text = update.message.text.strip()
    # Save link/username
    context.user_data["order"]["target"] = text

    # show payment methods
    kb = [[m[1] for m in PAYMENT_METHODS]]  # single row
    kb.append(["/service", "/start"])
    prompt = t(lang, "Choose a payment method:", "እባክዎ የክፍያ ዘዴ ይምረጡ:")
    # show order summary with price
    order = context.user_data["order"]
    order_summary = t(lang,
                      f"Order: {order['package']} — {order['price']:.2f} ETB\nTarget: {order['target']}",
                      f"ትዕዛዝ: {order['package']} — {order['price']:.2f} ብር\nትኬት: {order['target']}")
    await update.message.reply_text(order_summary)
    await update.message.reply_text(prompt, reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))
    return STATE_PAYMENT_METHOD

# ===== Payment method chosen: ask to send screenshot =====
def find_payment_key_by_label(label):
    for key, name in PAYMENT_METHODS:
        if name.lower() == label.lower():
            return key
    return None

async def payment_method_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    text = update.message.text.strip()
    pm_key = find_payment_key_by_label(text)
    if not pm_key:
        await update.message.reply_text(t(lang, "Invalid payment option. Choose again.", "እባክዎ ትክክለኛ የክፍያ ዘዴ ይምረጡ።"))
        return STATE_PAYMENT_METHOD

    context.user_data["order"]["payment_method"] = pm_key
    # show payment info (you can replace with your real account details)
    payment_info = {
        "telebirr": "+251912345678",
        "cbe": "CBE 1000123456789",
        "awash": "Awash 500012345678",
        "abyssinia": "Abyssinia 200012345678"
    }
    acc = payment_info.get(pm_key, "")
    ask = t(lang,
            f"Please send payment to: {acc}\nAfter payment, send your payment screenshot here (photo).",
            f"እባክዎ ክፍያዎን ወደ: {acc} አድርጉ። ከዚያም የክፍያ ስክሪንሾት እባክዎ ይላኩ።")
    await update.message.reply_text(ask, reply_markup=ReplyKeyboardMarkup([["/service","/start"]], resize_keyboard=True))
    # now wait for screenshot
    return STATE_AWAIT_SCREENSHOT

# ===== Screenshot handler (user sends photo) =====
# This forwards to admin with Approve/Reject buttons and notifies user (Amharic message)
async def screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # only accept when in state expecting screenshot
    state = context.user_data.get("_conversation_state", None)
    # Save state attempt — in this flow we simply require order exists
    order = context.user_data.get("order")
    if not order:
        # no order context — ask user to start
        lang = context.user_data.get("lang", "en")
        await update.message.reply_text(t(lang, "No order found. Start with /service.", "ትዕዛዝ አልተገኘም። /service ይጠቀሙ።"))
        return ConversationHandler.END

    # Confirm reviewing message to user (in Amharic as requested)
    lang = context.user_data.get("lang", "en")
    # immediate message: "we are reviewing your payment" in Amharic
    reviewing_msg = "ክፍያዎን እየገመገምን ነው። እባክዎ ይጠብቁ።" if lang == "am" else "We are reviewing your payment. Please wait."
    await update.message.reply_text(reviewing_msg)

    user = update.effective_user
    username = user.username or user.first_name
    user_id = user.id

    # get largest photo file_id
    if not update.message.photo:
        await update.message.reply_text(t(lang, "Please send a photo (screenshot).", "እባክዎ እትክ ስክሪንሾት ይላኩ።"))
        return STATE_AWAIT_SCREENSHOT

    photo_file_id = update.message.photo[-1].file_id

    # Build caption for admin including order summary
    caption_lines = [
        f"📩 Payment screenshot from @{username} (ID: {user_id})",
        f"Service: {SERVICES[order['service_key']]['label_en']} - {order['package']}",
        f"Target: {order.get('target','N/A')}",
        f"Price: {order['price']:.2f} ETB",
        f"Payment method: {order.get('payment_method','N/A')}",
        "",
        "Press Approve or Reject below."
    ]
    caption = "\n".join(caption_lines)

    # Inline buttons for admin
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{user_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject:{user_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send photo to admin
    try:
        sent = await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo_file_id, caption=caption, reply_markup=reply_markup)
    except Exception as e:
        logger.error("Error sending photo to admin: %s", e)
        await update.message.reply_text(t(lang, "Could not forward screenshot to admin. Try again later.", "ስክሪንሾትን ወደ አስተዳደር ማስመላለሻ አልተቻለም። ከዚያ በኋላ ይሞክሩ።"))
        return ConversationHandler.END

    # Optionally store mapping from admin message id to user (not strictly necessary here)
    # context.bot_data[sent.message_id] = {"user_id": user_id, "order": order}

    # keep user in conversation ended state or you may return ConversationHandler.END
    return ConversationHandler.END

# ===== Admin approve/reject callback handler =====
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # e.g., "approve:123456"
    if ":" not in data:
        return
    action, uid = data.split(":", 1)
    try:
        target_user_id = int(uid)
    except ValueError:
        await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n⚠️ Invalid user id.")
        return

    admin_user = query.from_user
    # allow only admin to press
    if admin_user.id != ADMIN_ID:
        await query.edit_message_caption(caption=(query.message.caption or "") + f"\n\n⚠️ Unauthorized action by @{admin_user.username}")
        return

    # find user preferred language? We don't have their language here; we'll assume English fallback
    # If you want, you can map stored orders to get user's language; for now send both lang messages
    try:
        if action == "approve":
            # notify user
            try:
                await context.bot.send_message(chat_id=target_user_id, text="✅ ክፍያዎት ተፈቅዷል። ትእዛዝዎ እየሠራ ነው።\n(Your payment has been approved.)")
            except Exception:
                # user may have privacy settings
                pass
            new_caption = (query.message.caption or "") + "\n\n✅ Approved by admin."
            await query.edit_message_caption(caption=new_caption, reply_markup=None)
        elif action == "reject":
            try:
                await context.bot.send_message(chat_id=target_user_id, text="❌ ክፍያዎት አልተፈቀደም። እባክዎ ደገም ይክፈሉ ወይም ይሞክሩ።\n(Your payment was rejected.)")
            except Exception:
                pass
            new_caption = (query.message.caption or "") + "\n\n❌ Rejected by admin."
            await query.edit_message_caption(caption=new_caption, reply_markup=None)
    except Exception as e:
        logger.error("Error in admin callback: %s", e)

# ===== Simple commands placeholders =====
async def recharge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    # show payment accounts
    await update.message.reply_text(t(lang,
                                     "💳 Payment Accounts:\nTelebirr: +251912345678\nCBE: 1000123456789\nAwash: 500012345678\nAbyssinia: 200012345678\n\nAfter payment, send screenshot here.",
                                     "💳 የክፍያ መለያዎች:\nTelebirr: +251912345678\nCBE: 1000123456789\nAwash: 500012345678\nAbyssinia: 200012345678\n\nከክፍያ በኋላ ስክሪንሾት ይላኩ።"))

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    await update.message.reply_text(t(lang, "💳 Balance: 0 ETB (manual system)", "💳 ቀሪ ሂሳብ: 0 ብር (እጅግ ዳሽ)"))

async def my_orders_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    await update.message.reply_text(t(lang, "No orders yet. Your orders will appear here.", "هنوز هیچ سفارشی وجود ندارد"))

async def more_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    await update.message.reply_text(t(lang, "More services are available. Contact admin.", "ተጨማሪ አገልግሎቶች አሉ። እባክዎ ከአስተዳደር ጋር ይገናኙ።"))

# ===== Fallbacks & unknown =====
async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    await update.message.reply_text(t(lang, "Use /service to start an order or /language to change language.", "እባክዎ /service ይጠቀሙ ወይም /language ይምረጡ።"))

# ===== Main setup =====
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("service", service_cmd)],
        states={
            STATE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_selected)],
            STATE_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, service_selected)],
            STATE_PACKAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, package_selected)],
            STATE_ASK_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_link_received)],
            STATE_PAYMENT_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_method_selected)],
            STATE_AWAIT_SCREENSHOT: [MessageHandler(filters.PHOTO, screenshot_handler)],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("language", language_cmd)],
        allow_reentry=True,
    )

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language_cmd))
    # language choice (simple text)
    app.add_handler(MessageHandler(filters.Regex("^(English|አማርኛ)$"), language_choice))
    app.add_handler(conv_handler)

    # Payment screenshot handler for when user sends screenshot outside conversation
    app.add_handler(MessageHandler(filters.PHOTO, screenshot_handler))

    # Admin callback button handler
    app.add_handler(CallbackQueryHandler(admin_callback_handler))

    # Simple other commands
    app.add_handler(CommandHandler("recharge", recharge_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("my_orders", my_orders_cmd))
    app.add_handler(CommandHandler("more", more_cmd))

    # Unknown text fallback
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message))

    print(f"{BOT_NAME} is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
