# bot.py
# Elevate Promotion - full bot with video welcome, clickable packages, balance (SQLite),
# recharge via screenshot + admin approve/reject, and order flow.
# Requires: python-telegram-bot v22.x (tested with 22.3)
# Place welcome.mp4 in same folder or set WELCOME_VIDEO to a file_id or URL

import os
import logging
import sqlite3
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8476063027:AAEWh4T6D1wq85-I1_XjoJ4Yedk6wVQSndc"
ADMIN_ID = int(os.getenv("ADMIN_ID") or "5872954068")  # your numeric Telegram ID
WELCOME_VIDEO = os.getenv("WELCOME_VIDEO") or "welcome.mp4"  # local file, file_id, or URL

# Payment accounts shown to users when they pick external payment
PAYMENT_INFO = {
    "telebirr": "+251912345678",
    "cbe": "CBE 1000123456789",
    "awash": "Awash 500012345678",
    "abyssinia": "Abyssinia 200012345678",
}

# Services and packages (modify to your real packages/prices)
SERVICES = {
    "tiktok": {
        "label_am": "TikTok 🎶",
        "label_en": "TikTok 🎶",
        "sub": {
            "likes": {
                "label_am": "Likes",
                "label_en": "Likes",
                "packages": [
                    ("300 Likes", 72.00),
                    ("500 Likes", 110.00),
                    ("1000 Likes", 224.00),
                    ("5000 Likes", 566.25),
                ],
            },
            "followers": {
                "label_am": "Followers",
                "label_en": "Followers",
                "packages": [
                    ("1000 Followers", 180.00),
                    ("5000 Followers", 820.00),
                ],
            },
        },
    },
    "youtube": {
        "label_am": "YouTube 🎥",
        "label_en": "YouTube 🎥",
        "sub": {
            "views": {
                "label_am": "Views",
                "label_en": "Views",
                "packages": [
                    ("1000 Views", 350.00),
                    ("5000 Views", 1486.25),
                    ("10000 Views", 2515.00),
                ],
            },
            "subs": {
                "label_am": "Subscribers",
                "label_en": "Subscribers",
                "packages": [
                    ("100 Subs", 100.00),
                    ("1000 Subs", 370.00),
                ],
            },
        },
    },
    "instagram": {
        "label_am": "Instagram 📸",
        "label_en": "Instagram 📸",
        "sub": {
            "likes": {
                "label_am": "Likes",
                "label_en": "Likes",
                "packages": [
                    ("500 Likes", 155.12),
                    ("1000 Likes", 289.00),
                ],
            }
        },
    },
    "facebook": {
        "label_am": "Facebook 🌍",
        "label_en": "Facebook 🌍",
        "sub": {
            "page_likes": {
                "label_am": "Page Likes",
                "label_en": "Page Likes",
                "packages": [
                    ("1000 Page Likes", 338.00),
                ],
            }
        },
    },
    "telegram": {
        "label_am": "Telegram ✈️",
        "label_en": "Telegram ✈️",
        "sub": {
            "members": {
                "label_am": "Members",
                "label_en": "Members",
                "packages": [
                    ("100 Members", 100.00),
                    ("500 Members", 470.00),
                ],
            }
        },
    },
}

# ---------------- logging ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- Database setup ----------------
DB_FILE = "bot.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()
# users: stores balance
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0
)
""")
# orders: stores orders (when user orders a package)
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    service_key TEXT,
    subkey TEXT,
    package_title TEXT,
    price REAL,
    target TEXT,
    payment_method TEXT,
    status TEXT,
    created_at TEXT
)
""")
# recharges: stores recharge attempts
cursor.execute("""
CREATE TABLE IF NOT EXISTS recharges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    payment_method TEXT,
    status TEXT,
    admin_message_id INTEGER,
    created_at TEXT
)
""")
conn.commit()

