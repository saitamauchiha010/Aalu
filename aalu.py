import requests
import json
import random
import string
import certifi
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import BadRequest

# ══════════════════════════════════════════════
#               CONFIGURATION
# ══════════════════════════════════════════════

API_URL        = "num.zvx.workers.dev/?key=DxD&mobile={}"
API_URL2       = "https://telegram-to-num-gray.vercel.app/sms?key=Demo&term={}"
VEHICLE_API    = "https://vehicle-15l4.onrender.com//lookup?rc={}"
BOT_TOKEN      = "8745436475:AAEzTsfWTMo7KuUdVIcLwM5lwa3KVqWhILQ"
BOT_USERNAME   = "DeepTraceRobot"
CUSTOM_NAME    = "@ROLEX_SIR009 & @Darkdon01 & @DarkGalaxxyy & @R4HULxTRUSTED"
ADMIN_ID       = 6131370190
MONGO_URI      = "mongodb+srv://saitamauchiha01025_db_user:yMvHQKjjRpFsgDxz@cluster0.fomymln.mongodb.net/?appName=Cluster0"
UPI_ID         = "DarkGalaxxyy@naviaxis"
UPI_QR_LINK    = "https://t.me/jaiwkwkwkkwkwkjwkq/2"
PAYOUT_CHANNEL = -1003579822719

START_CREDITS      = 2
REFER_CREDITS      = 3
DEDUCTION_CREDITS  = 1
MODE               = "dual"
UNLIMITED_MODE     = False

REFERRAL_COMMISSION_PERCENT = 15  # % of purchase amount given as commission
MIN_WITHDRAW = 15  # minimum ₹ to withdraw

FORCE_CHANNEL_USERNAME = "siee1234"
FORCE_CHANNEL_LINK     = "https://t.me/siee1234"
FORCE_GROUP1_LINK      = "https://t.me/+QmnlbCK1x045MzZl"
FORCE_GROUP2_ID        = -1003416250413
FORCE_GROUP2_LINK      = "https://t.me/+cePuY51FkgE5MzY1"

# Payment preset amounts (credit: amount)
PRESET_PAYMENTS = {
    "10": 10,    # ₹10 → 10 credits
    "25": 30,    # ₹25 → 30 credits
    "50": 65,    # ₹50 → 65 credits
}
MIN_CUSTOM_AMOUNT = 5

# Indian timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# ══════════════════════════════════════════════
#               MONGODB
# ══════════════════════════════════════════════

client   = AsyncIOMotorClient(MONGO_URI, tls=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=10000)
db       = client["numbot"]
users    = db["users"]
vouchers = db["vouchers"]
orders   = db["orders"]
admins   = db["admins"]
adminlogs = db["adminlogs"]

# ══════════════════════════════════════════════
#               DATA MANAGEMENT
# ══════════════════════════════════════════════

async def get_user(user_id):
    return await users.find_one({"user_id": user_id})

async def create_user(user_id, referred_by=None, username=None, name=None, force_joined=False):
    ref_code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    user = {
        "user_id"         : user_id,
        "credits"         : START_CREDITS if force_joined else 0,
        "joined"          : datetime.now(IST).strftime("%Y-%m-%d"),
        "ref_code"        : ref_code,
        "referred_by"     : referred_by,
        "referrals"       : 0,
        "username"        : username,
        "name"            : name,
        "banned"          : False,
        "banned_at"       : None,
        "force_joined"    : force_joined,
        "earned_commission": 0,
        "withdrawn"       : 0
    }
    await users.insert_one(user)
    if referred_by and force_joined:
        await users.update_one({"user_id": referred_by}, {"$inc": {"credits": REFER_CREDITS, "referrals": 1}})
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

# ══════════════════════════════════════════════
#               ADMIN HELPERS & LOGGING
# ══════════════════════════════════════════════

async def is_admin(user_id):
    if user_id == ADMIN_ID:
        return True
    return await admins.find_one({"user_id": user_id}) is not None

async def log_admin_action(admin_id, action, target=None, details=None):
    await adminlogs.insert_one({
        "admin_id" : admin_id,
        "action"   : action,
        "target"   : target,
        "details"  : details,
        "time"     : datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    })

# ══════════════════════════════════════════════
#               KEYBOARDS
# ══════════════════════════════════════════════

def get_main_keyboard(user_id, is_admin_user=False):
    if is_admin_user:
        keyboard = [
            [KeyboardButton("🔍 Search Number"),   KeyboardButton("🔎 Search TG Number")],
            [KeyboardButton("🚗 Vehicle Search"),   KeyboardButton("👤 My Account")],
            [KeyboardButton("💰 Credits"),          KeyboardButton("🔗 Refer")],
            [KeyboardButton("💳 Buy Credits"),      KeyboardButton("❓ Help")],
            [KeyboardButton("⚙️ Admin Panel")],
        ]
    else:
        keyboard = [
            [KeyboardButton("🔍 Search Number"),   KeyboardButton("🔎 Search TG Number")],
            [KeyboardButton("🚗 Vehicle Search"),   KeyboardButton("👤 My Account")],
            [KeyboardButton("💰 Credits"),          KeyboardButton("🔗 Refer")],
            [KeyboardButton("💳 Buy Credits"),      KeyboardButton("❓ Help")],
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ══════════════════════════════════════════════
#               MEMBERSHIP CHECK
# ══════════════════════════════════════════════

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

def join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=FORCE_CHANNEL_LINK)],
        [InlineKeyboardButton("👥 Join Group 1", url=FORCE_GROUP1_LINK)],
        [InlineKeyboardButton("👥 Join Group 2", url=FORCE_GROUP2_LINK)],
    ])

# ══════════════════════════════════════════════
#               START
# ══════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    username = update.effective_user.username
    name     = update.effective_user.full_name
    bot      = context.bot

    referred_by = None
    if context.args and context.args[0].startswith("ref_"):
        ref_code = context.args[0][4:]
        referrer = await users.find_one({"ref_code": ref_code})
        if referrer and referrer["user_id"] != user_id:
            referred_by = referrer["user_id"]

    user = await get_user(user_id)
    if user is None:
        user = await create_user(user_id, referred_by, username, name, force_joined=False)
    else:
        await users.update_one({"user_id": user_id}, {"$set": {"username": username, "name": name}})

    if user.get("banned"):
        await update.message.reply_text(
            "<b>🚫 Access Denied</b>\n\nYou have been banned from using this bot.\nContact @DarkGalaxxyy for support.",
            parse_mode="HTML"
        )
        return

    joined = await force_join_check(bot, user_id)
    if not joined:
        await update.message.reply_text(
            "╔══════════════════════╗\n"
            "        🔐 <b>ACCESS RESTRICTED</b>\n"
            "╚══════════════════════╝\n\n"
            "To use this bot, you must join\n"
            "all of the following:\n\n"
            "📢 Official Channel\n"
            "👥 Group 1  •  👥 Group 2\n\n"
            "After joining, send /start again ↩️",
            parse_mode="HTML",
            reply_markup=join_keyboard()
        )
        return

    if not user.get("force_joined"):
        final_referred_by = referred_by or user.get("referred_by")
        await users.update_one(
            {"user_id": user_id},
            {"$set": {"force_joined": True}, "$inc": {"credits": START_CREDITS}}
        )
        if final_referred_by and final_referred_by != user_id:
            await users.update_one({"user_id": final_referred_by}, {"$inc": {"credits": REFER_CREDITS, "referrals": 1}})
        is_new = True
        user   = await get_user(user_id)
    else:
        is_new = False

    links_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Channel", url=FORCE_CHANNEL_LINK),
         InlineKeyboardButton("👥 Group 1", url=FORCE_GROUP1_LINK)],
        [InlineKeyboardButton("👥 Group 2", url=FORCE_GROUP2_LINK)],
    ])

    welcome_msg = (
        f"🎊 <b>Welcome aboard, {name}!</b>\n\n"
        f"🎁 You've received <b>{START_CREDITS} free credits</b> to get started!\n\n"
    ) if is_new else f"👋 <b>Welcome back, {name}!</b>\n\n"

    unlimited_note = "♾️ <b>Unlimited Mode is ON</b> — searches are free!\n\n" if UNLIMITED_MODE else ""

    msg = (
        f"{welcome_msg}{unlimited_note}"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔍 <b>DeepTrace</b> — Fetch detailed info\n"
        "about any mobile number instantly.\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 <b>Available APIs & Commands</b>\n\n"
        "<code>/num &lt;number&gt;</code> — Mobile Number Info (API 1)\n"
        "<code>/tgnum &lt;number&gt;</code> — Telegram UID Lookup (API 2)\n"
        "<code>/vehicle &lt;reg_no&gt;</code> — Vehicle Registration Info 🚗\n"
        "<code>/referstat</code> — Refer leaderboard\n"
        "<code>/redeem &lt;code&gt;</code> — Redeem voucher\n\n"
        "💡 Use the buttons below to navigate."
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=links_kb)
    user_is_admin = await is_admin(user_id)
    await update.message.reply_text("🗂 <b>Main Menu</b>", parse_mode="HTML", reply_markup=get_main_keyboard(user_id, is_admin_user=user_is_admin))

