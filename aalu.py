import requests
import json
import random
import string
from datetime import datetime
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.error import BadRequest

# ============================================================
#                     CONFIGURATION
# ============================================================

API_URL      = "num.zvx.workers.dev/?key=DxD&mobile={}"
BOT_TOKEN    = "8693982920:AAH_fwloRRWwRCgNyYyVNeZlY1PoVcyPcG0"
BOT_USERNAME = "Gamcchhaa_Bot"  # Without @
CUSTOM_NAME  = "@ROLEX_SIR009 & @Darkdon01 & @DarkGalaxxyy & @R4HULxTRUSTED"
ADMIN_ID     = 6131370190
MONGO_URI    = "mongodb+srv://saitamauchiha01025_db_user:yMvHQKjjRpFsgDxz@cluster0.fomymln.mongodb.net/?appName=Cluster0"

# Credit Settings
START_CREDITS = 4
REFER_CREDITS = 2

# Mode: dual / group / private / maintenance
MODE = "dual"

# Force Join Settings
FORCE_CHANNEL_USERNAME = "siee1234"
FORCE_CHANNEL_LINK     = "https://t.me/siee1234"
FORCE_GROUP1_LINK      = "https://t.me/+QmnlbCK1x045MzZl"
FORCE_GROUP2_ID        = -1003416250413
FORCE_GROUP2_LINK      = "https://t.me/+cePuY51FkgE5MzY1"

# ============================================================
#                     MONGODB SETUP
# ============================================================

client = MongoClient(MONGO_URI)
db     = client["numbot"]
users  = db["users"]

# ============================================================
#                     DATA MANAGEMENT
# ============================================================

def get_user(user_id):
    return users.find_one({"user_id": user_id})

def create_user(user_id, referred_by=None):
    ref_code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    user = {
        "user_id"    : user_id,
        "credits"    : START_CREDITS,
        "joined"     : datetime.now().strftime("%Y-%m-%d"),
        "ref_code"   : ref_code,
        "referred_by": referred_by,
        "referrals"  : 0
    }
    users.insert_one(user)
    if referred_by:
        users.update_one({"user_id": referred_by}, {"$inc": {"credits": REFER_CREDITS, "referrals": 1}})
    return user

def update_credits(user_id, amount):
    result = users.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"credits": amount}},
        return_document=True
    )
    return result["credits"] if result else None

def set_credits(user_id, amount):
    result = users.update_one({"user_id": user_id}, {"$set": {"credits": amount}})
    return result.modified_count > 0

# ============================================================
#                     KEYBOARDS
# ============================================================