# ---------------- DB helper functions ----------------
def get_balance(user_id: int) -> float:
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    r = cursor.fetchone()
    if r:
        return r[0]
    cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
    conn.commit()
    return 0.0

def set_balance(user_id: int, new_balance: float):
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
    conn.commit()

def add_balance(user_id: int, amount: float) -> float:
    bal = get_balance(user_id)
    new_bal = bal + amount
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_bal, user_id))
    conn.commit()
    return new_bal

def deduct_balance(user_id: int, amount: float) -> (bool, float):
    bal = get_balance(user_id)
    if bal >= amount:
        new_bal = bal - amount
        cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_bal, user_id))
        conn.commit()
        return True, new_bal
    else:
        return False, bal

def create_order(user_id:int, service_key:str, subkey:str, package_title:str, price:float, target:str, payment_method:str, status:str="pending"):
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO orders (user_id, service_key, subkey, package_title, price, target, payment_method, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, service_key, subkey, package_title, price, target, payment_method, status, now))
    conn.commit()
    return cursor.lastrowid

def update_order_status(order_id:int, status:str):
    cursor.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()

def create_recharge(user_id:int, amount:float, payment_method:str, status:str="pending", admin_message_id: int=None):
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO recharges (user_id, amount, payment_method, status, admin_message_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, amount, payment_method, status, admin_message_id, now))
    conn.commit()
    return cursor.lastrowid

def update_recharge_status(recharge_id:int, status:str, admin_message_id:int=None):
    if admin_message_id is None:
        cursor.execute("UPDATE recharges SET status=? WHERE id=?", (status, recharge_id))
    else:
        cursor.execute("UPDATE recharges SET status=?, admin_message_id=? WHERE id=?", (status, admin_message_id, recharge_id))
    conn.commit()

# ---------------- small helper ----------------
def t(lang, en_text, am_text):
    return am_text if lang == "am" else en_text