# ── Helper: insufficient credits inline keyboard ──
def insufficient_credits_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Buy Credits", callback_data="credits_buy"),
         InlineKeyboardButton("🔗 Refer", callback_data="credits_refer")]
    ])

# ══════════════════════════════════════════════
#               PROCESS NUMBER (SHARED)
# ══════════════════════════════════════════════

async def process_number(update, context, number, api_num=1):
    user_id   = update.effective_user.id
    chat_type = update.effective_chat.type
    bot       = context.bot

    if MODE == "maintenance":
        await update.message.reply_text("<b>🔧 Maintenance Mode</b>\n\nBot is under maintenance. Please try again later.", parse_mode="HTML")
        return
    if MODE == "group" and chat_type == "private":
        await update.message.reply_text("⚠️ This bot only works in groups.")
        return
    if MODE == "private" and chat_type in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ This bot only works in private chat.")
        return

    joined = await force_join_check(bot, user_id)
    if not joined:
        await update.message.reply_text("⚠️ <b>Access Restricted</b>\n\nJoin all required channels first.", parse_mode="HTML", reply_markup=join_keyboard())
        return

    user = await get_user(user_id)
    if user is None:
        user = await create_user(user_id)

    if user.get("banned"):
        await update.message.reply_text("🚫 You have been banned from using this bot.")
        return

    if not UNLIMITED_MODE and user["credits"] <= 0:
        zero_msg = (
            "❌ <b>Insufficient Credits</b>\n\n"
            "You have <b>0 credits</b> remaining.\n\n"
            "💡 <b>Ways to earn credits:</b>\n"
            "• Refer friends → 🔗 Refer button\n"
            "• Redeem a voucher → <code>/redeem</code>\n"
            "• Purchase credits → 💳 Buy Credits\n\n"
            "Use the buttons below:"
        )
        await update.message.reply_text(zero_msg, parse_mode="HTML", reply_markup=insufficient_credits_kb())
        return

    try:
        if api_num == 1:
            url = API_URL.format(number)
            if not url.startswith("http"):
                url = "https://" + url
        else:
            url = API_URL2.format(number)

        response = requests.get(url, timeout=10)
        result   = response.text.strip()

        if not result:
            await update.message.reply_text("❌ <b>No Result Found</b>\n\nNo data available for this number.", parse_mode="HTML")
            return

        deduct_credits = True
        try:
            data = json.loads(result)
            if api_num == 2:
                # --- NEW START (add this block) ---
                if data.get("status") == False and "Daily limit exceeded" in data.get("error", ""):
                    await update.message.reply_text(
                        "❌ *TG API Limit Reached*\n\nDaily limit exceeded. Please try again later.\n_No credits deducted._",
                        parse_mode="Markdown"
                    )
                    return
                # --- NEW END ---
            
                # Also handle result.error for wait or not found
                r = data.get("result", {})
                if r.get("status") == False:
                    err = r.get("error", "") or r.get("msg", "")
                    if "not found" in err.lower() or "wait" in err.lower():
                        await update.message.reply_text(f"❌ <b>TG Lookup Failed</b>\n\n{err}\n\n<i>No credits deducted.</i>", parse_mode="HTML")
                        return
            if api_num == 1 and (not data.get("success", True) or "No Record" in str(data)):
                await update.message.reply_text("❌ <b>No Result Found</b>\n\nNo data available for this number.", parse_mode="HTML")
                return

            if deduct_credits:
                if UNLIMITED_MODE:
                    credit_note = "♾️ <i>Unlimited Mode — no credits deducted</i>"
                else:
                    new_balance = await update_credits(user_id, -DEDUCTION_CREDITS)
                    credit_note = f"💰 <i>Credits remaining: {new_balance}</i>"

                if "Api_BY" in data:
                    data["Api_BY"] = CUSTOM_NAME
                pretty = json.dumps(data, indent=2, ensure_ascii=False)
                await update.message.reply_text(f"<pre>{pretty}</pre>\n\n{credit_note}", parse_mode="HTML")
        except json.JSONDecodeError:
            if deduct_credits:
                if not UNLIMITED_MODE:
                    new_balance = await update_credits(user_id, -DEDUCTION_CREDITS)
                    credit_note = f"💰 <i>Credits remaining: {new_balance}</i>"
                else:
                    credit_note = "♾️ <i>Unlimited Mode ON</i>"
                await update.message.reply_text(f"{result}\n\n{credit_note}", parse_mode="HTML")
            else:
                await update.message.reply_text(f"{result}\n\n<i>No credits deducted.</i>", parse_mode="HTML")

    except requests.exceptions.Timeout:
        await update.message.reply_text("⏱ <b>Request Timed Out</b>\n\nPlease try again.", parse_mode="HTML")
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("📡 <b>Connection Error</b>\n\nUnable to connect to the API.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📌 <b>Usage:</b> <code>/num &lt;number&gt;</code>\n\n<b>Example:</b> <code>/num 9876543210</code>", parse_mode="HTML")
        return
    await process_number(update, context, context.args[0], api_num=1)

async def tgnum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📌 <b>Usage:</b> <code>/tgnum &lt;number&gt;</code>\n\n<b>Example:</b> <code>/tgnum 6116352810</code>", parse_mode="HTML")
        return
    await process_number(update, context, context.args[0], api_num=2)

# ══════════════════════════════════════════════
#               VEHICLE SEARCH
# ══════════════════════════════════════════════

async def process_vehicle(update, context, rc_number):
    user_id   = update.effective_user.id
    chat_type = update.effective_chat.type
    bot       = context.bot

    if MODE == "maintenance":
        await update.message.reply_text("<b>🔧 Maintenance Mode</b>\n\nBot is under maintenance. Please try again later.", parse_mode="HTML")
        return
    if MODE == "group" and chat_type == "private":
        await update.message.reply_text("⚠️ This bot only works in groups.")
        return
    if MODE == "private" and chat_type in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ This bot only works in private chat.")
        return

    joined = await force_join_check(bot, user_id)
    if not joined:
        await update.message.reply_text("⚠️ <b>Access Restricted</b>\n\nJoin all required channels first.", parse_mode="HTML", reply_markup=join_keyboard())
        return

    user = await get_user(user_id)
    if user is None:
        user = await create_user(user_id)

    if user.get("banned"):
        await update.message.reply_text("🚫 You have been banned from using this bot.")
        return

    if not UNLIMITED_MODE and user["credits"] <= 0:
        zero_msg = (
            "❌ <b>Insufficient Credits</b>\n\n"
            "You have <b>0 credits</b> remaining.\n\n"
            "💡 <b>Ways to earn credits:</b>\n"
            "• Refer friends → 🔗 Refer button\n"
            "• Redeem a voucher → <code>/redeem</code>\n"
            "• Purchase credits → 💳 Buy Credits\n\n"
            "Use the buttons below:"
        )
        await update.message.reply_text(zero_msg, parse_mode="HTML", reply_markup=insufficient_credits_kb())
        return

    try:
        url      = VEHICLE_API.format(rc_number.upper())
        response = requests.get(url, timeout=15)
        data     = response.json()

        values = [v for k, v in data.items() if k != "copyright"]
        non_null = [v for v in values if v not in (None, "NA", "")]

        if not non_null:
            await update.message.reply_text(
                "❌ <b>No Result Found</b>\n\nNo data available for this vehicle number.",
                parse_mode="HTML"
            )
            return

        if UNLIMITED_MODE:
            credit_note = "♾️ <i>Unlimited Mode — no credits deducted</i>"
        else:
            new_balance = await update_credits(user_id, -DEDUCTION_CREDITS)
            credit_note = f"💰 <i>Credits remaining: {new_balance}</i>"

        pretty = json.dumps(data, indent=2, ensure_ascii=False)
        await update.message.reply_text(f"<pre>{pretty}</pre>\n\n{credit_note}", parse_mode="HTML")

    except requests.exceptions.Timeout:
        await update.message.reply_text("⏱ <b>Request Timed Out</b>\n\nPlease try again.", parse_mode="HTML")
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("📡 <b>Connection Error</b>\n\nUnable to connect to the API.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📌 <b>Usage:</b>\n<code>/vehicle &lt;vehicle number&gt;</code>\n\n<b>Example:</b>\n<code>/vehicle UP78AB1234</code>",
            parse_mode="HTML"
        )
        return
    await process_vehicle(update, context, context.args[0])