def get_main_keyboard(user_id):
    if user_id == ADMIN_ID:
        keyboard = [
            [KeyboardButton("🔍 Search Number"), KeyboardButton("👤 My Account")],
            [KeyboardButton("💰 Credits"),        KeyboardButton("🔗 Refer")],
            [KeyboardButton("💳 Buy Credits"),    KeyboardButton("⚙️ Admin Panel")],
        ]
    else:
        keyboard = [
            [KeyboardButton("🔍 Search Number"), KeyboardButton("👤 My Account")],
            [KeyboardButton("💰 Credits"),        KeyboardButton("🔗 Refer")],
            [KeyboardButton("💳 Buy Credits")],
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
    user_id = update.effective_user.id
    bot     = context.bot

    # Refer code check
    referred_by = None
    if context.args and context.args[0].startswith("ref_"):
        ref_code = context.args[0][4:]
        referrer = users.find_one({"ref_code": ref_code})
        if referrer and referrer["user_id"] != user_id:
            referred_by = referrer["user_id"]

    # Force join check
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

    # Register user
    user   = get_user(user_id)
    is_new = user is None
    if is_new:
        user = create_user(user_id, referred_by)

    inline_keyboard = [
        [
            InlineKeyboardButton("📢 Channel", url=FORCE_CHANNEL_LINK),
            InlineKeyboardButton("👥 Group 1", url=FORCE_GROUP1_LINK),
        ],
        [InlineKeyboardButton("👥 Group 2", url=FORCE_GROUP2_LINK)],
    ]

    welcome = "🎉 Welcome! You received 4 free credits!\n\n" if is_new else "👋 Welcome back!\n\n"
    msg = (
        f"{welcome}"
        "🔍 This bot lets you fetch detailed information about any number.\n"
        "Powered by @siee1234\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📌 Commands:\n\n"
        "/num <number> — Fetch number info\n"
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

    user = get_user(user_id)
    if user is None:
        user = create_user(user_id)

    if user["credits"] <= 0:
        await update.message.reply_text(
            "❌ You have 0 credits!\n\n"
            "Refer friends to earn more credits or buy credits.\n"
            "Use 🔗 Refer button to get your refer link."
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

        new_balance = update_credits(user_id, -1)

        try:
            data = json.loads(result)
            if "Api_BY" in data:
                data["Api_BY"] = CUSTOM_NAME
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
            await update.message.reply_text(
                f"```\n{pretty}\n```\n\n💰 Credits remaining: {new_balance}",
                parse_mode="Markdown"
            )
        except json.JSONDecodeError:
            await update.message.reply_text(f"{result}\n\n💰 Credits remaining: {new_balance}")

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
#                     BUTTON HANDLERS
# ============================================================

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text    = update.message.text
    user_id = update.effective_user.id
    bot     = context.bot

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

    if context.user_data.get("waiting_for_number"):
        context.user_data["waiting_for_number"] = False
        if text.isdigit():
            await process_number(update, context, text)
        else:
            await update.message.reply_text("❌ Invalid number. Please enter digits only.")
        return

    if text == "👤 My Account":
        user = get_user(user_id) or create_user(user_id)
        await update.message.reply_text(
            "👤 My Account\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 User ID: {user_id}\n"
            f"💰 Credits: {user['credits']}\n"
            f"📅 Joined: {user['joined']}\n"
            f"👥 Referrals: {user['referrals']}\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        return

    if text == "💰 Credits":
        await update.message.reply_text(
            "💰 What are Credits?\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Credits are required to search numbers.\n"
            "Each search costs 1 credit.\n\n"
            "📌 How to get Credits:\n\n"
            f"• New users get {START_CREDITS} free credits\n"
            f"• Refer a friend → earn {REFER_CREDITS} credits\n"
            "• Buy credits → ₹1 = 1 credit\n\n"
            "Use 🔗 Refer or 💳 Buy Credits buttons!\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        return

    if text == "🔗 Refer":
        user     = get_user(user_id) or create_user(user_id)
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

    if text == "💳 Buy Credits":
        await update.message.reply_text(
            "💳 Buy Credits\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💵 Rate: ₹1 = 1 Credit\n\n"
            "To purchase credits, contact:\n"
            "👤 @DarkGalaxxyy\n\n"
            f"Send your User ID: {user_id}\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        return

    if text == "⚙️ Admin Panel":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ Access Denied.")
            return
        total_users   = users.count_documents({})
        total_credits = sum(u["credits"] for u in users.find({}, {"credits": 1}))
        await update.message.reply_text(
            "⚙️ Admin Panel\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔧 Mode: {MODE}\n"
            f"👤 Total Users: {total_users}\n"
            f"💰 Total Credits: {total_credits}\n"
            f"🎁 Start Credits: {START_CREDITS}\n"
            f"🔗 Refer Credits: {REFER_CREDITS}\n\n"
            "📌 Admin Commands:\n\n"
            "/setmode <mode>\n"
            "/broadcast <msg>\n"
            "/stats\n"
            "/addcredits <uid> <amount>\n"
            "/removecredits <uid> <amount>\n"
            "/setcredits <uid> <amount>\n"
            "/checkbalance <uid>\n"
            "/setstartcredits <amount>\n"
            "/setrefercredits <amount>\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        return

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


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /broadcast <message>")
        return
    message = " ".join(context.args)
    success = failed = 0
    for u in users.find({}, {"user_id": 1}):
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
    total_users   = users.count_documents({})
    total_credits = sum(u["credits"] for u in users.find({}, {"credits": 1}))
    await update.message.reply_text(
        f"📊 Bot Statistics\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Total Users: {total_users}\n"
        f"💰 Total Credits: {total_credits}\n"
        f"🔧 Mode: {MODE}\n"
        f"🎁 Start Credits: {START_CREDITS}\n"
        f"🔗 Refer Credits: {REFER_CREDITS}"
    )


async def addcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("📌 Usage: /addcredits <user_id> <amount>")
        return
    new_bal = update_credits(int(context.args[0]), int(context.args[1]))
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
    new_bal = update_credits(int(context.args[0]), -int(context.args[1]))
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
    success = set_credits(int(context.args[0]), int(context.args[1]))
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
    user = get_user(int(context.args[0]))
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
    app.add_handler(CommandHandler("setmode",         setmode))
    app.add_handler(CommandHandler("broadcast",       broadcast))
    app.add_handler(CommandHandler("stats",           stats))
    app.add_handler(CommandHandler("addcredits",      addcredits))
    app.add_handler(CommandHandler("removecredits",   removecredits))
    app.add_handler(CommandHandler("setcredits",      setcredits))
    app.add_handler(CommandHandler("checkbalance",    checkbalance))
    app.add_handler(CommandHandler("setstartcredits", setstartcredits))
    app.add_handler(CommandHandler("setrefercredits", setrefercredits))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    print("Bot is running...")
    app.run_polling()