# ---------------- START handler ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    # default language = Amharic
    if "lang" not in context.user_data:
        context.user_data["lang"] = "am"
    lang = context.user_data["lang"]
    balance = get_balance(uid)

    caption = t(lang,
                f"👋 Welcome to Elevate Promotion!\nYour balance: {balance:.2f} ETB\nChoose a service below.",
                f"👋 እንኳን ደህና መጡ ወደ Elevate Promotion!\nቀሪ ብር: {balance:.2f}\nእባክዎን ከዚህ አገልግሎት ይምረጡ።")

    # build category inline buttons
    buttons = []
    row = []
    for key, data in SERVICES.items():
        label = data["label_am"] if lang == "am" else data["label_en"]
        row.append(InlineKeyboardButton(label, callback_data=f"svc|{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    # add short quick buttons (balance, recharge, language)
    buttons.append([
        InlineKeyboardButton(t(lang, "Balance", "ቀሪ ሂሳብ"), callback_data="cmd|balance"),
        InlineKeyboardButton(t(lang, "Recharge", "ገንዘብ ማስገቢያ"), callback_data="cmd|recharge"),
    ])
    buttons.append([InlineKeyboardButton(t(lang, "Language", "ቋንቋ"), callback_data="cmd|language")])

    # send video if available; else send caption text
    try:
        if WELCOME_VIDEO and os.path.isfile(WELCOME_VIDEO):
            with open(WELCOME_VIDEO, "rb") as f:
                await update.message.reply_video(video=f, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            # file_id or URL
            await update.message.reply_video(video=WELCOME_VIDEO, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        # fallback to text
        await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(buttons))

# ---------------- Callback handler for inline buttons ----------------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # e.g., "svc|tiktok" or "sub|tiktok|likes" or "pkg|tiktok|likes|0" or "pay|telebirr" or "admin|approve_recharge|<rid>|<uid>"
    user = query.from_user
    lang = context.user_data.get("lang", "am")

    parts = data.split("|")
    prefix = parts[0]

    # ----- category chosen -----
    if prefix == "svc":
        if len(parts) < 2:
            await query.edit_message_text(t(lang, "Invalid category.", "ምድር የለም።"))
            return
        service_key = parts[1]
        context.user_data["current_service"] = service_key
        sub = SERVICES[service_key]["sub"]
        buttons = []
        row = []
        for subkey, subdata in sub.items():
            lbl = subdata["label_am"] if lang == "am" else subdata["label_en"]
            row.append(InlineKeyboardButton(lbl, callback_data=f"sub|{service_key}|{subkey}"))
            if len(row) == 2:
                buttons.append(row); row = []
        if row: buttons.append(row)
        buttons.append([InlineKeyboardButton(t(lang, "Back", "ተመለስ"), callback_data="back|")])
        await query.edit_message_text(t(lang, "Choose a service:", "እባክዎ አገልግሎት ይምረጡ።"), reply_markup=InlineKeyboardMarkup(buttons))
        return

    # ----- subservice chosen -> show packages as buttons -----
    if prefix == "sub":
        _, service_key, subkey = parts
        context.user_data["current_sub"] = subkey
        packages = SERVICES[service_key]["sub"][subkey]["packages"]
        buttons = []
        for idx, (title, price) in enumerate(packages):
            btn_text = f"{title} — {price:.2f} ETB"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"pkg|{service_key}|{subkey}|{idx}")])
        buttons.append([InlineKeyboardButton(t(lang, "Back", "ተመለስ"), callback_data=f"svc|{service_key}")])
        await query.edit_message_text(t(lang, "Choose a package:", "እባክዎ ጥንካሬ ይምረጡ።"), reply_markup=InlineKeyboardMarkup(buttons))
        return

    # ----- package chosen: save order and ask for link/username -----
    if prefix == "pkg":
        _, service_key, subkey, idx_str = parts
        idx = int(idx_str)
        packages = SERVICES[service_key]["sub"][subkey]["packages"]
        if idx < 0 or idx >= len(packages):
            await query.edit_message_text(t(lang, "Invalid package.", "ስህተት በፓኬጅ።"))
            return
        title, price = packages[idx]
        user_id = user.id
        order = {
            "user_id": user_id,
            "service_key": service_key,
            "subkey": subkey,
            "package_title": title,
            "price": price,
            "lang": context.user_data.get("lang", "am"),
        }
        # store current order in bot_data keyed by user id until link & payment chosen
        context.application.bot_data[f"order:{user_id}"] = order
        # ask for link/username
        if service_key in ("youtube", "tiktok", "instagram", "facebook"):
            prompt = t(order["lang"], "Send the link (URL) of your post/video:", "እባክዎ ሊንኩን ይላኩ።")
        else:
            prompt = t(order["lang"], "Send your channel/group username (without @):", "እባክዎ ዩዘርኔም ይላኩ (without @).")
        await query.edit_message_text(t(order["lang"],
                                       f"You selected: {title} — {price:.2f} ETB\n\n{prompt}",
                                       f"የተመረጠ፦ {title} — {price:.2f} ብር\n\n{prompt}"))
        # set flag: waiting for link
        context.user_data["awaiting_link_for_order"] = True
        return

    # ----- after user chooses payment method for an order (external) -----
    if prefix == "pay":
        # data: pay|telebirr  OR pay|balance (for pay with balance)
        if len(parts) < 2:
            await query.answer()
            return
        method = parts[1]
        user_id = user.id
        order = context.application.bot_data.get(f"order:{user_id}")
        if not order:
            await query.edit_message_text(t(lang, "No order found. Use /service to start.", "ትዕዛዝ አልተገኘም። /service ይግቡ።"))
            return
        if method == "balance":
            # pay with balance now
            price = order["price"]
            ok, new_bal = deduct_balance(user_id, price)
            if ok:
                # record order as paid
                order_id = create_order(user_id, order["service_key"], order["subkey"],
                                        order["package_title"], price, order.get("target", ""), "balance", status="paid")
                # remove temporary order
                context.application.bot_data.pop(f"order:{user_id}", None)
                await query.edit_message_text(t(lang,
                                               f"✅ Payment successful. {price:.2f} ETB deducted from your balance.\nRemaining: {new_bal:.2f} ETB\nYour order id: {order_id}",
                                               f"✅ ክፍያ ተከፍሏል። {price:.2f} ብር ከቀሪ ሂሳብዎ ተቀናል።\nቀሪ: {new_bal:.2f} ብር\nትዕዛዝ መለያ: {order_id}"))
            else:
                await query.edit_message_text(t(lang,
                                               f"❌ Insufficient balance ({new_bal:.2f} ETB). Please recharge or choose another payment method.",
                                               f"❌ በቂ ቀሪ ሂሳብ የለም ({new_bal:.2f} ብር). እባክዎ ይክፈሉ ወይም ሌላ ዘዴ ይምረጡ።"))
            return
        else:
            # external payment selected: send account info and ask for screenshot
            acc = PAYMENT_INFO.get(method, "Not available")
            context.application.bot_data[f"order:{user_id}"]["payment_method"] = method
            # create order with status pending_payment (so we have an order id)
            ord = context.application.bot_data.get(f"order:{user_id}")
            order_id = create_order(user_id, ord["service_key"], ord["subkey"], ord["package_title"], ord["price"], ord.get("target",""), method, status="pending_payment")
            # store order_id in bot_data for later reference
            context.application.bot_data[f"order:{user_id}"]["order_id"] = order_id
            await query.edit_message_text(t(lang,
                                           f"Please send payment to: {acc}\nAfter payment, upload your screenshot (photo) here.\nOrder ID: {order_id}",
                                           f"እባክዎ ክፍያዎን ወደ፦ {acc} ይከፍሉ።\nከዚያ በኋላ የክፍያ ስክሪንሾት ይላኩ።\nየትዕዛዝ መለያ: {order_id}"))
            return

    # ----- admin approve/reject for orders or recharges -----
    # callbacks:
    #   admin|approve_order|<order_id>|<user_id>
    #   admin|reject_order|<order_id>|<user_id>
    #   admin|approve_recharge|<recharge_id>|<user_id>
    #   admin|reject_recharge|<recharge_id>|<user_id>
    if prefix == "admin":
        if len(parts) < 4:
            await query.answer("Bad admin action", show_alert=True)
            return
        action = parts[1]  # approve_order, reject_recharge, etc.
        obj_id = int(parts[2])
        target_user_id = int(parts[3])
        if query.from_user.id != ADMIN_ID:
            await query.answer("Unauthorized", show_alert=True)
            return

        # approve order
        if action == "approve_order":
            # mark order paid/processing
            update_order_status(obj_id, "approved")
            # notify user
            try:
                await context.bot.send_message(chat_id=target_user_id, text=t(context.application.bot_data.get(f"order_lang:{target_user_id}", "am"),
                    "✅ Your payment has been approved. Your order is processing.",
                    "✅ ክፍያዎት ተፈቅዷል። ትዕዛዝዎ እየተሰራ ነው።"))
            except Exception:
                logger.warning("Could not notify user about approved order.")
            # edit admin message caption to show approved
            await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n✅ Approved by admin.", reply_markup=None)
            return

        # reject order
        if action == "reject_order":
            update_order_status(obj_id, "rejected")
            try:
                await context.bot.send_message(chat_id=target_user_id, text=t(context.application.bot_data.get(f"order_lang:{target_user_id}", "am"),
                    "❌ Your payment was rejected. Please try again or contact admin.",
                    "❌ ክፍያዎት አልተፈቀደም። እባክዎ ደግመው ይሞክሩ።"))
            except Exception:
                logger.warning("Could not notify user about rejected order.")
            await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n❌ Rejected by admin.", reply_markup=None)
            return

        # approve recharge
        if action == "approve_recharge":
            # add to user's balance and mark recharge approved
            recharge_id = obj_id
            cursor.execute("SELECT user_id, amount FROM recharges WHERE id=?", (recharge_id,))
            rec = cursor.fetchone()
            if not rec:
                await query.answer("Recharge record not found", show_alert=True)
                return
            r_user_id, r_amount = rec
            add_balance(r_user_id, r_amount)
            update_recharge_status(recharge_id, "approved")
            # notify user
            try:
                await context.bot.send_message(chat_id=r_user_id, text=t(context.application.bot_data.get(f"order_lang:{r_user_id}", "am"),
                    f"✅ ክፍያዎት ተፈቅዷል። {r_amount:.2f} ETB በቀሪ ሂሳብዎ ታክሏል።",
                    f"✅ Your recharge of {r_amount:.2f} ETB has been approved and added to your balance."))
            except Exception:
                logger.warning("Could not notify user about approved recharge.")
            await query.edit_message_caption(caption=(query.message.caption or "") + f"\n\n✅ Recharge approved ({r_amount:.2f})", reply_markup=None)
            return

        # reject recharge
        if action == "reject_recharge":
            recharge_id = obj_id
            update_recharge_status(recharge_id, "rejected")
            cursor.execute("SELECT user_id, amount FROM recharges WHERE id=?", (recharge_id,))
            rec = cursor.fetchone()
            if rec:
                r_user_id, r_amount = rec
                try:
                    await context.bot.send_message(chat_id=r_user_id, text=t(context.application.bot_data.get(f"order_lang:{r_user_id}", "am"),
                        "❌ ክፍያዎት አልተፈቀደም። እባክዎ ሌላ ዘዴ ይሞክሩ።",
                        "❌ Your recharge was rejected. Please try again or contact admin."))
                except Exception:
                    pass
            await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n❌ Recharge rejected", reply_markup=None)
            return

    # ----- small command-like buttons: balance, recharge, language -----
    if prefix == "cmd":
        if len(parts) < 2:
            await query.answer()
            return
        cmd = parts[1]
        if cmd == "balance":
            bal = get_balance(user.id)
            await query.edit_message_text(t(lang, f"Your balance: {bal:.2f} ETB", f"ቀሪ ሂሳብ: {bal:.2f} ብር"))
            return
        if cmd == "recharge":
            # show recharge amounts
            kb = [
                [InlineKeyboardButton("50 ETB", callback_data="recharge_amt|50")],
                [InlineKeyboardButton("100 ETB", callback_data="recharge_amt|100")],
                [InlineKeyboardButton("200 ETB", callback_data="recharge_amt|200")],
                [InlineKeyboardButton("Custom amount", callback_data="recharge_custom|")],
                [InlineKeyboardButton(t(lang, "Back", "ተመለስ"), callback_data="back|")]
            ]
            await query.edit_message_text(t(lang, "Choose amount to recharge:", "እባክዎ መጠን ይምረጡ።"), reply_markup=InlineKeyboardMarkup(kb))
            return
        if cmd == "language":
            kb = [
                [InlineKeyboardButton("አማርኛ", callback_data="lang|am"), InlineKeyboardButton("English", callback_data="lang|en")]
            ]
            await query.edit_message_text(t(lang, "Choose language:", "ቋንቋ ይምረጡ።"), reply_markup=InlineKeyboardMarkup(kb))
            return

    # ----- recharge amount chosen -----
    if prefix == "recharge_amt":
        amount = float(parts[1])
        user_id = user.id
        # store pending recharge in bot_data and ask to pay & send screenshot
        context.application.bot_data[f"recharge_pending:{user_id}"] = {"amount": amount, "method": None}
        kb = []
        for m in PAYMENT_INFO.keys():
            kb.append([InlineKeyboardButton(m.capitalize(), callback_data=f"recharge_pay|{m}")])
        kb.append([InlineKeyboardButton(t(lang, "Cancel", "ሰርዝ"), callback_data="back|")])
        await query.edit_message_text(t(lang,
                                       f"Send {amount:.2f} ETB to one of these accounts and upload screenshot here.",
                                       f"{amount:.2f} ብር ወደ ከዚህ አካውንቶች ይላኩ እና ስክሪንሾት ይላኩ።"), reply_markup=InlineKeyboardMarkup(kb))
        return

    # ----- custom recharge selected: ask user to type amount -----
    if prefix == "recharge_custom":
        # set flag to expect custom amount then screenshot
        context.user_data["awaiting_custom_recharge_amount"] = True
        await query.edit_message_text(t(lang, "Send the amount (numbers only):", "እባክዎ መጠን ይላኩ (ቁጥር ብቻ)።"))
        return

    # ----- user chose which account to pay for recharge -----
    if prefix == "recharge_pay":
        if len(parts) < 2:
            await query.answer()
            return
        method = parts[1]
        user_id = user.id
        pending = context.application.bot_data.get(f"recharge_pending:{user_id}")
        if not pending:
            await query.edit_message_text(t(lang, "No pending recharge found. Choose /recharge again.", "ትዕዛዝ አልተገኘም። /recharge ይግቡ።"))
            return
        pending["method"] = method
        context.application.bot_data[f"recharge_pending:{user_id}"] = pending
        acc = PAYMENT_INFO.get(method, "Not available")
        # set a mapping for language (used when notifying after admin approval)
        context.application.bot_data[f"order_lang:{user_id}"] = context.user_data.get("lang", "am")
        await query.edit_message_text(t(lang,
                                       f"Please send payment to: {acc}\nAfter payment, upload your screenshot (photo) here.",
                                       f"እባክዎ ክፍያዎን ወደ፦ {acc} ይከፍሉ። ከዚያ በኋላ ስክሪንሾት ይላኩ።"))
        return

    # ----- simple back button -----
    if prefix == "back":
        await start(update, context)
        return

    # ----- language change -----
    if prefix == "lang":
        if len(parts) >= 2:
            chosen = parts[1]
            if chosen in ("am", "en"):
                context.user_data["lang"] = chosen
                await query.edit_message_text(t(chosen, "Language set to English.", "ቋንቋ እዚህ ተቀይዧል — አማርኛ"))
        return

    # fallback
    await query.edit_message_text(t(lang, "Unknown action.", "ያልታወቀ እርስዎ።"))