# ══════════════════════════════════════════════
#               /id COMMAND (ADMIN ONLY)
# ══════════════════════════════════════════════

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Admin only command.")
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /id @username")
        return
    username = context.args[0].lstrip('@')
    try:
        chat = await context.bot.get_chat(f"@{username}")
        await update.message.reply_text(
            f"🆔 <b>User ID for @{username}:</b> <code>{chat.id}</code>\n"
            f"👤 Name: {chat.full_name or 'N/A'}",
            parse_mode="HTML"
        )
    except BadRequest as e:
        await update.message.reply_text(f"❌ Error: {e.message}", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to get ID: {str(e)}")

# ══════════════════════════════════════════════
#               BAN / UNBAN / BANLIST
# ══════════════════════════════════════════════

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /ban <user_id>")
        return
    uid    = int(context.args[0])
    result = await users.update_one({"user_id": uid}, {"$set": {"banned": True, "banned_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")}})
    if result.modified_count:
        await log_admin_action(update.effective_user.id, "ban", uid, f"Banned user {uid}")
        await update.message.reply_text(f"🚫 User <code>{uid}</code> has been banned.", parse_mode="HTML")
        try:
            await context.bot.send_message(chat_id=uid, text="🚫 You have been banned from this bot.\nContact @DarkGalaxxyy for support.")
        except Exception:
            pass
    else:
        await update.message.reply_text("❌ User not found.")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /unban <user_id>")
        return
    uid    = int(context.args[0])
    result = await users.update_one({"user_id": uid}, {"$set": {"banned": False, "banned_at": None}})
    if result.modified_count:
        await log_admin_action(update.effective_user.id, "unban", uid, f"Unbanned user {uid}")
        await update.message.reply_text(f"✅ User <code>{uid}</code> has been unbanned.", parse_mode="HTML")
        try:
            await context.bot.send_message(chat_id=uid, text="✅ You have been unbanned!\nYou can now use the bot again.")
        except Exception:
            pass
    else:
        await update.message.reply_text("❌ User not found.")

async def banusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    banned_users = await users.find({"banned": True}).to_list(length=100)
    if not banned_users:
        await update.message.reply_text("✅ No banned users found.")
        return
    msg = "🚫 <b>Banned Users List</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for u in banned_users:
        name = u.get("name") or f"User {u['user_id']}"
        ban_date = u.get("banned_at") or "Unknown"
        msg += f'🆔 <a href="tg://user?id={u["user_id"]}">{name}</a> (ID: <code>{u["user_id"]}</code>)\n📅 Banned: {ban_date}\n\n'
    await update.message.reply_text(msg, parse_mode="HTML")

# ══════════════════════════════════════════════
#               CHECK USER
# ══════════════════════════════════════════════

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /check <user_id>")
        return
    uid  = int(context.args[0])
    user = await get_user(uid)
    if not user:
        await update.message.reply_text("❌ User not found.")
        return

    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user['ref_code']}"
    uname    = f"@{user['username']}" if user.get("username") else "No username"
    name     = user.get("name") or "Unknown"
    banned   = "Yes 🚫" if user.get("banned") else "No ✅"
    fj       = "Yes ✅" if user.get("force_joined") else "No ❌"
    ref_by   = user.get("referred_by")
    if ref_by:
        ref_user = await get_user(ref_by)
        ref_name = f'<a href="tg://user?id={ref_user["user_id"]}">{ref_user.get("name") or "Unknown"}</a>' if ref_user else "Unknown"
        ref_text = ref_name
    else:
        ref_text = "None"

    referred_users = await users.find(
        {"referred_by": uid}, {"username": 1, "user_id": 1, "name": 1}
    ).to_list(length=100)

    refer_list = ""
    for r in referred_users:
        rname = r.get("name") or f"User {r['user_id']}"
        refer_list += f'  • <a href="tg://user?id={r["user_id"]}">{rname}</a>\n'

    msg = (
        "👤 <b>User Details</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Name: <a href='tg://user?id={uid}'>{name}</a>\n"
        f"🔖 Username: {uname}\n"
        f"🆔 User ID: <code>{uid}</code>\n"
        f"💰 Credits: {user['credits']}\n"
        f"💸 Earned Commission: ₹{user.get('earned_commission', 0)}\n"
        f"🏧 Withdrawn: ₹{user.get('withdrawn', 0)}\n"
        f"📅 Joined: {user['joined']}\n"
        f"👥 Referrals: {user['referrals']}\n"
        f"🔗 Referred By: {ref_text}\n"
        f"✅ Force Joined: {fj}\n"
        f"🚫 Banned: {banned}\n"
        f"🔗 <a href='{ref_link}'>Refer Link</a>\n"
    )
    if refer_list:
        msg += f"\n👥 <b>Referred Users:</b>\n{refer_list}"
    else:
        msg += "\n👥 Referred Users: None"

    await update.message.reply_text(msg, parse_mode="HTML")

# ══════════════════════════════════════════════
#               MSG USER
# ══════════════════════════════════════════════

