import requests
import json
import random
import string
import certifi
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import BadRequest

# ══════════════════════════════════════════════
#               CONFIGURATION
# ══════════════════════════════════════════════

API_URL        = "num.zvx.workers.dev/?key=DxD&mobile={}"
BOT_TOKEN      = "8693982920:AAH_fwloRRWwRCgNyYyVNeZlY1PoVcyPcG0"
BOT_USERNAME   = "Gamcchhaa_Bot"
CUSTOM_NAME    = "@ROLEX_SIR009 & @Darkdon01 & @DarkGalaxxyy & @R4HULxTRUSTED"
ADMIN_ID       = 6131370190
MONGO_URI      = "mongodb+srv://saitamauchiha01025_db_user:yMvHQKjjRpFsgDxz@cluster0.fomymln.mongodb.net/?appName=Cluster0"
UPI_ID         = "DarkGalaxxyy@naviaxis"
UPI_QR_LINK    = "https://t.me/jaiwkwkwkkwkwkjwkq/2"
PAYOUT_CHANNEL = -1003579822719

START_CREDITS  = 2
REFER_CREDITS  = 2
MODE           = "dual"
UNLIMITED_MODE = False

FORCE_CHANNEL_USERNAME = "siee1234"
FORCE_CHANNEL_LINK     = "https://t.me/siee1234"
FORCE_GROUP1_LINK      = "https://t.me/+QmnlbCK1x045MzZl"
FORCE_GROUP2_ID        = -1003416250413
FORCE_GROUP2_LINK      = "https://t.me/+cePuY51FkgE5MzY1"

# ══════════════════════════════════════════════
#               MONGODB
# ══════════════════════════════════════════════

client   = AsyncIOMotorClient(MONGO_URI, tls=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=10000)
db       = client["numbot"]
users    = db["users"]
vouchers = db["vouchers"]
orders   = db["orders"]

# ══════════════════════════════════════════════
#               DATA MANAGEMENT
# ══════════════════════════════════════════════

async def get_user(user_id):
    return await users.find_one({"user_id": user_id})

async def create_user(user_id, referred_by=None, username=None, name=None, force_joined=False):
    ref_code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    user = {
        "user_id"     : user_id,
        "credits"     : START_CREDITS if force_joined else 0,
        "joined"      : datetime.now().strftime("%Y-%m-%d"),
        "ref_code"    : ref_code,
        "referred_by" : referred_by,
        "referrals"   : 0,
        "username"    : username,
        "name"        : name,
        "banned"      : False,
        "force_joined": force_joined
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
#               KEYBOARDS
# ══════════════════════════════════════════════

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

    # Save user even before join check
    user = await get_user(user_id)
    if user is None:
        user = await create_user(user_id, referred_by, username, name, force_joined=False)
    else:
        await users.update_one({"user_id": user_id}, {"$set": {"username": username, "name": name}})

    if user.get("banned"):
        await update.message.reply_text(
            "🚫 *Access Denied*\n\nYou have been banned from using this bot.\nContact @DarkGalaxxyy for support.",
            parse_mode="Markdown"
        )
        return

    joined = await force_join_check(bot, user_id)
    if not joined:
        await update.message.reply_text(
            "╔══════════════════════╗\n"
            "        🔐 *ACCESS RESTRICTED*\n"
            "╚══════════════════════╝\n\n"
            "To use this bot, you must join\n"
            "all of the following:\n\n"
            "📢 Official Channel\n"
            "👥 Group 1  •  👥 Group 2\n\n"
            "After joining, send /start again ↩️",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    # First time joining — give credits
    if not user.get("force_joined"):
        await users.update_one(
            {"user_id": user_id},
            {"$set": {"force_joined": True}, "$inc": {"credits": START_CREDITS}}
        )
        if referred_by:
            await users.update_one({"user_id": referred_by}, {"$inc": {"credits": REFER_CREDITS, "referrals": 1}})
        is_new = True
        user   = await get_user(user_id)
    else:
        is_new = False

    links_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Channel", url=FORCE_CHANNEL_LINK),
         InlineKeyboardButton("👥 Group 1", url=FORCE_GROUP1_LINK)],
        [InlineKeyboardButton("👥 Group 2", url=FORCE_GROUP2_LINK)],
    ])

    if is_new:
        welcome_msg = (
            f"🎊 *Welcome aboard, {name}!*\n\n"
            f"🎁 You've received *{START_CREDITS} free credits* to get started!\n\n"
        )
    else:
        welcome_msg = f"👋 *Welcome back, {name}!*\n\n"

    unlimited_note = "♾️ *Unlimited Mode is ON* — searches are free!\n\n" if UNLIMITED_MODE else ""

    msg = (
        f"{welcome_msg}"
        f"{unlimited_note}"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔍 *NumBot* — Fetch detailed info\n"
        "about any mobile number instantly.\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 *Commands*\n\n"
        "`/num <number>` — Search a number\n"
        "`/referstat` — Refer leaderboard\n"
        "`/redeem <code>` — Redeem voucher\n\n"
        "💡 Use the buttons below to navigate."
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=links_kb)
    await update.message.reply_text("🗂 *Main Menu*", parse_mode="Markdown", reply_markup=get_main_keyboard(user_id))