# ---------------- handle user text messages (links, custom recharge amounts, etc.) ----------------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    lang = context.user_data.get("lang", "am")

    # if waiting for custom recharge amount
    if context.user_data.get("awaiting_custom_recharge_amount"):
        txt = update.message.text.strip()
        try:
            amount = float(txt)
            # store pending recharge
            context.application.bot_data[f"recharge_pending:{user_id}"] = {"amount": amount, "method": None}
            context.user_data.pop("awaiting_custom_recharge_amount", None)
            # ask to choose payment method
            kb = []
            for m in PAYMENT_INFO.keys():
                kb.append([InlineKeyboardButton(m.capitalize(), callback_data=f"recharge_pay|{m}")])
            kb.append([InlineKeyboardButton(t(lang, "Cancel", "ሰርዝ"), callback_data="back|")])
            await update.message.reply_text(t(lang,
                                            f"Send {amount:.2f} ETB to one of these accounts and upload screenshot here.",
                                            f"{amount:.2f} ብር ወደ ከዚህ አካውንቶች ይከፍሉ እና ስክሪንሾት ይላኩ።"),
                                            reply_markup=InlineKeyboardMarkup(kb))
        except Exception:
            await update.message.reply_text(t(lang, "Please send a valid number amount.", "እባክዎ ትክክለኛ ቁጥር ይላኩ።"))
        return

    # if waiting for order link/username
    if context.user_data.get("awaiting_link_for_order"):
        link = update.message.text.strip()
        order = context.application.bot_data.get(f"order:{user_id}")
        if not order:
            await update.message.reply_text(t(lang, "No order found. Use /service to start.", "ትዕዛዝ አልተገኘም። /service ይጠቀሙ።"))
            context.user_data.pop("awaiting_link_for_order", None)
            return
        order["target"] = link
        context.application.bot_data[f"order:{user_id}"] = order
        context.application.bot_data[f"order_lang:{user_id}"] = context.user_data.get("lang", "am")
        # present payment choices: Pay with balance OR external accounts
        kb = [
            [InlineKeyboardButton(t(lang, "Pay with balance", "በቀሪ ሂሳብ ይክፈሉ"), callback_data="pay|balance")],
        ]
        for m in PAYMENT_INFO.keys():
            kb.append([InlineKeyboardButton(m.capitalize(), callback_data=f"pay|{m}")])
        kb.append([InlineKeyboardButton(t(lang, "Cancel", "ሰርዝ"), callback_data="back|")])
        await update.message.reply_text(t(lang, "Choose payment method:", "እባክዎ የክፍያ ዘዴ ይምረጡ።"), reply_markup=InlineKeyboardMarkup(kb))
        context.user_data.pop("awaiting_link_for_order", None)
        return

    # other texts -> give instructions
    await update.message.reply_text(t(lang,
                                     "Use /service to start an order, /recharge to add balance, or /balance to see your balance.",
                                     "እባክዎ /service ይጠቀሙ ለትዕዛዝ፣ /recharge ለገንዘብ ማስገቢያ፣ ወይም /balance ለቀሪ ሂሳብ።"))