async def msg_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("📌 Usage: /msg <user_id> <message>")
        return
    uid     = int(context.args[0])
    message = " ".join(context.args[1:])
    user    = await get_user(uid)
    if not user:
        await update.message.reply_text("❌ User not found.")
        return
    try:
        await context.bot.send_message(chat_id=uid, text=message)
        uname = f"@{user['username']}" if user.get("username") else user.get("name") or str(uid)
        await update.message.reply_text(f"✅ Message sent to {uname} (<code>{uid}</code>)", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {str(e)}")

# ══════════════════════════════════════════════
#               REFER LIST
# ══════════════════════════════════════════════

async def referlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    all_users = await users.find(
        {"referrals": {"$gt": 0}, "user_id": {"$ne": ADMIN_ID}},
        {"username": 1, "user_id": 1, "referrals": 1, "name": 1}
    ).sort("referrals", -1).to_list(length=100)

    if not all_users:
        await update.message.reply_text("No referrals found.")
        return

    msg = "📋 <b>Full Refer List</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, u in enumerate(all_users, 1):
        name = u.get("name") or f"User {u['user_id']}"
        msg += f'{i}. <a href="tg://user?id={u["user_id"]}">{name}</a> — {u["referrals"]} refers\n'
    msg += "\n━━━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(msg, parse_mode="HTML")

# ══════════════════════════════════════════════
#               REFER LEADERBOARD
# ══════════════════════════════════════════════

async def referstat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = await users.find(
        {"referrals": {"$gt": 0}, "user_id": {"$ne": ADMIN_ID}},
        {"username": 1, "user_id": 1, "referrals": 1, "name": 1}
    ).sort("referrals", -1).to_list(length=500)

    if not top_users:
        await update.message.reply_text("🔗 No referrals yet! Be the first to refer.")
        return

    medals = ["🥇", "🥈", "🥉"]
    msg = "🏆 <b>Refer Leaderboard</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, u in enumerate(top_users):
        medal = medals[i] if i < 3 else f"{i+1}."
        name  = u.get("name") or f"User {u['user_id']}"
        msg  += f'{medal} <a href="tg://user?id={u["user_id"]}">{name}</a> — <b>{u["referrals"]}</b> refers\n'
    msg += "\n━━━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(msg, parse_mode="HTML")

# ══════════════════════════════════════════════
#               VOUCHER SYSTEM
# ══════════════════════════════════════════════

async def createvoucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 3:
        await update.message.reply_text("📌 Usage: /createvoucher <code> <credits> <max_uses>")
        return
    code     = context.args[0].upper()
    credits  = int(context.args[1])
    max_uses = int(context.args[2])
    if await vouchers.find_one({"code": code}):
        await update.message.reply_text(f"❌ Voucher <code>{code}</code> already exists.", parse_mode="HTML")
        return
    await vouchers.insert_one({"code": code, "credits": credits, "max_uses": max_uses, "uses": 0, "used_by": []})
    await log_admin_action(update.effective_user.id, "createvoucher", None, f"Created voucher {code} with {credits} credits, {max_uses} uses")
    await update.message.reply_text(
        f"🎟️ <b>Voucher Created!</b>\n\n📌 Code: <code>{code}</code>\n💰 Credits: {credits}\n👥 Max Uses: {max_uses}",
        parse_mode="HTML"
    )

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot     = context.bot

    joined = await force_join_check(bot, user_id)
    if not joined:
        await update.message.reply_text("⚠️ Please join all required channels/groups before redeeming.", reply_markup=join_keyboard())
        return

    if not context.args:
        await update.message.reply_text("📌 Usage: /redeem <code>")
        return
    code    = context.args[0].upper()
    voucher = await vouchers.find_one({"code": code})
    if not voucher:
        await update.message.reply_text("❌ Invalid voucher code.")
        return
    if voucher["uses"] >= voucher["max_uses"]:
        await update.message.reply_text("❌ This voucher has expired.")
        return
    if user_id in voucher["used_by"]:
        await update.message.reply_text("❌ You have already redeemed this voucher.")
        return
    await vouchers.update_one({"code": code}, {"$inc": {"uses": 1}, "$push": {"used_by": user_id}})
    new_balance = await update_credits(user_id, voucher["credits"])
    await update.message.reply_text(
        f"🎉 <b>Voucher Redeemed!</b>\n\n💰 Credits Added: <b>{voucher['credits']}</b>\n💳 New Balance: <b>{new_balance}</b> credits",
        parse_mode="HTML"
    )

async def deletevoucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /deletevoucher <code>")
        return
    code   = context.args[0].upper()
    result = await vouchers.delete_one({"code": code})
    if result.deleted_count:
        await log_admin_action(update.effective_user.id, "deletevoucher", None, f"Deleted voucher {code}")
    await update.message.reply_text(
        f"✅ Voucher <code>{code}</code> deleted." if result.deleted_count else f"❌ Voucher <code>{code}</code> not found.",
        parse_mode="HTML"
    )

async def listvouchers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    all_vouchers = await vouchers.find({}).to_list(length=50)
    if not all_vouchers:
        await update.message.reply_text("No vouchers found.")
        return
    msg = "🎟️ <b>All Vouchers</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for v in all_vouchers:
        msg += f"<code>{v['code']}</code> — 💰 {v['credits']} credits — 👥 {v['uses']}/{v['max_uses']} used\n"
    await update.message.reply_text(msg, parse_mode="HTML")

# ══════════════════════════════════════════════
#               BUY CREDITS - UPI
# ══════════════════════════════════════════════

async def buy_credits_menu(update, context):
    keyboard = [
        [InlineKeyboardButton(f"₹10 → 10 Credits", callback_data="buy_preset_10")],
        [InlineKeyboardButton(f"₹25 → 30 Credits", callback_data="buy_preset_25")],
        [InlineKeyboardButton(f"₹50 → 65 Credits", callback_data="buy_preset_50")],
        [InlineKeyboardButton("💰 Custom Amount", callback_data="buy_custom")],
    ]
    await update.message.reply_text(
        "💳 <b>Buy Credits</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💵 <b>Select an option:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "✨ <b>Bonus on higher packs!</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def process_payment(update, query, amount, credits):
    user_id = query.from_user.id
    order_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    await orders.insert_one({
        "order_id": order_id,
        "user_id" : user_id,
        "amount"  : amount,
        "credits" : credits,
        "status"  : "pending",
        "type"    : "buy",
        "created" : datetime.now(IST).strftime("%Y-%m-%d %H:%M")
    })
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Paid", callback_data=f"paid_{order_id}")],
        [InlineKeyboardButton("❌ Cancel",    callback_data="cancel_payment")],
        [InlineKeyboardButton("🔙 Back",      callback_data="buy_menu_back")]
    ])
    await query.message.delete()
    await query.message.reply_photo(
        photo=UPI_QR_LINK,
        caption=(
            f"📱 <b>UPI Payment</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Amount: ₹{amount}\n"
            f"💰 Credits: {credits}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏦 UPI ID: <code>{UPI_ID}</code>\n\n"
            f"<i>Scan QR or use UPI ID to pay</i>\n"
            f"Then tap ✅ I've Paid below.\n\n"
            f"🔖 Order ID: <code>{order_id}</code>"
        ),
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ══════════════════════════════════════════════
#               CALLBACKS
# ══════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    data    = query.data
    user_id = query.from_user.id
    await query.answer()

    # ── Buy Preset or Custom ──
    if data.startswith("buy_preset_"):
        preset_key = data.split("_")[2]
        if preset_key not in PRESET_PAYMENTS:
            await query.answer("Invalid option.", show_alert=True)
            return
        amount = int(preset_key)
        credits = PRESET_PAYMENTS[preset_key]
        await process_payment(update, query, amount, credits)
        return

    if data == "buy_custom":
        context.user_data["upi_custom"] = True
        await query.message.edit_text(
            "💰 <b>Custom Amount</b>\n\n"
            "Please enter the amount you want to pay (in ₹):\n"
            f"<i>Minimum amount: ₹{MIN_CUSTOM_AMOUNT}</i>\n\n"
            "Example: <code>50</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]])
        )
        return

    # ── Credits menu inline buttons ──
    elif data == "credits_refer":
        # Now show the same refer message as main menu "Refer" button (with withdraw)
        user = await get_user(user_id) or await create_user(user_id)
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user['ref_code']}"
        msg = (
            "🔗 <b>Refer & Earn</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔗 Your Link:\n<code>{ref_link}</code>\n\n"
            f"💰 Reward: <b>{REFER_CREDITS} credits</b> per refer\n"
            f"👥 Total Referrals: <b>{user['referrals']}</b>\n"
            f"💸 Earned Commission: ₹{user.get('earned_commission', 0)}\n"
            f"🏧 Minimum Withdraw: ₹{MIN_WITHDRAW}\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 Withdraw Commission", callback_data="withdraw_start")]
        ])
        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=kb)
        await query.answer()
        return

    elif data == "credits_buy":
        await buy_credits_menu(query, context)
        await query.answer()
        return

    # ── Withdraw callbacks ──
    elif data == "withdraw_start":
        user = await get_user(user_id)
        if not user:
            await query.answer("Account not found.", show_alert=True)
            return
        if user.get("earned_commission", 0) < MIN_WITHDRAW:
            await query.answer(f"Minimum withdrawal is ₹{MIN_WITHDRAW}. Your balance is ₹{user.get('earned_commission', 0)}.", show_alert=True)
            return
        context.user_data["withdraw_step"] = "amount"
        await query.message.reply_text(
            f"💸 <b>Withdraw Commission</b>\n\n"
            f"Your earned commission: ₹{user.get('earned_commission', 0)}\n"
            f"Minimum withdraw: ₹{MIN_WITHDRAW}\n\n"
            "Please enter the amount you want to withdraw (₹):",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]])
        )
        await query.answer()
        return

    elif data == "cancel_withdraw":
        for k in ("withdraw_step", "withdraw_amount", "withdraw_bank_name", "withdraw_account_name", "withdraw_upi"):
            context.user_data.pop(k, None)
        try:
            await query.message.edit_text("❌ Withdrawal cancelled.", reply_markup=None)
        except:
            pass
        await query.answer()
        return

    # ── Back to buy menu from payment screen ──
    elif data == "buy_menu_back":
        await query.message.delete()
        await buy_credits_menu(query, context)
        return

    # ── Cancel Search ──
    elif data == "cancel_search":
        context.user_data.pop("waiting_for_number", None)
        context.user_data.pop("waiting_for_vehicle", None)
        try:
            await query.message.edit_text("❌ <b>Search cancelled.</b>", parse_mode="HTML", reply_markup=None)
        except Exception:
            pass

    # ── Cancel Payment ──
    elif data == "cancel_payment":
        context.user_data.pop("upi_custom", None)
        try:
            await query.message.edit_text("❌ <b>Payment Cancelled</b>\n\nNo charges were made.", parse_mode="HTML", reply_markup=None)
        except Exception:
            try:
                await query.message.edit_caption("❌ <b>Payment Cancelled</b>\n\nNo charges were made.", parse_mode="HTML", reply_markup=None)
            except Exception:
                pass

    # ── I've Paid ──
    elif data.startswith("paid_"):
        order_id = data.split("_", 1)[1]
        order    = await orders.find_one({"order_id": order_id})
        if not order:
            await query.answer("❌ Order not found.", show_alert=True)
            return
        if order.get("submitted"):
            await query.answer("⚠️ Already submitted!", show_alert=True)
            return
        await orders.update_one({"order_id": order_id}, {"$set": {"submitted": True}})
        username = query.from_user.username
        name     = query.from_user.full_name
        amount   = order["amount"]
        credits  = order["credits"]
        uname    = f"@{username}" if username else name or f"User {user_id}"

        payout_msg = (
            "💳 <b>New Payment Order</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📛 Name: {name}\n"
            f"👤 Username: {uname}\n"
            f"🆔 User ID: <code>{user_id}</code>\n"
            f"💵 Amount: ₹{amount}\n"
            f"💰 Credits: {credits}\n"
            f"📊 Status: Pending ⏳\n\n"
            f"🔖 Order ID: <code>{order_id}</code>"
        )
        payout_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Mark as Done",  callback_data=f"done_{order_id}_{user_id}_{credits}"),
                InlineKeyboardButton("❌ Cancel Order",  callback_data=f"cancelorder_{order_id}_{user_id}")
            ]
        ])
        try:
            await context.bot.send_message(chat_id=PAYOUT_CHANNEL, text=payout_msg, parse_mode="HTML", reply_markup=payout_kb)
        except Exception as e:
            await query.answer(f"❌ Failed to send to payout channel: {str(e)}", show_alert=True)
            await orders.update_one({"order_id": order_id}, {"$set": {"submitted": False}})
            return

        success_text = (
            "✅ <b>Payment Request Submitted!</b>\n\n"
            f"Your order ID: <code>{order_id}</code>\n"
            "Your credits will be added after verification.\n"
            "<i>Usually within a few minutes.</i>"
        )
        try:
            await query.message.edit_caption(success_text, parse_mode="HTML", reply_markup=None)
        except Exception:
            try:
                await query.message.edit_text(success_text, parse_mode="HTML", reply_markup=None)
            except Exception:
                await query.answer("✅ Payment submitted!", show_alert=True)

    # ── Mark as Done (Buy) ──
    elif data.startswith("done_"):
        parts    = data.split("_")
        order_id = parts[1]
        uid      = int(parts[2])
        credits  = int(parts[3])
        await update_credits(uid, credits)
        await orders.update_one({"order_id": order_id}, {"$set": {"status": "done"}})
        order = await orders.find_one({"order_id": order_id})
        if order and order.get("type", "buy") == "buy":
            buyer = await get_user(uid)
            if buyer and buyer.get("referred_by"):
                ref_uid = buyer["referred_by"]
                commission = int(order["amount"] * REFERRAL_COMMISSION_PERCENT / 100)
                if commission > 0:
                    await users.update_one({"user_id": ref_uid}, {"$inc": {"earned_commission": commission}})
                    try:
                        await context.bot.send_message(
                            chat_id=ref_uid,
                            text=(
                                f"🎉 <b>Commission Earned!</b>\n\n"
                                f"Your referral <a href='tg://user?id={uid}'>{buyer.get('name', 'User')}</a> just purchased credits.\n"
                                f"You earned ₹{commission} commission.\n"
                                f"Total earned: ₹{ (await get_user(ref_uid))['earned_commission'] }"
                            ),
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
        new_text = query.message.text.replace("📊 Status: Pending ⏳", "📊 Status: Done ✅")
        try:
            await query.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "🎉 <b>Payment Approved!</b>\n\n"
                    f"💰 <b>{credits} credits</b> have been added to your account.\n\n"
                    "Start searching now — happy hunting! 🔍\n"
                    "<i>For any help, contact @DarkGalaxxyy</i>"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    # ── Mark Withdraw as Done ──
    elif data.startswith("withdrawdone_"):
        parts    = data.split("_")
        order_id = parts[1]
        uid      = int(parts[2])
        amount   = int(parts[3])
        await orders.update_one({"order_id": order_id}, {"$set": {"status": "done"}})
        await users.update_one({"user_id": uid}, {"$inc": {"earned_commission": -amount, "withdrawn": amount}})
        new_text = query.message.text.replace("📊 Status: Pending ⏳", "📊 Status: Done ✅")
        try:
            await query.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
        except Exception:
            pass
        order = await orders.find_one({"order_id": order_id})
        upi_id = order.get("upi_id", "N/A") if order else "N/A"
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    f"✅ <b>Withdrawal Successful!</b>\n\n"
                    f"Amount withdrawn: ₹{amount}\n"
                    f"To UPI ID: <code>{upi_id}</code>\n\n"
                    "Thank you for using DeepTrace! 🙏"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    # ── Cancel Withdraw Order ──
    elif data.startswith("cancelwithdraworder_"):
        parts    = data.split("_")
        order_id = parts[1]
        uid      = int(parts[2])
        await orders.update_one({"order_id": order_id}, {"$set": {"status": "cancelled"}})
        new_text = query.message.text.replace("📊 Status: Pending ⏳", "📊 Status: Cancelled ❌")
        try:
            await query.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "❌ <b>Withdrawal Cancelled</b>\n\n"
                    "Your withdrawal request has been cancelled.\n"
                    "If this is a mistake, contact @DarkGalaxxyy"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    # ── Cancel Order (Buy) ──
    elif data.startswith("cancelorder_"):
        parts    = data.split("_")
        order_id = parts[1]
        uid      = int(parts[2])
        await orders.update_one({"order_id": order_id}, {"$set": {"status": "cancelled"}})
        new_text = query.message.text.replace("📊 Status: Pending ⏳", "📊 Status: Cancelled ❌")
        try:
            await query.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "❌ <b>Payment Cancelled</b>\n\n"
                    "Your payment order has been cancelled.\n"
                    "If this is a mistake, contact @DarkGalaxxyy"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    # ── Refresh Stats ──
    elif data == "refresh_stats":
        if user_id != ADMIN_ID:
            return
        total_users    = await users.count_documents({})
        joined_users   = await users.count_documents({"force_joined": True})
        only_start     = total_users - joined_users
        total_credits  = sum([u["credits"] async for u in users.find({}, {"credits": 1})])
        total_vouchers = await vouchers.count_documents({})
        new_text = (
            "📊 <b>Bot Statistics</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Total Users: <b>{total_users}</b>\n"
            f"✅ Joined Users: <b>{joined_users}</b>\n"
            f"⏳ Only Started: <b>{only_start}</b>\n\n"
            f"💰 Total Credits: <b>{total_credits}</b>\n"
            f"🔧 Mode: <code>{MODE}</code>\n"
            f"♾️ Unlimited: {'ON ✅' if UNLIMITED_MODE else 'OFF ❌'}\n"
            f"🎁 Start Credits: <b>{START_CREDITS}</b>\n"
            f"🔗 Refer Credits: <b>{REFER_CREDITS}</b>\n"
            f"🎟️ Vouchers: <b>{total_vouchers}</b>\n\n"
            f"<i>Last refreshed: {datetime.now(IST).strftime('%H:%M:%S')}</i>"
        )
        refresh_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]])
        try:
            await query.message.edit_text(new_text, parse_mode="HTML", reply_markup=refresh_kb)
        except Exception:
            pass

