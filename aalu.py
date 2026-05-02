import requests
import json
import random
import string
import certifi
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, PreCheckoutQueryHandler, ContextTypes, filters
from telegram.error import BadRequest

# ============================================================
#                     CONFIGURATION
# ============================================================

API_URL          = "num.zvx.workers.dev/?key=DxD&mobile={}"
BOT_TOKEN        = "8693982920:AAH_fwloRRWwRCgNyYyVNeZlY1PoVcyPcG0"
BOT_USERNAME     = "Gamcchhaa_Bot"
CUSTOM_NAME      = "@ROLEX_SIR009 & @Darkdon01 & @DarkGalaxxyy & @R4HULxTRUSTED"
ADMIN_ID         = 6131370190
MONGO_URI        = "mongodb+srv://saitamauchiha01025_db_user:yMvHQKjjRpFsgDxz@cluster0.fomymln.mongodb.net/?appName=Cluster0"
PAYOUT_CHANNEL   = -1003579822719
UPI_ID           = "darkgalaxxyyy@naviaxis"
UPI_QR_LINK      = "https://t.me/jaiwkwkwkkwkwkjwkq/2"
STARS_PER_CREDIT = 2   # 1 star = 2 credits (so user pays stars, gets 2x credits)

# Credit Settings
START_CREDITS = 2
REFER_CREDITS = 2

# Mode: dual / group / private / maintenance
MODE = "dual"

# Unlimited Mode
UNLIMITED_MODE = False

# Force Join Settings
FORCE_CHANNEL_USERNAME = "siee1234"
FORCE_CHANNEL_LINK     = "https://t.me/siee1234"
FORCE_GROUP1_LINK      = "https://t.me/+QmnlbCK1x045MzZl"
FORCE_GROUP2_ID        = -1003416250413
FORCE_GROUP2_LINK      = "https://t.me/+cePuY51FkgE5MzY1"

# ============================================================
#                     MONGODB ASYNC SETUP
# ============================================================

client = AsyncIOMotorClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000
)
db       = client["numbot"]
users    = db["users"]
vouchers = db["vouchers"]

# ============================================================
#                     DATA MANAGEMENT
# ============================================================

async def get_user(user_id):
    return await users.find_one({"user_id": user_id})

async def create_user(user_id, referred_by=None):
    ref_code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    user = {
        "user_id"    : user_id,
        "credits"    : START_CREDITS,
        "joined"     : datetime.now().strftime("%Y-%m-%d"),
        "ref_code"   : ref_code,
        "referred_by": referred_by,
        "referrals"  : 0,
        "username"   : None
    }
    await users.insert_one(user)
    if referred_by:
        await users.update_one(
            {"user_id": referred_by},
            {"$inc": {"credits": REFER_CREDITS, "referrals": 1}}
        )
    return user

async def update_credits(user_id, amount):
    result = await users.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"credits": amount}},
        return_document=True
    )
    return result["credits"] if result else None

async def set_credits(user_id, amount):
    result = await users.update_one({"user_id": user_id}, {"$set": {"credits": amount}})
    return result.modified_count > 0

# ============================================================
#                     KEYBOARDS
# ============================================================