# ---------------- Photo handler: either order payment screenshot or recharge screenshot ----------------
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    lang = context.user_data.get("lang", "am")

    # check if there is a pending recharge for this user
    pending_recharge = context.application.bot_data.get(f"recharge_pending:{user_id}")
    if pending_recharge:
        # handle recharge screenshot
        if not update.message.photo:
            await update.message.reply_text(t(lang, "Please send a photo screenshot.", "እባክዎ ስክሪንሾት ይላኩ።"))
            return
        file_id = update.message.photo[-1].file_id
        amount = pending_recharge.get("amount")
        method = pending_recharge.get("method")  # may be None if custom but user should have chosen
        # create recharge record
        recharge_id = create_recharge(user_id, amount, method or "unknown", status="pending")
        # send photo to admin with approve/reject buttons, include recharge_id and user_id in callback
        caption = f"🔔 Recharge request\nUser: @{user.username or user.first_name} (ID: {user_id})\nAmount: {amount:.2f} ETB\nMethod: {method or 'N/A'}\nRecharge ID: {recharge_id}"
        admin_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve", callback_data=f"admin|approve_recharge|{recharge_id}|{user_id}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"admin|reject_recharge|{recharge_id}|{user_id}")],
        ])
        try:
            sent = await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=caption, reply_markup=admin_kb)
            # optionally store admin message id in recharge row
            update_recharge_status(recharge_id, "pending", admin_message_id=sent.message_id)
            # clear pending recharge
            context.application.bot_data.pop(f"recharge_pending:{user_id}", None)
            # map user lang for admin messages
            context.application.bot_data[f"order_lang:{user_id}"] = lang
            await update.message.reply_text(t(lang, "ክፍያዎን እየገመገምን ነው። እባክዎ ይጠብቁ።", "We are reviewing your payment. Please wait."))
        except Exception as e:
            logger.exception("Failed to forward recharge to admin: %s", e)
            await update.message.reply_text(t(lang, "Could not forward screenshot to admin. Try later.", "ስክሪንሾትን ወደ አስተዳደር ማስመላለሻ አልተቻለም።"))
        return

    # else check if there's a pending order with payment pending
    order = context.application.bot_data.get(f"order:{user_id}")
    if order and order.get("order_id") and order.get("payment_method"):
        # treat this photo as proof for that order
        if not update.message.photo:
            await update.message.reply_text(t(lang, "Please send a photo screenshot.", "እባክዎ ስክሪንሾት ይላኩ።"))
            return
        file_id = update.message.photo[-1].file_id
        order_id = order.get("order_id")
        caption = (f"🔔 Order payment\nUser: @{user.username or user.first_name} (ID: {user_id})\n"
                   f"Order ID: {order_id}\nService: {SERVICES[order['service_key']]['label_en']} - {order['package_title']}\n"
                   f"Target: {order.get('target','N/A')}\nPrice: {order['price']:.2f} ETB\nMethod: {order.get('payment_method','N/A')}")
        admin_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve", callback_data=f"admin|approve_order|{order_id}|{user_id}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"admin|reject_order|{order_id}|{user_id}")],
        ])
        try:
            sent = await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=caption, reply_markup=admin_kb)
            # map language for notifications later
            context.application.bot_data[f"order_lang:{user_id}"] = lang
            await update.message.reply_text(t(lang, "ክፍያዎን እየገመገምን ነው። እባክዎ ይጠብቁ።", "We are reviewing your payment. Please wait."))
            # clear order from bot_data (we keep DB record)
            context.application.bot_data.pop(f"order:{user_id}", None)
        except Exception as e:
            logger.exception("Failed to forward order payment to admin: %s", e)
            await update.message.reply_text(t(lang, "Could not forward screenshot to admin. Try later.", "ስክሪንሾትን ወደ አስተዳደር ማስመላለሻ አልተቻለም።"))
        return

    # no pending things
    await update.message.reply_text(t(lang, "No pending order or recharge found. Use /service or /recharge to start.", "ምንም የቆየ ትዕዛዝ ወይም ክፍያ የለም። /service ወይም /recharge ይጠቀሙ።"))