# ══════════════════════════════════════════════
#               BUTTON HANDLERS
# ══════════════════════════════════════════════

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text    = update.message.text
    user_id = update.effective_user.id
    bot     = context.bot

    # ── Withdrawal flow steps ──
    if context.user_data.get("withdraw_step"):
        step = context.user_data["withdraw_step"]
        if step == "amount":
            if text.isdigit():
                amount = int(text)
                user = await get_user(user_id)
                if amount > user.get("earned_commission", 0) or amount < MIN_WITHDRAW:
                    await update.message.reply_text(
                        f"❌ Amount must be between ₹{MIN_WITHDRAW} and your balance ₹{user.get('earned_commission', 0)}. Try again.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]])
                    )
                    return
                context.user_data["withdraw_amount"] = amount
                context.user_data["withdraw_step"] = "bank_name"
                await update.message.reply_text("🏦 Enter your Bank Name:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]]))
            else:
                await update.message.reply_text("❌ Invalid amount. Enter a number (₹).", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]]))
            return

        elif step == "bank_name":
            context.user_data["withdraw_bank_name"] = text
            context.user_data["withdraw_step"] = "account_name"
            await update.message.reply_text("📛 Enter your Bank Account Name:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]]))
            return

        elif step == "account_name":
            context.user_data["withdraw_account_name"] = text
            context.user_data["withdraw_step"] = "upi"
            await update.message.reply_text("📱 Enter your UPI ID:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]]))
            return

        elif step == "upi":
            upi = text.strip()
            if not upi:
                await update.message.reply_text("❌ Invalid UPI ID. Try again.")
                return
            context.user_data["withdraw_upi"] = upi
            amount = context.user_data["withdraw_amount"]
            bank = context.user_data["withdraw_bank_name"]
            acc = context.user_data["withdraw_account_name"]
            msg = (
                "💸 <b>Confirm Withdrawal</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Amount: ₹{amount}\n"
                f"Bank: {bank}\n"
                f"Account Name: {acc}\n"
                f"UPI ID: <code>{upi}</code>\n\n"
                "Is this correct?"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm", callback_data="confirm_withdraw"),
                 InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]
            ])
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb)
            context.user_data.pop("withdraw_step")
            return
        return

    # ── Custom Amount Input ──
    if context.user_data.get("upi_custom"):
        if text.isdigit() and int(text) >= MIN_CUSTOM_AMOUNT:
            amount = int(text)
            credits = amount
            order_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            context.user_data.pop("upi_custom")
            await orders.insert_one({
                "order_id": order_id,
                "user_id" : user_id,
                "amount"  : amount,
                "credits" : credits,
                "status"  : "pending",
                "type"    : "buy",
                "created" : datetime.now(IST).strftime("%Y-%m-%d %H:%M")
            })
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ I've Paid", callback_data=f"paid_{order_id}")],
                [InlineKeyboardButton("❌ Cancel",    callback_data="cancel_payment")],
                [InlineKeyboardButton("🔙 Back",      callback_data="buy_menu_back")]
            ])
            await update.message.reply_photo(
                photo=UPI_QR_LINK,
                caption=(
                    f"📱 <b>UPI Payment</b>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 Amount: ₹{amount}\n"
                    f"💰 Credits: {credits}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🏦 UPI ID: <code>{UPI_ID}</code>\n\n"
                    f"<i>Scan QR or use UPI ID to pay</i>\n"
                    f"Then tap ✅ I've Paid below.\n\n"
                    f"🔖 Order ID: <code>{order_id}</code>"
                ),
                parse_mode="HTML",
                reply_markup=keyboard
            )
        elif text.isdigit() and int(text) < MIN_CUSTOM_AMOUNT:
            await update.message.reply_text(
                f"❌ Amount should be at least ₹{MIN_CUSTOM_AMOUNT}.\n\nPlease enter a valid amount:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]])
            )
        else:
            await update.message.reply_text(
                "❌ Invalid amount. Enter a number (digits only):\n"
                f"<i>Minimum ₹{MIN_CUSTOM_AMOUNT}</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]])
            )
        return

    # ── Search Number (API 1) ──
    if text == "🔍 Search Number":
        joined = await force_join_check(bot, user_id)
        if not joined:
            await update.message.reply_text("⚠️ Please join all required channels/groups first.", reply_markup=join_keyboard())
            return
        context.user_data["waiting_for_number"] = 1
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_search")]])
        await update.message.reply_text(
            "🔍 <b>Number Search — API 1</b>\n\n"
            "Please enter the number to search:\n\n"
            "⚠️ <b>Without +91</b> — digits only\n"
            "<i>Example: <code>9876543210</code></i>",
            parse_mode="HTML",
            reply_markup=cancel_kb
        )
        return

    # ── Search TG Number (TG API) ──
    if text == "🔎 Search TG Number":
        joined = await force_join_check(bot, user_id)
        if not joined:
            await update.message.reply_text("⚠️ Please join all required channels/groups first.", reply_markup=join_keyboard())
            return
        context.user_data["waiting_for_number"] = 2
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_search")]])
        await update.message.reply_text(
            "🔎 <b>Search TG Number</b>\n\n"
            "Please enter the User ID Or Target Username to search:\n\n"
            "⚠️ <b>Without space</b> — User ID or Username\n"
            "<i>Example: <code>6116093010</code></i>\n"
            "<i>Example: <code>@username</code></i>",
            parse_mode="HTML",
            reply_markup=cancel_kb
        )
        return

    # ── Vehicle Search ──
    if text == "🚗 Vehicle Search":
        joined = await force_join_check(bot, user_id)
        if not joined:
            await update.message.reply_text("⚠️ Please join all required channels/groups first.", reply_markup=join_keyboard())
            return
        context.user_data["waiting_for_vehicle"] = True
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_search")]])
        await update.message.reply_text(
            "🚗 <b>Vehicle Search</b>\n\n"
            "Please enter the Vehicle Registration Number:\n\n"
            "<i>Example: <code>UP78AB1234</code></i>",
            parse_mode="HTML",
            reply_markup=cancel_kb
        )
        return

    if context.user_data.get("waiting_for_vehicle"):
        context.user_data.pop("waiting_for_vehicle")
        rc = text.strip().upper()
        if rc:
            await process_vehicle(update, context, rc)
        else:
            await update.message.reply_text("❌ Invalid input. Enter a valid vehicle number.")
        return

    if context.user_data.get("waiting_for_number"):
        api_num = context.user_data.pop("waiting_for_number")
        clean = text.strip().lstrip("@")
        if api_num == 1:
            if text.isdigit():
                await process_number(update, context, text, api_num=1)
            else:
                await update.message.reply_text("❌ Invalid input. Enter digits only, without +91 or spaces.")
        else:
            if clean:
                await process_number(update, context, clean, api_num=2)
            else:
                await update.message.reply_text("❌ Invalid input.")
        return

    # ── My Account ──
    if text == "👤 My Account":
        user = await get_user(user_id) or await create_user(user_id)
        unlimited_note = "\n♾️ <i>Unlimited Mode ON — searches are free!</i>" if UNLIMITED_MODE else ""
        await update.message.reply_text(
            "👤 <b>My Account</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 User ID: <code>{user_id}</code>\n"
            f"💰 Credits: <b>{user['credits']}</b>{unlimited_note}\n"
            f"💸 Earned Commission: ₹{user.get('earned_commission', 0)}\n"
            f"📅 Joined: {user['joined']}\n"
            f"👥 Referrals: {user['referrals']}\n"
            "━━━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML"
        )
        return

    # ── Credits with inline buttons ──
    if text == "💰 Credits":
        user = await get_user(user_id) or await create_user(user_id)
        unlimited_note = "\n\n♾️ <i>Unlimited Mode is ON — searches are FREE!</i>" if UNLIMITED_MODE else ""
        credits_msg = (
            "💰 <b>Credits</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💳 <b>Your Balance:</b> <code>{user['credits']}</code> credits{unlimited_note}\n\n"
            f"Each search costs <b>{DEDUCTION_CREDITS} credit(s)</b>.\n\n"
            "📌 <b>How to earn credits:</b>\n\n"
            f"🎁 New users → <b>{START_CREDITS}</b> free credits\n"
            f"🔗 Refer a friend → <b>{REFER_CREDITS}</b> credits\n"
            "🎟️ Redeem voucher → <code>/redeem &lt;code&gt;</code>\n"
            "<i>(Vouchers are dropped in official channel @siee1234)</i>\n"
            "💳 Purchase → ₹1 = 1 credit\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Refer", callback_data="credits_refer"),
             InlineKeyboardButton("💳 Buy Credits", callback_data="credits_buy")]
        ])
        await update.message.reply_text(credits_msg, parse_mode="HTML", reply_markup=kb)
        return

    # ── Refer ──
    if text == "🔗 Refer":
        user     = await get_user(user_id) or await create_user(user_id)
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user['ref_code']}"
        msg = (
            "🔗 <b>Refer & Earn</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔗 Your Link:\n<code>{ref_link}</code>\n\n"
            f"💰 Reward: <b>{REFER_CREDITS} credits</b> per refer\n"
            f"👥 Total Referrals: <b>{user['referrals']}</b>\n"
            f"💸 Earned Commission: ₹{user.get('earned_commission', 0)}\n"
            f"🏧 Minimum Withdraw: ₹{MIN_WITHDRAW}\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 Withdraw Commission", callback_data="withdraw_start")]
        ])
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb)
        return

    # ── Buy Credits ──
    if text == "💳 Buy Credits":
        await buy_credits_menu(update, context)
        return

    # ── Help ──
    if text == "❓ Help":
        await update.message.reply_text(
            "❓ <b>Help & Support</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "For any queries, issues or\n"
            "to purchase credits, contact:\n\n"
            "👤 @DarkGalaxxyy\n\n"
            "<i>We typically respond within minutes.</i>\n"
            "━━━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML"
        )
        return

    # ── Admin Panel ──
    if text == "⚙️ Admin Panel":
        if not await is_admin(user_id):
            await update.message.reply_text("❌ Access Denied.")
            return
        total_users    = await users.count_documents({})
        joined_users   = await users.count_documents({"force_joined": True})
        only_start     = total_users - joined_users
        refresh_kb     = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Stats", callback_data="refresh_stats")]])

        if user_id != ADMIN_ID:
            await update.message.reply_text(
                "🛡️ <b>Admin Panel</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 Total Users: <b>{total_users}</b>\n"
                f"✅ Joined Users: <b>{joined_users}</b>\n"
                f"⏳ Only Started: <b>{only_start}</b>\n\n"
                "📌 <b>Your Commands:</b>\n\n"
                "<code>/addcredits &lt;uid&gt; &lt;amount&gt;</code>\n"
                "<code>/removecredits &lt;uid&gt; &lt;amount&gt;</code>\n"
                "<code>/setcredits &lt;uid&gt; &lt;amount&gt;</code>\n"
                "<code>/checkbalance &lt;uid&gt;</code>\n"
                "<code>/ban &lt;uid&gt;</code>\n"
                "<code>/unban &lt;uid&gt;</code>\n"
                "<code>/banusers</code>\n"
                "<code>/broadcast &lt;msg&gt;</code>\n"
                "━━━━━━━━━━━━━━━━━━━━",
                parse_mode="HTML",
                reply_markup=refresh_kb
            )
            return

        total_credits  = sum([u["credits"] async for u in users.find({}, {"credits": 1})])
        total_vouchers = await vouchers.count_documents({})
        total_admins   = await admins.count_documents({})
        await update.message.reply_text(
            "👑 <b>Owner Panel</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔧 Mode: <code>{MODE}</code>\n"
            f"♾️ Unlimited: {'ON ✅' if UNLIMITED_MODE else 'OFF ❌'}\n\n"
            f"👤 Total Users: <b>{total_users}</b>\n"
            f"✅ Joined Users: <b>{joined_users}</b>\n"
            f"⏳ Only Started: <b>{only_start}</b>\n\n"
            f"💰 Total Credits: <b>{total_credits}</b>\n"
            f"🎁 Start Credits: <b>{START_CREDITS}</b>\n"
            f"🔗 Refer Credits: <b>{REFER_CREDITS}</b>\n"
            f"💸 Search Cost: <b>{DEDUCTION_CREDITS}</b> credit(s)\n"
            f"🎟️ Vouchers: <b>{total_vouchers}</b>\n"
            f"🛡️ Admins: <b>{total_admins}</b>\n\n"
            "📌 <b>All Commands:</b>\n\n"
            "👑 <b>Owner Only:</b>\n"
            "<code>/addadmin &lt;uid&gt;</code>\n"
            "<code>/removeadmin &lt;uid&gt;</code>\n"
            "<code>/adminlist</code>\n"
            "<code>/checkadmin &lt;uid&gt;</code>\n"
            "<code>/setmode dual|group|private|maintenance</code>\n"
            "<code>/unlimited on|off</code>\n"
            "<code>/setstartcredits &lt;amount&gt;</code>\n"
            "<code>/setrefercredits &lt;amount&gt;</code>\n"
            "<code>/setdeductioncredits &lt;amount&gt;</code>\n"
            "<code>/createvoucher &lt;code&gt; &lt;credits&gt; &lt;uses&gt;</code>\n"
            "<code>/deletevoucher &lt;code&gt;</code>\n"
            "<code>/listvouchers</code>\n"
            "<code>/check &lt;uid&gt;</code>\n"
            "<code>/msg &lt;uid&gt; &lt;message&gt;</code>\n"
            "<code>/referlist</code>\n"
            "<code>/stats</code>\n"
            "<code>/id &lt;@username&gt;</code>\n"
            "<code>/orderid &lt;order_id&gt;</code>\n\n"
            "🛡️ <b>Admin & Owner:</b>\n"
            "<code>/addcredits &lt;uid&gt; &lt;amount&gt;</code>\n"
            "<code>/removecredits &lt;uid&gt; &lt;amount&gt;</code>\n"
            "<code>/setcredits &lt;uid&gt; &lt;amount&gt;</code>\n"
            "<code>/checkbalance &lt;uid&gt;</code>\n"
            "<code>/ban &lt;uid&gt;</code> · <code>/unban &lt;uid&gt;</code>\n"
            "<code>/banusers</code>\n"
            "<code>/broadcast &lt;msg&gt;</code>\n"
            "━━━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML",
            reply_markup=refresh_kb
        )
        return