# ══════════════════════════════════════════════
#               PROCESS NUMBER
# ══════════════════════════════════════════════

async def process_number(update, context, number):
    user_id   = update.effective_user.id
    chat_type = update.effective_chat.type
    bot       = context.bot

    if MODE == "maintenance":
        await update.message.reply_text("🔧 *Maintenance Mode*\n\nBot is under maintenance. Please try again later.", parse_mode="Markdown")
        return
    if MODE == "group" and chat_type == "private":
        await update.message.reply_text("⚠️ This bot only works in groups.")
        return
    if MODE == "private" and chat_type in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ This bot only works in private chat.")
        return

    joined = await force_join_check(bot, user_id)
    if not joined:
        await update.message.reply_text("⚠️ *Access Restricted*\n\nJoin all required channels first.", parse_mode="Markdown", reply_markup=join_keyboard())
        return

    user = await get_user(user_id)
    if user is None:
        user = await create_user(user_id)

    if user.get("banned"):
        await update.message.reply_text("🚫 You have been banned from using this bot.")
        return

    if not UNLIMITED_MODE and user["credits"] <= 0:
        await update.message.reply_text(
            "❌ *Insufficient Credits*\n\n"
            "You have *0 credits* remaining.\n\n"
            "💡 *Ways to earn credits:*\n"
            "• Refer friends → 🔗 Refer button\n"
            "• Redeem a voucher → /redeem\n"
            "• Purchase credits → 💳 Buy Credits",
            parse_mode="Markdown"
        )
        return

    try:
        url = API_URL.format(number)
        if not url.startswith("http"):
            url = "https://" + url
        response = requests.get(url, timeout=10)
        result   = response.text.strip()

        if not result:
            await update.message.reply_text("❌ *No Result Found*\n\nNo data available for this number.", parse_mode="Markdown")
            return

        try:
            data = json.loads(result)
            if not data.get("success", True) or "No Record" in str(data):
                await update.message.reply_text("❌ *No Result Found*\n\nNo data available for this number.", parse_mode="Markdown")
                return

            if UNLIMITED_MODE:
                credit_note = "♾️ _Unlimited Mode — no credits deducted_"
            else:
                new_balance = await update_credits(user_id, -1)
                credit_note = f"💰 _Credits remaining: {new_balance}_"

            if "Api_BY" in data:
                data["Api_BY"] = CUSTOM_NAME
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
            await update.message.reply_text(f"```\n{pretty}\n```\n\n{credit_note}", parse_mode="Markdown")

        except json.JSONDecodeError:
            if not UNLIMITED_MODE:
                new_balance = await update_credits(user_id, -1)
                credit_note = f"💰 _Credits remaining: {new_balance}_"
            else:
                credit_note = "♾️ _Unlimited Mode ON_"
            await update.message.reply_text(f"{result}\n\n{credit_note}", parse_mode="Markdown")

    except requests.exceptions.Timeout:
        await update.message.reply_text("⏱ *Request Timed Out*\n\nPlease try again.", parse_mode="Markdown")
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("📡 *Connection Error*\n\nUnable to connect to the API.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📌 *Usage:* `/num <number>`\n\n*Example:* `/num 9876543210`", parse_mode="Markdown")
        return
    await process_number(update, context, context.args[0])