# ---------------- Commands ----------------
async def service_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = context.user_data.get("lang", "am")
    bal = get_balance(user_id)
    await update.message.reply_text(t(lang, f"Your balance: {bal:.2f} ETB", f"ቀሪ ሂሳብ: {bal:.2f} ብር"))

async def recharge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "am")
    kb = [
        [InlineKeyboardButton("50 ETB", callback_data="recharge_amt|50")],
        [InlineKeyboardButton("100 ETB", callback_data="recharge_amt|100")],
        [InlineKeyboardButton("200 ETB", callback_data="recharge_amt|200")],
        [InlineKeyboardButton("Custom amount", callback_data="recharge_custom|")],
        [InlineKeyboardButton(t(lang, "Cancel", "ሰርዝ"), callback_data="back|")]
    ]
    await update.message.reply_text(t(lang, "Choose amount to recharge:", "እባክዎ መጠን ይምረጡ።"), reply_markup=InlineKeyboardMarkup(kb))

# admin-only helper command to add balance manually if needed
async def addbalance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(context.args[0])
        amount = float(context.args[1])
        new_bal = add_balance(user_id, amount)
        await update.message.reply_text(f"✅ Added {amount:.2f} ETB to {user_id}. New balance: {new_bal:.2f} ETB")
    except Exception:
        await update.message.reply_text("Usage: /addbalance <user_id> <amount>")

# ---------------- fallback unknown commands ----------------
async def unknown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "am")
    await update.message.reply_text(t(lang, "Use /service or /recharge to start.", "እባክዎ /service ወይም /recharge ይጠቀሙ።"))

# ---------------- Main ----------------
def main():
    if not BOT_TOKEN or BOT_TOKEN.startswith("PASTE_"):
        logger.error("Please set BOT_TOKEN and ADMIN_ID in environment or in the file.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("service", service_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("recharge", recharge_cmd))
    app.add_handler(CommandHandler("addbalance", addbalance_cmd))

    # Inline callback handler
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Photo & text handlers
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Unknown commands
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

    logger.info("Elevate Promotion bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