def get_main_keyboard(user_id):
    if user_id == ADMIN_ID:
        keyboard = [
            [KeyboardButton("🔍 Search Number"), KeyboardButton("👤 My Account")],
            [KeyboardButton("💰 Credits"),        KeyboardButton("🔗 Refer")],
            [KeyboardButton("💳 Buy Credits"),    KeyboardButton("❓ Help")],
            [KeyboardButton("⚙️ Admin Panel")],
        ]
    else:
        keyboard = [
            [KeyboardButton("🔍 Search Number"), KeyboardButton("👤 My Account")],
            [KeyboardButton("💰 Credits"),        KeyboardButton("🔗 Refer")],
            [KeyboardButton("💳 Buy Credits"),    KeyboardButton("❓ Help")],
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ============================================================
#                     MEMBERSHIP CHECK
# ============================================================

async def check_membership(bot, user_id, chat):
    try:
        member = await bot.get_chat_member(chat, user_id)
        if member.status in ["kicked", "left"]:
            return False
        return True
    except BadRequest as e:
        if "user not found" in str(e).lower():
            return False
        return True
    except Exception:
        return True

async def force_join_check(bot, user_id):
    in_channel = await check_membership(bot, user_id, f"@{FORCE_CHANNEL_USERNAME}")
    in_group2  = await check_membership(bot, user_id, FORCE_GROUP2_ID)
    return in_channel and in_group2

# ============================================================
#                     START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    username = update.effective_user.username
    bot      = context.bot

    referred_by = None
    if context.args and context.args[0].startswith("ref_"):
        ref_code = context.args[0][4:]
        referrer = await users.find_one({"ref_code": ref_code})
        if referrer and referrer["user_id"] != user_id:
            referred_by = referrer["user_id"]

    joined = await force_join_check(bot, user_id)
    if not joined:
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel", url=FORCE_CHANNEL_LINK)],
            [InlineKeyboardButton("👥 Join Group 1", url=FORCE_GROUP1_LINK)],
            [InlineKeyboardButton("👥 Join Group 2", url=FORCE_GROUP2_LINK)],
        ]
        await update.message.reply_text(
            "⚠️ Access Restricted\n\n"
            "To use this bot, please join all of the following:\n\n"
            "Once joined or request sent, send /start again.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    user   = await get_user(user_id)
    is_new = user is None
    if is_new:
        user = await create_user(user_id, referred_by)

    if username:
        await users.update_one({"user_id": user_id}, {"$set": {"username": username}})

    inline_keyboard = [
        [
            InlineKeyboardButton("📢 Channel", url=FORCE_CHANNEL_LINK),
            InlineKeyboardButton("👥 Group 1", url=FORCE_GROUP1_LINK),
        ],
        [InlineKeyboardButton("👥 Group 2", url=FORCE_GROUP2_LINK)],
    ]

    unlimited_note = "\n♾️ Unlimited Mode is currently ON — searches are free!\n" if UNLIMITED_MODE else ""
    welcome = f"🎉 Welcome! You received {START_CREDITS} free credits!\n\n" if is_new else "👋 Welcome back!\n\n"
    msg = (
        f"{welcome}"
        f"{unlimited_note}"
        "🔍 This bot lets you fetch detailed information about any number.\n"
        "Powered by @siee1234\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📌 Commands:\n\n"
        "/num <number> — Fetch number info\n"
        "/referstat — Refer leaderboard\n"
        "/redeem <code> — Redeem a voucher\n"
        "/start — Show this message\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard))
    await update.message.reply_text("Use the buttons below to navigate:", reply_markup=get_main_keyboard(user_id))

# ============================================================
#                     PROCESS NUMBER
# ============================================================

async def process_number(update, context, number):
    user_id   = update.effective_user.id
    chat_type = update.effective_chat.type
    bot       = context.bot

    if MODE == "maintenance":
        await update.message.reply_text("🔧 Bot is under maintenance. Please try again later.")
        return
    if MODE == "group" and chat_type == "private":
        await update.message.reply_text("⚠️ This bot only works in groups.")
        return
    if MODE == "private" and chat_type in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ This bot only works in private chat.")
        return

    joined = await force_join_check(bot, user_id)
    if not joined:
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel", url=FORCE_CHANNEL_LINK)],
            [InlineKeyboardButton("👥 Join Group 1", url=FORCE_GROUP1_LINK)],
            [InlineKeyboardButton("👥 Join Group 2", url=FORCE_GROUP2_LINK)],
        ]
        await update.message.reply_text(
            "⚠️ Access Restricted\n\nPlease join all required channels/groups first.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    user = await get_user(user_id)
    if user is None:
        user = await create_user(user_id)

    if not UNLIMITED_MODE:
        if user["credits"] <= 0:
            await update.message.reply_text(
                "❌ You have 0 credits!\n\n"
                "Refer friends to earn more credits or buy credits.\n"
                "Use 🔗 Refer button to get your refer link or dm @DarkGalaxxyy to buy credits."
            )
            return

    try:
        url = API_URL.format(number)
        if not url.startswith("http"):
            url = "https://" + url
        response = requests.get(url, timeout=10)
        result   = response.text.strip()

        if not result:
            await update.message.reply_text("❌ No result found for this number.")
            return

        if UNLIMITED_MODE:
            credit_note = "♾️ Unlimited Mode ON — no credits deducted"
        else:
            new_balance = await update_credits(user_id, -1)
            credit_note = f"💰 Credits remaining: {new_balance}"

        try:
            data = json.loads(result)
            if "Api_BY" in data:
                data["Api_BY"] = CUSTOM_NAME
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
            await update.message.reply_text(
                f"```\n{pretty}\n```\n\n{credit_note}",
                parse_mode="Markdown"
            )
        except json.JSONDecodeError:
            await update.message.reply_text(f"{result}\n\n{credit_note}")

    except requests.exceptions.Timeout:
        await update.message.reply_text("❌ Request timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("❌ Unable to connect to the API.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📌 Usage: /num <number>\nExample: /num 1234567890")
        return
    await process_number(update, context, context.args[0])

# ============================================================
#                     REFER LEADERBOARD
# ============================================================

async def referstat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = await users.find(
        {"referrals": {"$gt": 0}, "user_id": {"$ne": ADMIN_ID}},
        {"username": 1, "user_id": 1, "referrals": 1}
    ).sort("referrals", -1).limit(10).to_list(length=10)

    if not top_users:
        await update.message.reply_text("🔗 No referrals yet! Be the first to refer.")
        return

    medals = ["🥇", "🥈", "🥉"]
    msg = "🏆 Refer Leaderboard\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, u in enumerate(top_users):
        medal = medals[i] if i < 3 else f"{i+1}."
        name  = f"@{u['username']}" if u.get("username") else f"User {u['user_id']}"
        msg  += f"{medal} {name} — {u['referrals']} refers\n"
    msg += "\n━━━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(msg)

# ============================================================
#                     VOUCHER SYSTEM
# ============================================================

async def createvoucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if len(context.args) < 3:
        await update.message.reply_text("📌 Usage: /createvoucher <code> <credits> <max_uses>\nExample: /createvoucher SAVE50 50 100")
        return
    code     = context.args[0].upper()
    credits  = int(context.args[1])
    max_uses = int(context.args[2])
    existing = await vouchers.find_one({"code": code})
    if existing:
        await update.message.reply_text(f"❌ Voucher code '{code}' already exists.")
        return
    await vouchers.insert_one({
        "code"    : code,
        "credits" : credits,
        "max_uses": max_uses,
        "uses"    : 0,
        "used_by" : []
    })
    await update.message.reply_text(
        f"✅ Voucher Created!\n\n"
        f"📌 Code: {code}\n"
        f"💰 Credits: {credits}\n"
        f"👥 Max Uses: {max_uses}"
    )


async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("📌 Usage: /redeem <code>\nExample: /redeem SAVE50")
        return
    code    = context.args[0].upper()
    voucher = await vouchers.find_one({"code": code})
    if not voucher:
        await update.message.reply_text("❌ Invalid voucher code.")
        return
    if voucher["uses"] >= voucher["max_uses"]:
        await update.message.reply_text("❌ This voucher has expired (max uses reached).")
        return
    if user_id in voucher["used_by"]:
        await update.message.reply_text("❌ You have already redeemed this voucher.")
        return
    await vouchers.update_one(
        {"code": code},
        {"$inc": {"uses": 1}, "$push": {"used_by": user_id}}
    )
    new_balance = await update_credits(user_id, voucher["credits"])
    await update.message.reply_text(
        f"🎉 Voucher Redeemed Successfully!\n\n"
        f"💰 Credits Added: {voucher['credits']}\n"
        f"💳 New Balance: {new_balance}"
    )


async def deletevoucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /deletevoucher <code>")
        return
    code   = context.args[0].upper()
    result = await vouchers.delete_one({"code": code})
    if result.deleted_count:
        await update.message.reply_text(f"✅ Voucher '{code}' deleted.")
    else:
        await update.message.reply_text(f"❌ Voucher '{code}' not found.")


async def listvouchers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    all_vouchers = await vouchers.find({}).to_list(length=50)
    if not all_vouchers:
        await update.message.reply_text("No vouchers found.")
        return
    msg = "🎟️ All Vouchers\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for v in all_vouchers:
        msg += f"📌 {v['code']} | 💰 {v['credits']} credits | 👥 {v['uses']}/{v['max_uses']} used\n"
    await update.message.reply_text(msg)

# ============================================================
#                     TELEGRAM STARS PAYMENT
# ============================================================

async def buystars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "⭐ Buy Credits with Telegram Stars\n\n"
            "Usage: /buystars <stars>\n"
            "Example: /buystars 10 → you get 20 credits\n\n"
            f"Rate: 1 ⭐ = {STARS_PER_CREDIT} credits"
        )
        return

    stars   = int(context.args[0])
    credits = stars * STARS_PER_CREDIT

    await update.message.reply_invoice(
        title="Buy Credits",
        description=f"Purchase {credits} credits for {stars} Telegram Stars",
        payload=f"stars_{stars}_{update.effective_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=f"{credits} Credits", amount=stars)],
    )


async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payment = update.message.successful_payment
    stars   = payment.total_amount
    credits = stars * STARS_PER_CREDIT

    new_balance = await update_credits(user_id, credits)
    await update.message.reply_text(
        f"✅ Payment Successful!\n\n"
        f"⭐ Stars Paid: {stars}\n"
        f"💰 Credits Added: {credits}\n"
        f"💳 New Balance: {new_balance}"
    )

# ============================================================
#                     BUTTON HANDLERS
# ============================================================

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text    = update.message.text
    user_id = update.effective_user.id
    bot     = context.bot

    # ── Search Number ──
    if text == "🔍 Search Number":
        joined = await force_join_check(bot, user_id)
        if not joined:
            keyboard = [
                [InlineKeyboardButton("📢 Join Channel", url=FORCE_CHANNEL_LINK)],
                [InlineKeyboardButton("👥 Join Group 1", url=FORCE_GROUP1_LINK)],
                [InlineKeyboardButton("👥 Join Group 2", url=FORCE_GROUP2_LINK)],
            ]
            await update.message.reply_text(
                "⚠️ Please join all required channels/groups first.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        context.user_data["waiting_for_number"] = True
        await update.message.reply_text("📲 Please enter the number you want to search:")
        return

    # ── Waiting for number ──
    if context.user_data.get("waiting_for_number"):
        context.user_data["waiting_for_number"] = False
        if text.isdigit():
            await process_number(update, context, text)
        else:
            await update.message.reply_text("❌ Invalid number. Please enter digits only.")
        return

    # ── Waiting for UPI screenshot ──
    if context.user_data.get("waiting_for_screenshot"):
        context.user_data["waiting_for_screenshot"] = False
        await update.message.reply_text(
            "⏳ Payment request submitted!\n\n"
            "Please wait for admin approval.\n"
            "Credits will be added once verified."
        )
        return

    # ── My Account ──
    if text == "👤 My Account":
        user = await get_user(user_id)
        if user is None:
            user = await create_user(user_id)
        unlimited_note = "\n♾️ Unlimited Mode ON — searches are free!" if UNLIMITED_MODE else ""
        await update.message.reply_text(
            "👤 My Account\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 User ID: {user_id}\n"
            f"💰 Credits: {user['credits']}{unlimited_note}\n"
            f"📅 Joined: {user['joined']}\n"
            f"👥 Referrals: {user['referrals']}\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        return

    # ── Credits ──
    if text == "💰 Credits":
        unlimited_note = "\n♾️ Unlimited Mode is currently ON — searches are FREE for everyone!" if UNLIMITED_MODE else ""
        await update.message.reply_text(
            "💰 What are Credits?\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Credits are required to search numbers.{unlimited_note}\n"
            "Each search costs 1 credit.\n\n"
            "📌 How to get Credits:\n\n"
            f"• New users get {START_CREDITS} free credits\n"
            f"• Refer a friend → earn {REFER_CREDITS} credits\n"
            "• Redeem a voucher → /redeem <code>\n"
            "• Buy via UPI or Telegram Stars → 💳 Buy Credits\n\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        return

    # ── Refer ──
    if text == "🔗 Refer":
        user = await get_user(user_id)
        if user is None:
            user = await create_user(user_id)
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user['ref_code']}"
        await update.message.reply_text(
            "🔗 Refer & Earn\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Your Refer Link:\n{ref_link}\n\n"
            f"Share this link with friends.\n"
            f"You will receive {REFER_CREDITS} credits for each friend who joins!\n\n"
            f"👥 Your total referrals: {user['referrals']}\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        return

    # ── Buy Credits ──
    if text == "💳 Buy Credits":
        username = update.effective_user.username
        uname    = f"@{username}" if username else f"User {user_id}"
        keyboard = [
            [InlineKeyboardButton("📸 I've Paid via UPI", callback_data="upi_paid")],
        ]
        await update.message.reply_photo(
            photo=UPI_QR_LINK,
            caption=(
                "💳 Buy Credits\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "💵 Rate: ₹1 = 1 Credit\n\n"
                "📌 Pay via UPI:\n"
                f"UPI ID: `{UPI_ID}`\n\n"
                "After payment, send your screenshot here.\n"
                "Admin will verify and add credits.\n\n"
                "⭐ Or buy with Telegram Stars:\n"
                f"/buystars <amount> (1 star = {STARS_PER_CREDIT} credits)\n"
                "━━━━━━━━━━━━━━━━━━━━"
            ),
            parse_mode="Markdown"
        )
        context.user_data["waiting_for_screenshot"] = True
        context.user_data["pending_upi_user_id"]    = user_id
        context.user_data["pending_upi_username"]   = uname
        await update.message.reply_text("📸 Send your payment screenshot now:")
        return

    # ── Help ──
    if text == "❓ Help":
        await update.message.reply_text(
            "❓ Help & Support\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "For any issues or queries, contact:\n\n"
            "👤 @DarkGalaxxyy\n\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        return

    # ── Admin Panel ──
    if text == "⚙️ Admin Panel":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ Access Denied.")
            return
        total_users    = await users.count_documents({})
        total_credits  = 0
        async for u in users.find({}, {"credits": 1}):
            total_credits += u["credits"]
        total_vouchers = await vouchers.count_documents({})
        unlimited_status = "ON ♾️" if UNLIMITED_MODE else "OFF"
        await update.message.reply_text(
            "⚙️ Admin Panel\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔧 Mode: {MODE}\n"
            f"♾️ Unlimited Mode: {unlimited_status}\n"
            f"👤 Total Users: {total_users}\n"
            f"💰 Total Credits: {total_credits}\n"
            f"🎁 Start Credits: {START_CREDITS}\n"
            f"🔗 Refer Credits: {REFER_CREDITS}\n"
            f"🎟️ Active Vouchers: {total_vouchers}\n\n"
            "📌 Admin Commands:\n\n"
            "/setmode <mode> — dual|group|private|maintenance\n"
            "/unlimited on|off — Toggle unlimited mode\n"
            "/broadcast <msg> — Send to all users\n"
            "/stats\n"
            "/addcredits <uid> <amount>\n"
            "/removecredits <uid> <amount>\n"
            "/setcredits <uid> <amount>\n"
            "/checkbalance <uid>\n"
            "/setstartcredits <amount>\n"
            "/setrefercredits <amount>\n"
            "/createvoucher <code> <credits> <max_uses>\n"
            "/deletevoucher <code>\n"
            "/listvouchers\n"
            "/buystars <amount>\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        return


# ── Handle screenshot (photo message) ──
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    username = update.effective_user.username
    uname    = f"@{username}" if username else f"User {user_id}"

    if not context.user_data.get("waiting_for_screenshot"):
        return

    context.user_data["waiting_for_screenshot"] = False

    # Forward screenshot to payouts channel with details
    caption = (
        "💳 New Payment Request\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 User ID: {user_id}\n"
        f"📛 Username: {uname}\n"
        f"📊 Status: Pending ⏳\n\n"
        f"To approve: /addcredits {user_id} <amount>"
    )

    await context.bot.forward_message(
        chat_id=PAYOUT_CHANNEL,
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id
    )
    await context.bot.send_message(chat_id=PAYOUT_CHANNEL, text=caption)

    await update.message.reply_text(
        "✅ Screenshot received!\n\n"
        "⏳ Please wait for admin approval.\n"
        "Credits will be added once payment is verified."
    )

# ============================================================
#                     ADMIN COMMANDS
# ============================================================

async def setmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MODE
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /setmode <mode>\nModes: dual | group | private | maintenance")
        return
    new_mode = context.args[0].lower()
    if new_mode not in ["dual", "group", "private", "maintenance"]:
        await update.message.reply_text("❌ Invalid mode.")
        return
    MODE = new_mode
    await update.message.reply_text(f"✅ Mode set to: {MODE}")


async def unlimited(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global UNLIMITED_MODE
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /unlimited on|off")
        return
    val = context.args[0].lower()
    if val == "on":
        UNLIMITED_MODE = True
        await update.message.reply_text("♾️ Unlimited Mode is now ON\n\nAll users can search without spending credits.")
    elif val == "off":
        UNLIMITED_MODE = False
        await update.message.reply_text("✅ Unlimited Mode is now OFF\n\nCredits will be deducted as normal.")
    else:
        await update.message.reply_text("❌ Use: /unlimited on or /unlimited off")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /broadcast <message>")
        return
    message = " ".join(context.args)
    success = failed = 0
    async for u in users.find({}, {"user_id": 1}):
        try:
            await context.bot.send_message(chat_id=u["user_id"], text=message)
            success += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"📢 Broadcast Complete\n\n✅ Sent: {success}\n❌ Failed: {failed}")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    total_users    = await users.count_documents({})
    total_credits  = 0
    async for u in users.find({}, {"credits": 1}):
        total_credits += u["credits"]
    total_vouchers = await vouchers.count_documents({})
    unlimited_status = "ON ♾️" if UNLIMITED_MODE else "OFF"
    await update.message.reply_text(
        f"📊 Bot Statistics\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Total Users: {total_users}\n"
        f"💰 Total Credits: {total_credits}\n"
        f"🔧 Mode: {MODE}\n"
        f"♾️ Unlimited: {unlimited_status}\n"
        f"🎁 Start Credits: {START_CREDITS}\n"
        f"🔗 Refer Credits: {REFER_CREDITS}\n"
        f"🎟️ Vouchers: {total_vouchers}"
    )


async def addcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("📌 Usage: /addcredits <user_id> <amount>")
        return
    new_bal = await update_credits(int(context.args[0]), int(context.args[1]))
    if new_bal is None:
        await update.message.reply_text("❌ User not found.")
        return
    await update.message.reply_text(f"✅ Added {context.args[1]} credits\n💰 New Balance: {new_bal}")


async def removecredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("📌 Usage: /removecredits <user_id> <amount>")
        return
    new_bal = await update_credits(int(context.args[0]), -int(context.args[1]))
    if new_bal is None:
        await update.message.reply_text("❌ User not found.")
        return
    await update.message.reply_text(f"✅ Removed {context.args[1]} credits\n💰 New Balance: {new_bal}")


async def setcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("📌 Usage: /setcredits <user_id> <amount>")
        return
    success = await set_credits(int(context.args[0]), int(context.args[1]))
    if not success:
        await update.message.reply_text("❌ User not found.")
        return
    await update.message.reply_text(f"✅ Credits set to {context.args[1]} for user {context.args[0]}")


async def checkbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /checkbalance <user_id>")
        return
    user = await get_user(int(context.args[0]))
    if not user:
        await update.message.reply_text("❌ User not found.")
        return
    await update.message.reply_text(
        f"👤 User: {context.args[0]}\n"
        f"💰 Credits: {user['credits']}\n"
        f"📅 Joined: {user['joined']}\n"
        f"👥 Referrals: {user['referrals']}"
    )


async def setstartcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global START_CREDITS
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /setstartcredits <amount>")
        return
    START_CREDITS = int(context.args[0])
    await update.message.reply_text(f"✅ Start credits set to: {START_CREDITS}")


async def setrefercredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global REFER_CREDITS
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /setrefercredits <amount>")
        return
    REFER_CREDITS = int(context.args[0])
    await update.message.reply_text(f"✅ Refer credits set to: {REFER_CREDITS}")

# ============================================================
#                     MAIN
# ============================================================

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",           start))
    app.add_handler(CommandHandler("num",             num))
    app.add_handler(CommandHandler("referstat",       referstat))
    app.add_handler(CommandHandler("redeem",          redeem))
    app.add_handler(CommandHandler("buystars",        buystars))
    app.add_handler(CommandHandler("createvoucher",   createvoucher))
    app.add_handler(CommandHandler("deletevoucher",   deletevoucher))
    app.add_handler(CommandHandler("listvouchers",    listvouchers))
    app.add_handler(CommandHandler("unlimited",       unlimited))
    app.add_handler(CommandHandler("setmode",         setmode))
    app.add_handler(CommandHandler("broadcast",       broadcast))
    app.add_handler(CommandHandler("stats",           stats))
    app.add_handler(CommandHandler("addcredits",      addcredits))
    app.add_handler(CommandHandler("removecredits",   removecredits))
    app.add_handler(CommandHandler("setcredits",      setcredits))
    app.add_handler(CommandHandler("checkbalance",    checkbalance))
    app.add_handler(CommandHandler("setstartcredits", setstartcredits))
    app.add_handler(CommandHandler("setrefercredits", setrefercredits))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    print("Bot is running...")
    app.run_polling()