# ══════════════════════════════════════════════
#               ADMIN COMMANDS
# ══════════════════════════════════════════════

async def setmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MODE
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args or context.args[0].lower() not in ["dual", "group", "private", "maintenance"]:
        await update.message.reply_text("📌 Usage: /setmode dual|group|private|maintenance")
        return
    MODE = context.args[0].lower()
    await log_admin_action(update.effective_user.id, "setmode", None, f"Mode set to {MODE}")
    await update.message.reply_text(f"✅ Mode set to: <code>{MODE}</code>", parse_mode="HTML")

async def unlimited(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global UNLIMITED_MODE
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /unlimited on|off")
        return
    val = context.args[0].lower()
    if val == "on":
        UNLIMITED_MODE = True
        await log_admin_action(update.effective_user.id, "unlimited", None, "Unlimited mode ON")
        await update.message.reply_text("♾️ <b>Unlimited Mode is now ON</b>\n\nAll users can search for free.", parse_mode="HTML")
    elif val == "off":
        UNLIMITED_MODE = False
        await log_admin_action(update.effective_user.id, "unlimited", None, "Unlimited mode OFF")
        await update.message.reply_text("✅ <b>Unlimited Mode is now OFF</b>\n\nCredits will be deducted normally.", parse_mode="HTML")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    full_text = update.message.text
    if len(full_text.split(" ", 1)) < 2:
        await update.message.reply_text("📌 Usage: /broadcast <message>")
        return
    message = full_text.split(" ", 1)[1]
    success = failed = 0
    async for u in users.find({}, {"user_id": 1}):
        try:
            await context.bot.send_message(chat_id=u["user_id"], text=message)
            success += 1
        except Exception:
            failed += 1
    await log_admin_action(update.effective_user.id, "broadcast", None, f"Broadcast sent, success: {success}, failed: {failed}")
    await update.message.reply_text(f"📢 <b>Broadcast Complete</b>\n\n✅ Sent: {success}\n❌ Failed: {failed}", parse_mode="HTML")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total_users    = await users.count_documents({})
    joined_users   = await users.count_documents({"force_joined": True})
    only_start     = total_users - joined_users
    total_credits  = sum([u["credits"] async for u in users.find({}, {"credits": 1})])
    total_vouchers = await vouchers.count_documents({})
    refresh_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]])
    await update.message.reply_text(
        "📊 <b>Bot Statistics</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Total Users: <b>{total_users}</b>\n"
        f"✅ Joined Users: <b>{joined_users}</b>\n"
        f"⏳ Only Started: <b>{only_start}</b>\n\n"
        f"💰 Total Credits: <b>{total_credits}</b>\n"
        f"🔧 Mode: <code>{MODE}</code>\n"
        f"♾️ Unlimited: {'ON ✅' if UNLIMITED_MODE else 'OFF ❌'}\n"
        f"🎁 Start Credits: <b>{START_CREDITS}</b>\n"
        f"🔗 Refer Credits: <b>{REFER_CREDITS}</b>\n"
        f"🎟️ Vouchers: <b>{total_vouchers}</b>",
        parse_mode="HTML",
        reply_markup=refresh_kb
    )