# ══════════════════════════════════════════════
#               BAN / UNBAN
# ══════════════════════════════════════════════

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /ban <user_id>")
        return
    uid    = int(context.args[0])
    result = await users.update_one({"user_id": uid}, {"$set": {"banned": True}})
    if result.modified_count:
        await update.message.reply_text(f"🚫 User `{uid}` has been banned.", parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=uid, text="🚫 You have been banned from this bot.\nContact @DarkGalaxxyy for support.")
        except Exception:
            pass
    else:
        await update.message.reply_text("❌ User not found.")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /unban <user_id>")
        return
    uid    = int(context.args[0])
    result = await users.update_one({"user_id": uid}, {"$set": {"banned": False}})
    if result.modified_count:
        await update.message.reply_text(f"✅ User `{uid}` has been unbanned.", parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=uid, text="✅ You have been unbanned!\nYou can now use the bot again.")
        except Exception:
            pass
    else:
        await update.message.reply_text("❌ User not found.")

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

    referred_users = await users.find(
        {"referred_by": uid}, {"username": 1, "user_id": 1, "name": 1}
    ).to_list(length=100)

    refer_list = ""
    for r in referred_users:
        rname = f"@{r['username']}" if r.get("username") else r.get("name") or f"User {r['user_id']}"
        refer_list += f"  • [{rname}](tg://user?id={r['user_id']})\n"

    msg = (
        "👤 *User Details*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Name: {name}\n"
        f"🔖 Username: {uname}\n"
        f"🆔 User ID: `{uid}`\n"
        f"💰 Credits: {user['credits']}\n"
        f"📅 Joined: {user['joined']}\n"
        f"👥 Referrals: {user['referrals']}\n"
        f"✅ Force Joined: {fj}\n"
        f"🚫 Banned: {banned}\n"
        f"🔗 [Refer Link]({ref_link})\n"
    )
    if refer_list:
        msg += f"\n👥 *Referred Users:*\n{refer_list}"
    else:
        msg += "\n👥 Referred Users: None"

    await update.message.reply_text(msg, parse_mode="Markdown")

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
        await update.message.reply_text(f"✅ Message sent to {uname} (`{uid}`)", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {str(e)}")

# ══════════════════════════════════════════════
#               REFER LIST (ADMIN)
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

    msg = "📋 *Full Refer List*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, u in enumerate(all_users, 1):
        name = f"@{u['username']}" if u.get("username") else u.get("name") or f"User {u['user_id']}"
        msg += f"{i}. [{name}](tg://user?id={u['user_id']}) — {u['referrals']} refers\n"
    msg += "\n━━━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ══════════════════════════════════════════════
#               REFER LEADERBOARD (PUBLIC)
# ══════════════════════════════════════════════

async def referstat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = await users.find(
        {"referrals": {"$gt": 0}, "user_id": {"$ne": ADMIN_ID}},
        {"username": 1, "user_id": 1, "referrals": 1, "name": 1}
    ).sort("referrals", -1).limit(10).to_list(length=10)

    if not top_users:
        await update.message.reply_text("🔗 No referrals yet! Be the first to refer.")
        return

    medals = ["🥇", "🥈", "🥉"]
    msg = "🏆 *Refer Leaderboard*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, u in enumerate(top_users):
        medal = medals[i] if i < 3 else f"{i+1}\\."
        name  = f"@{u['username']}" if u.get("username") else u.get("name") or f"User {u['user_id']}"
        msg  += f"{medal} [{name}](tg://user?id={u['user_id']}) — *{u['referrals']}* refers\n"
    msg += "\n━━━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(msg, parse_mode="Markdown")

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
        await update.message.reply_text(f"❌ Voucher `{code}` already exists.", parse_mode="Markdown")
        return
    await vouchers.insert_one({"code": code, "credits": credits, "max_uses": max_uses, "uses": 0, "used_by": []})
    await update.message.reply_text(
        f"🎟️ *Voucher Created!*\n\n"
        f"📌 Code: `{code}`\n"
        f"💰 Credits: {credits}\n"
        f"👥 Max Uses: {max_uses}",
        parse_mode="Markdown"
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
        f"🎉 *Voucher Redeemed!*\n\n"
        f"💰 Credits Added: *{voucher['credits']}*\n"
        f"💳 New Balance: *{new_balance}* credits",
        parse_mode="Markdown"
    )


async def deletevoucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /deletevoucher <code>")
        return
    code   = context.args[0].upper()
    result = await vouchers.delete_one({"code": code})
    await update.message.reply_text(
        f"✅ Voucher `{code}` deleted." if result.deleted_count else f"❌ Voucher `{code}` not found.",
        parse_mode="Markdown"
    )


async def listvouchers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    all_vouchers = await vouchers.find({}).to_list(length=50)
    if not all_vouchers:
        await update.message.reply_text("No vouchers found.")
        return
    msg = "🎟️ *All Vouchers*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for v in all_vouchers:
        msg += f"`{v['code']}` — 💰 {v['credits']} credits — 👥 {v['uses']}/{v['max_uses']} used\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ══════════════════════════════════════════════
#               BUY CREDITS - UPI
# ══════════════════════════════════════════════

async def buy_credits_menu(update, context):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Pay via UPI", callback_data="buy_upi")]
    ])
    await update.message.reply_text(
        "💳 *Buy Credits*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💵 Rate: ₹1 = 1 Credit\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Select payment method below:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    data    = query.data
    user_id = query.from_user.id
    await query.answer()

    # ── UPI Selected ──
    if data == "buy_upi":
        context.user_data["upi_step"] = "enter_amount"
        await query.message.edit_text(
            "📱 *UPI Payment*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💵 Rate: ₹1 = 1 Credit\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Please enter the amount you want to pay (in ₹):\n\n"
            "_Example: 50_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]])
        )

    # ── Cancel ──
    elif data == "cancel_payment":
        context.user_data.pop("upi_step", None)
        context.user_data.pop("upi_amount", None)
        try:
            await query.message.edit_text("❌ *Payment Cancelled*\n\nNo charges were made.", parse_mode="Markdown")
        except Exception:
            try:
                await query.message.edit_caption("❌ *Payment Cancelled*\n\nNo charges were made.", parse_mode="Markdown", reply_markup=None)
            except Exception:
                pass

    # ── I've Paid ──
    elif data.startswith("paid_"):
        order_id = data.split("_", 1)[1]
        order    = await orders.find_one({"order_id": order_id})
        if not order:
            await query.answer("❌ Order not found.", show_alert=True)
            return
        username = query.from_user.username
        name     = query.from_user.full_name
        amount   = order["amount"]
        uname    = f"@{username}" if username else name or f"User {user_id}"

        payout_msg = (
            "💳 *New Payment Order*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📛 Name: {name}\n"
            f"👤 Username: {uname}\n"
            f"🆔 User ID: `{user_id}`\n"
            f"💵 Amount: ₹{amount}\n"
            f"💰 Credits: {amount}\n"
            f"📊 Status: Pending ⏳\n\n"
            f"🔖 Order ID: `{order_id}`"
        )
        status_kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Mark as Done", callback_data=f"done_{order_id}_{user_id}_{amount}")]])
        await context.bot.send_message(chat_id=PAYOUT_CHANNEL, text=payout_msg, parse_mode="Markdown", reply_markup=status_kb)

        try:
            await query.message.edit_caption(
                "✅ *Payment Request Submitted!*\n\n"
                "Your credits will be added after verification.\n"
                "_Usually within a few minutes._",
                parse_mode="Markdown",
                reply_markup=None
            )
        except Exception:
            pass

    # ── Mark as Done (Admin in payout channel) ──
    elif data.startswith("done_"):
        parts    = data.split("_")
        order_id = parts[1]
        uid      = int(parts[2])
        amount   = int(parts[3])
        await update_credits(uid, amount)
        await orders.update_one({"order_id": order_id}, {"$set": {"status": "done"}})
        new_text = query.message.text.replace("📊 Status: Pending ⏳", "📊 Status: Done ✅")
        try:
            await query.message.edit_text(new_text, parse_mode="Markdown", reply_markup=None)
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "🎉 *Payment Approved!*\n\n"
                    f"💰 *{amount} credits* have been added to your account.\n\n"
                    "Start searching now — happy hunting! 🔍\n"
                    "_For any help, contact @DarkGalaxxyy_"
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass

# ══════════════════════════════════════════════
#               BUTTON HANDLERS
# ══════════════════════════════════════════════

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text    = update.message.text
    user_id = update.effective_user.id
    bot     = context.bot

    # ── UPI Amount Entry ──
    if context.user_data.get("upi_step") == "enter_amount":
        if text.isdigit() and int(text) > 0:
            amount   = int(text)
            order_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            context.user_data["upi_step"] = None
            await orders.insert_one({
                "order_id": order_id,
                "user_id" : user_id,
                "amount"  : amount,
                "status"  : "pending",
                "created" : datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ I've Paid", callback_data=f"paid_{order_id}")],
                [InlineKeyboardButton("❌ Cancel",    callback_data="cancel_payment")]
            ])
            await update.message.reply_photo(
                photo=UPI_QR_LINK,
                caption=(
                    f"📱 *UPI Payment*\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 Amount: ₹{amount}\n"
                    f"💰 Credits: {amount}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🏦 UPI ID: `{UPI_ID}`\n\n"
                    f"_Scan QR or use UPI ID to pay_\n"
                    f"Then tap ✅ I've Paid below."
                ),
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                "❌ Invalid amount. Enter a valid number:\n_Example: 50_",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]])
            )
        return

    # ── Search Number ──
    if text == "🔍 Search Number":
        joined = await force_join_check(bot, user_id)
        if not joined:
            await update.message.reply_text("⚠️ Please join all required channels/groups first.", reply_markup=join_keyboard())
            return
        context.user_data["waiting_for_number"] = True
        await update.message.reply_text(
            "🔍 *Number Search*\n\n"
            "Please enter the number to search:\n\n"
            "⚠️ *Without +91* — digits only\n"
            "_Example: `9876543210`_",
            parse_mode="Markdown"
        )
        return

    if context.user_data.get("waiting_for_number"):
        context.user_data["waiting_for_number"] = False
        if text.isdigit():
            await process_number(update, context, text)
        else:
            await update.message.reply_text("❌ Invalid input. Enter digits only, without +91 or spaces.")
        return

    # ── My Account ──
    if text == "👤 My Account":
        user = await get_user(user_id) or await create_user(user_id)
        unlimited_note = "\n♾️ _Unlimited Mode ON — searches are free!_" if UNLIMITED_MODE else ""
        await update.message.reply_text(
            "👤 *My Account*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 User ID: `{user_id}`\n"
            f"💰 Credits: *{user['credits']}*{unlimited_note}\n"
            f"📅 Joined: {user['joined']}\n"
            f"👥 Referrals: {user['referrals']}\n"
            "━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
        )
        return

    # ── Credits ──
    if text == "💰 Credits":
        unlimited_note = "\n\n♾️ *Unlimited Mode is ON* — searches are FREE!" if UNLIMITED_MODE else ""
        await update.message.reply_text(
            "💰 *Credits*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Each search costs *1 credit*.{unlimited_note}\n\n"
            "📌 *How to earn credits:*\n\n"
            f"🎁 New users → *{START_CREDITS}* free credits\n"
            f"🔗 Refer a friend → *{REFER_CREDITS}* credits\n"
            "🎟️ Redeem voucher → `/redeem <code>`\n"
            "💳 Purchase → ₹1 = 1 credit\n"
            "━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
        )
        return

    # ── Refer ──
    if text == "🔗 Refer":
        user     = await get_user(user_id) or await create_user(user_id)
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user['ref_code']}"
        await update.message.reply_text(
            "🔗 *Refer & Earn*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Share your link and earn credits\n"
            "for every friend who joins!\n\n"
            f"🔗 Your Link:\n`{ref_link}`\n\n"
            f"💰 Reward: *{REFER_CREDITS} credits* per refer\n"
            f"👥 Total Referrals: *{user['referrals']}*\n"
            "━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
        )
        return

    # ── Buy Credits ──
    if text == "💳 Buy Credits":
        await buy_credits_menu(update, context)
        return

    # ── Help ──
    if text == "❓ Help":
        await update.message.reply_text(
            "❓ *Help & Support*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "For any queries, issues or\n"
            "to purchase credits, contact:\n\n"
            "👤 @DarkGalaxxyy\n\n"
            "_We typically respond within minutes._\n"
            "━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
        )
        return

    # ── Admin Panel ──
    if text == "⚙️ Admin Panel":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ Access Denied.")
            return
        total_users    = await users.count_documents({})
        joined_users   = await users.count_documents({"force_joined": True})
        only_start     = total_users - joined_users
        total_credits  = sum([u["credits"] async for u in users.find({}, {"credits": 1})])
        total_vouchers = await vouchers.count_documents({})
        await update.message.reply_text(
            "⚙️ *Admin Panel*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔧 Mode: `{MODE}`\n"
            f"♾️ Unlimited: {'ON ✅' if UNLIMITED_MODE else 'OFF ❌'}\n\n"
            f"👤 Total Users: *{total_users}*\n"
            f"✅ Joined Users: *{joined_users}*\n"
            f"⏳ Only Started: *{only_start}*\n\n"
            f"💰 Total Credits: *{total_credits}*\n"
            f"🎁 Start Credits: *{START_CREDITS}*\n"
            f"🔗 Refer Credits: *{REFER_CREDITS}*\n"
            f"🎟️ Vouchers: *{total_vouchers}*\n\n"
            "📌 *Commands:*\n\n"
            "`/setmode` `dual|group|private|maintenance`\n"
            "`/unlimited` `on|off`\n"
            "`/broadcast` `<msg>`\n"
            "`/stats`\n"
            "`/addcredits` `<uid> <amount>`\n"
            "`/removecredits` `<uid> <amount>`\n"
            "`/setcredits` `<uid> <amount>`\n"
            "`/checkbalance` `<uid>`\n"
            "`/setstartcredits` `<amount>`\n"
            "`/setrefercredits` `<amount>`\n"
            "`/createvoucher` `<code> <credits> <uses>`\n"
            "`/deletevoucher` `<code>`\n"
            "`/listvouchers`\n"
            "`/ban` `<uid>` · `/unban` `<uid>`\n"
            "`/check` `<uid>`\n"
            "`/msg` `<uid> <message>`\n"
            "`/referlist`\n"
            "━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
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
    await update.message.reply_text(f"✅ Mode set to: `{MODE}`", parse_mode="Markdown")


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
        await update.message.reply_text("♾️ *Unlimited Mode is now ON*\n\nAll users can search for free.", parse_mode="Markdown")
    elif val == "off":
        UNLIMITED_MODE = False
        await update.message.reply_text("✅ *Unlimited Mode is now OFF*\n\nCredits will be deducted normally.", parse_mode="Markdown")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
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
    await update.message.reply_text(f"📢 *Broadcast Complete*\n\n✅ Sent: {success}\n❌ Failed: {failed}", parse_mode="Markdown")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total_users    = await users.count_documents({})
    joined_users   = await users.count_documents({"force_joined": True})
    only_start     = total_users - joined_users
    total_credits  = sum([u["credits"] async for u in users.find({}, {"credits": 1})])
    total_vouchers = await vouchers.count_documents({})
    await update.message.reply_text(
        "📊 *Bot Statistics*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Total Users: *{total_users}*\n"
        f"✅ Joined Users: *{joined_users}*\n"
        f"⏳ Only Started: *{only_start}*\n\n"
        f"💰 Total Credits: *{total_credits}*\n"
        f"🔧 Mode: `{MODE}`\n"
        f"♾️ Unlimited: {'ON ✅' if UNLIMITED_MODE else 'OFF ❌'}\n"
        f"🎁 Start Credits: *{START_CREDITS}*\n"
        f"🔗 Refer Credits: *{REFER_CREDITS}*\n"
        f"🎟️ Vouchers: *{total_vouchers}*",
        parse_mode="Markdown"
    )


async def addcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
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
    await update.message.reply_text(f"✅ Added *{amount}* credits to `{uid}`\n💰 New Balance: *{new_bal}*", parse_mode="Markdown")
    try:
        await context.bot.send_message(
            chat_id=uid,
            text=(
                "🎉 *Credits Added!*\n\n"
                f"💰 *{amount} credits* have been added to your account.\n"
                f"💳 New Balance: *{new_bal}* credits\n\n"
                "Thank you for your support! 🙏\n"
                "_Happy searching — @DarkGalaxxyy_"
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def removecredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("📌 Usage: /removecredits <user_id> <amount>")
        return
    new_bal = await update_credits(int(context.args[0]), -int(context.args[1]))
    await update.message.reply_text(
        f"✅ Removed *{context.args[1]}* credits\n💰 New Balance: *{new_bal}*" if new_bal is not None else "❌ User not found.",
        parse_mode="Markdown"
    )


async def setcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("📌 Usage: /setcredits <user_id> <amount>")
        return
    success = await set_credits(int(context.args[0]), int(context.args[1]))
    await update.message.reply_text(
        f"✅ Credits set to *{context.args[1]}* for `{context.args[0]}`" if success else "❌ User not found.",
        parse_mode="Markdown"
    )


async def checkbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /checkbalance <user_id>")
        return
    user = await get_user(int(context.args[0]))
    if not user:
        await update.message.reply_text("❌ User not found.")
        return
    await update.message.reply_text(
        f"👤 User: `{context.args[0]}`\n"
        f"💰 Credits: *{user['credits']}*\n"
        f"📅 Joined: {user['joined']}\n"
        f"👥 Referrals: {user['referrals']}",
        parse_mode="Markdown"
    )


async def setstartcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global START_CREDITS
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /setstartcredits <amount>")
        return
    START_CREDITS = int(context.args[0])
    await update.message.reply_text(f"✅ Start credits set to: *{START_CREDITS}*", parse_mode="Markdown")


async def setrefercredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global REFER_CREDITS
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📌 Usage: /setrefercredits <amount>")
        return
    REFER_CREDITS = int(context.args[0])
    await update.message.reply_text(f"✅ Refer credits set to: *{REFER_CREDITS}*", parse_mode="Markdown")

# ══════════════════════════════════════════════
#               MAIN
# ══════════════════════════════════════════════

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",           start))
    app.add_handler(CommandHandler("num",             num))
    app.add_handler(CommandHandler("referstat",       referstat))
    app.add_handler(CommandHandler("referlist",       referlist))
    app.add_handler(CommandHandler("redeem",          redeem))
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
    app.add_handler(CommandHandler("ban",             ban))
    app.add_handler(CommandHandler("unban",           unban))
    app.add_handler(CommandHandler("check",           check))
    app.add_handler(CommandHandler("msg",             msg_user))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    print("Bot is running...")
    app.run_polling()