async def addcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("📌 Usage: /addcredits <user_id> <amount>")
        return
    uid     = int(context.args[0])
    amount  = int(context.args[1])
    new_bal = await update_credits(uid, amount)
    if new_bal is None:
        await update.message.reply_text("❌ User not found.")
        return
    await log_admin_action(update.effective_user.id, "addcredits", uid, f"Added {amount} credits")
    await update.message.reply_text(f"✅ Added <b>{amount}</b> credits to <code>{uid}</code>\n💰 New Balance: <b>{new_bal}</b>", parse_mode="HTML")
    try:
        await context.bot.send_message(
            chat_id=uid,
            text=(
                "🎉 <b>Credits Added!</b>\n\n"
                f"💰 <b>{amount} credits</b> have been added to your account.\n"
                f"💳 New Balance: <b>{new_bal}</b> credits\n\n"
                "Thank you for your support! 🙏\n"
                "<i>Happy searching — @DarkGalaxxyy</i>"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

async def removecredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("📌 Usage: /removecredits <user_id> <amount>")
        return
    uid = int(context.args[0])
    amount = int(context.args[1])
    new_bal = await update_credits(uid, -amount)
    if new_bal is None:
        await update.message.reply_text("❌ User not found.")
        return
    await log_admin_action(update.effective_user.id, "removecredits", uid, f"Removed {amount} credits")
    await update.message.reply_text(f"✅ Removed <b>{amount}</b> credits from <code>{uid}</code>\n💰 New Balance: <b>{new_bal}</b>", parse_mode="HTML")

async def setcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("📌 Usage: /setcredits <user_id> <amount>")
        return
    uid = int(context.args[0])
    amount = int(context.args[1])
    success = await set_credits(uid, amount)
    if success:
        await log_admin_action(update.effective_user.id, "setcredits", uid, f"Set credits to {amount}")
        await update.message.reply_text(f"✅ Credits set to <b>{amount}</b> for <code>{uid}</code>", parse_mode="HTML")
    else:
        await update.message.reply_text("❌ User not found.")

async def checkbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /checkbalance <user_id>")
        return
    user = await get_user(int(context.args[0]))
    if not user:
        await update.message.reply_text("❌ User not found.")
        return
    await update.message.reply_text(
        f"👤 User: <code>{context.args[0]}</code>\n"
        f"💰 Credits: <b>{user['credits']}</b>\n"
        f"📅 Joined: {user['joined']}\n"
        f"👥 Referrals: {user['referrals']}",
        parse_mode="HTML"
    )

async def setstartcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global START_CREDITS
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /setstartcredits <amount>")
        return
    START_CREDITS = int(context.args[0])
    await log_admin_action(update.effective_user.id, "setstartcredits", None, f"Start credits set to {START_CREDITS}")
    await update.message.reply_text(f"✅ Start credits set to: <b>{START_CREDITS}</b>", parse_mode="HTML")

async def setrefercredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global REFER_CREDITS
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /setrefercredits <amount>")
        return
    REFER_CREDITS = int(context.args[0])
    await log_admin_action(update.effective_user.id, "setrefercredits", None, f"Refer credits set to {REFER_CREDITS}")
    await update.message.reply_text(f"✅ Refer credits set to: <b>{REFER_CREDITS}</b>", parse_mode="HTML")

async def setdeductioncredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DEDUCTION_CREDITS
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Owner only command.")
        return
    if not context.args or not context.args[0].isdigit() or int(context.args[0]) < 1:
        await update.message.reply_text("📌 Usage: /setdeductioncredits <amount>\n<i>Example: /setdeductioncredits 2</i>", parse_mode="HTML")
        return
    DEDUCTION_CREDITS = int(context.args[0])
    await log_admin_action(update.effective_user.id, "setdeductioncredits", None, f"Search cost set to {DEDUCTION_CREDITS}")
    await update.message.reply_text(
        f"✅ <b>Search cost updated!</b>\n\nEach search now costs <b>{DEDUCTION_CREDITS} credit(s)</b>.",
        parse_mode="HTML"
    )

async def orderid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /orderid <order_id>")
        return
    oid = context.args[0]
    order = await orders.find_one({"order_id": oid})
    if not order:
        await update.message.reply_text("❌ Order not found.")
        return
    msg = (
        f"📦 <b>Order Details</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔖 Order ID: <code>{order['order_id']}</code>\n"
        f"👤 User ID: <code>{order['user_id']}</code>\n"
        f"💵 Amount: ₹{order['amount']}\n"
        f"📊 Status: {order['status']}\n"
        f"📅 Created: {order['created']}\n"
    )
    if order.get("type") == "withdraw":
        msg += (
            f"🏦 Bank: {order.get('bank_name', 'N/A')}\n"
            f"📛 Account: {order.get('account_name', 'N/A')}\n"
            f"📱 UPI: <code>{order.get('upi_id', 'N/A')}</code>\n"
        )
    else:
        msg += f"💰 Credits: {order.get('credits', 'N/A')}\n"
    await update.message.reply_text(msg, parse_mode="HTML")

# ══════════════════════════════════════════════
#               OWNER ADMIN MANAGEMENT
# ══════════════════════════════════════════════

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Owner only command.")
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /addadmin <user_id>")
        return
    uid  = int(context.args[0])
    user = await get_user(uid)
    if not user:
        await update.message.reply_text("❌ User not found in database.")
        return
    existing = await admins.find_one({"user_id": uid})
    if existing:
        await update.message.reply_text(f"⚠️ User <code>{uid}</code> is already an admin.", parse_mode="HTML")
        return
    uname = f"@{user['username']}" if user.get("username") else user.get("name") or str(uid)
    await admins.insert_one({
        "user_id": uid,
        "username": user.get("username"),
        "name": user.get("name"),
        "added": datetime.now(IST).strftime("%Y-%m-%d %H:%M")
    })
    await log_admin_action(ADMIN_ID, "addadmin", uid, f"Added admin {uid}")
    await update.message.reply_text(f"✅ <b>{uname}</b> (<code>{uid}</code>) has been added as admin.", parse_mode="HTML")
    try:
        await context.bot.send_message(chat_id=uid, text="🛡️ <b>You have been granted Admin access.</b>\n\nYou can now use admin commands.", parse_mode="HTML")
    except Exception:
        pass

async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Owner only command.")
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /removeadmin <user_id>")
        return
    uid    = int(context.args[0])
    result = await admins.delete_one({"user_id": uid})
    if result.deleted_count:
        await log_admin_action(ADMIN_ID, "removeadmin", uid, f"Removed admin {uid}")
        await update.message.reply_text(f"✅ User <code>{uid}</code> removed from admins.", parse_mode="HTML")
        try:
            await context.bot.send_message(chat_id=uid, text="⚠️ Your admin access has been revoked.")
        except Exception:
            pass
    else:
        await update.message.reply_text("❌ User is not an admin.")

async def adminlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Owner only command.")
        return
    all_admins = await admins.find({}).to_list(length=100)
    msg = "🛡️ <b>Admin List</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"👑 Owner: <a href='tg://user?id={ADMIN_ID}'>Owner</a>\n\n"
    if not all_admins:
        msg += "_No additional admins._"
    else:
        for i, a in enumerate(all_admins, 1):
            aname = a.get("name") or f"User {a['user_id']}"
            msg += f'{i}. <a href="tg://user?id={a["user_id"]}">{aname}</a> — Added: {a.get("added", "N/A")}\n'
    msg += "\n━━━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(msg, parse_mode="HTML")

async def checkadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Owner only command.")
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /checkadmin <user_id>")
        return
    uid  = int(context.args[0])
    logs = await adminlogs.find({"admin_id": uid}).sort("time", -1).limit(50).to_list(length=50)
    admin_record = await admins.find_one({"user_id": uid})
    is_adm = "Yes ✅" if admin_record or uid == ADMIN_ID else "No ❌"
    msg = f"🛡️ <b>Admin Check: <code>{uid}</code></b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"Admin Status: {is_adm}\n\n"
    if logs:
        msg += "<b>Recent Actions (max 50):</b>\n"
        for log in logs:
            tgt = f" → <code>{log['target']}</code>" if log.get("target") else ""
            details = f" ({log['details']})" if log.get("details") else ""
            msg += f"• <code>{log['action']}</code>{tgt}{details} — {log['time']}\n"
    else:
        msg += "_No actions logged._"
    await update.message.reply_text(msg, parse_mode="HTML")

# ══════════════════════════════════════════════
#               CONFIRM WITHDRAW CALLBACK
# ══════════════════════════════════════════════

async def confirm_withdraw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if not context.user_data.get("withdraw_amount"):
        await query.message.edit_text("❌ Session expired. Start again.")
        return
    amount = context.user_data["withdraw_amount"]
    bank = context.user_data["withdraw_bank_name"]
    acc = context.user_data["withdraw_account_name"]
    upi = context.user_data["withdraw_upi"]
    order_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    await orders.insert_one({
        "order_id": order_id,
        "user_id": user_id,
        "amount": amount,
        "status": "pending",
        "type": "withdraw",
        "bank_name": bank,
        "account_name": acc,
        "upi_id": upi,
        "created": datetime.now(IST).strftime("%Y-%m-%d %H:%M")
    })
    user = await get_user(user_id)
    uname = f"@{user['username']}" if user.get("username") else user.get("name") or f"User {user_id}"
    payout_msg = (
        "🏧 <b>New Withdrawal Request</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Name: {user.get('name', 'N/A')}\n"
        f"👤 Username: {uname}\n"
        f"🆔 User ID: <code>{user_id}</code>\n"
        f"💵 Amount: ₹{amount}\n"
        f"🏦 Bank: {bank}\n"
        f"📛 Account: {acc}\n"
        f"📱 UPI: <code>{upi}</code>\n"
        f"📊 Status: Pending ⏳\n\n"
        f"🔖 Order ID: <code>{order_id}</code>"
    )
    payout_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Mark as Done", callback_data=f"withdrawdone_{order_id}_{user_id}_{amount}"),
         InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancelwithdraworder_{order_id}_{user_id}")]
    ])
    try:
        await context.bot.send_message(chat_id=PAYOUT_CHANNEL, text=payout_msg, parse_mode="HTML", reply_markup=payout_kb)
    except Exception as e:
        await query.message.edit_text(f"❌ Failed to submit. Contact support. Error: {e}")
        return
    for k in ("withdraw_amount", "withdraw_bank_name", "withdraw_account_name", "withdraw_upi"):
        context.user_data.pop(k, None)
    await query.message.edit_text("✅ Withdrawal request submitted! We will process it shortly.", reply_markup=None)

# ══════════════════════════════════════════════
#               MAIN
# ══════════════════════════════════════════════

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",                start))
    app.add_handler(CommandHandler("num",                  num))
    app.add_handler(CommandHandler("tgnum",                tgnum))
    app.add_handler(CommandHandler("vehicle",              vehicle))
    app.add_handler(CommandHandler("id",                   get_id))
    app.add_handler(CommandHandler("referstat",            referstat))
    app.add_handler(CommandHandler("referlist",            referlist))
    app.add_handler(CommandHandler("redeem",               redeem))
    app.add_handler(CommandHandler("createvoucher",        createvoucher))
    app.add_handler(CommandHandler("deletevoucher",        deletevoucher))
    app.add_handler(CommandHandler("listvouchers",         listvouchers))
    app.add_handler(CommandHandler("unlimited",            unlimited))
    app.add_handler(CommandHandler("setmode",              setmode))
    app.add_handler(CommandHandler("broadcast",            broadcast))
    app.add_handler(CommandHandler("stats",                stats))
    app.add_handler(CommandHandler("addcredits",           addcredits))
    app.add_handler(CommandHandler("removecredits",        removecredits))
    app.add_handler(CommandHandler("setcredits",           setcredits))
    app.add_handler(CommandHandler("checkbalance",         checkbalance))
    app.add_handler(CommandHandler("setstartcredits",      setstartcredits))
    app.add_handler(CommandHandler("setrefercredits",      setrefercredits))
    app.add_handler(CommandHandler("setdeductioncredits",  setdeductioncredits))
    app.add_handler(CommandHandler("orderid",              orderid))
    app.add_handler(CommandHandler("ban",                  ban))
    app.add_handler(CommandHandler("unban",                unban))
    app.add_handler(CommandHandler("banusers",             banusers))
    app.add_handler(CommandHandler("check",                check))
    app.add_handler(CommandHandler("msg",                  msg_user))
    app.add_handler(CommandHandler("addadmin",             addadmin))
    app.add_handler(CommandHandler("removeadmin",          removeadmin))
    app.add_handler(CommandHandler("adminlist",            adminlist))
    app.add_handler(CommandHandler("checkadmin",           checkadmin))
    app.add_handler(CallbackQueryHandler(confirm_withdraw_callback, pattern="confirm_withdraw"))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    print("Bot is running...")
    app.run_polling()
