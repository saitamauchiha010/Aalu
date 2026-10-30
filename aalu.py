import requests, json, random, string, certifi, asyncio
from io import BytesIO
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import BadRequest

# ══════════════════════════════════════════════
#               CONFIGURATION
# ══════════════════════════════════════════════
API_URL        = "https://num-to-info.asurpapa.workers.dev/api?key=OSINTBOT&number={}"
API_URL2       = "https://telegram-to-num-gray.vercel/sms?key=Demo&term={}"
VEHICLE_API    = "https://magical-knives-drum-condo.trycloudflare.com/vehicle-info?vno={}"
BOT_TOKEN      = "8745436475:AAE5FW3TTqeZCPVroJTCIy2W4e3eQVHOAaQ"
BOT_USERNAME   = "DeepTraceRobot"
CUSTOM_NAME    = "@DarkGalaxxyy & @R4HULxTRUSTED"
ADMIN_ID       = 6131370190
MONGO_URI      = "mongodb+srv://saitamauchiha01025_db_user:yMvHQKjjRpFsgDxz@cluster0.fomymln.mongodb.net/?appName=Cluster0"
UPI_ID         = "DarkGalaxxyy@naviaxis"
UPI_QR_LINK    = "https://t.me/jaiwkwkwkkwkwkjwkq/2"
PAYOUT_CHANNEL = -1003579822719

START_CREDITS = 2; REFER_CREDITS = 3; DEDUCTION_CREDITS = 1
MODE = "dual"; UNLIMITED_MODE = False
REFERRAL_COMMISSION_PERCENT = 15; MIN_WITHDRAW = 15

FORCE_CHANNEL_USERNAME = "siee1234"
FORCE_CHANNEL_LINK     = "https://t.me/siee1234"
FORCE_GROUP1_LINK      = "https://t.me/+37LAxYJO4rMxOGY1"
FORCE_GROUP2_ID        = -1003830965397
FORCE_GROUP2_LINK      = "https://t.me/+koTD7TYkHxRhNzY1"

PRESET_PAYMENTS = {"10": 10, "25": 30, "50": 65}
MIN_CUSTOM_AMOUNT = 5
IST = timezone(timedelta(hours=5, minutes=30))

# ══════════════════════════════════════════════
#               MONGODB
# ══════════════════════════════════════════════
client = AsyncIOMotorClient(MONGO_URI, tls=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=10000)
db = client["numbot"]
users = db["users"]; vouchers = db["vouchers"]; orders = db["orders"]
admins = db["admins"]; adminlogs = db["adminlogs"]

# ══════════════════════════════════════════════
#               DATA MANAGEMENT
# ══════════════════════════════════════════════
async def get_user(user_id):
    return await users.find_one({"user_id": user_id})

async def create_user(user_id, referred_by=None, username=None, name=None, force_joined=False):
    ref_code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    user = {
        "user_id": user_id, "credits": START_CREDITS if force_joined else 0,
        "joined": datetime.now(IST).strftime("%Y-%m-%d"), "ref_code": ref_code,
        "referred_by": referred_by, "referrals": 0, "username": username, "name": name,
        "banned": False, "banned_at": None, "force_joined": force_joined,
        "earned_commission": 0, "withdrawn": 0
    }
    await users.insert_one(user)
    if referred_by and force_joined:
        await users.update_one({"user_id": referred_by}, {"$inc": {"credits": REFER_CREDITS, "referrals": 1}})
    return user

async def update_credits(user_id, amount):
    r = await users.find_one_and_update({"user_id": user_id}, {"$inc": {"credits": amount}}, return_document=True)
    return r["credits"] if r else None

async def set_credits(user_id, amount):
    r = await users.update_one({"user_id": user_id}, {"$set": {"credits": amount}})
    return r.modified_count > 0

# ══════════════════════════════════════════════
#               ADMIN HELPERS
# ══════════════════════════════════════════════
async def is_admin(user_id):
    if user_id == ADMIN_ID: return True
    return await admins.find_one({"user_id": user_id}) is not None

async def log_admin_action(admin_id, action, target=None, details=None):
    await adminlogs.insert_one({
        "admin_id": admin_id, "action": action, "target": target, "details": details,
        "time": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    })

# ══════════════════════════════════════════════
#               KEYBOARDS
# ══════════════════════════════════════════════
def get_main_keyboard(user_id, is_admin_user=False):
    kb = [
        [KeyboardButton("🔍 Search Number"),   KeyboardButton("🔎 Search TG Number")],
        [KeyboardButton("🚗 Vehicle Search"),   KeyboardButton("👤 My Account")],
        [KeyboardButton("💰 Credits"),          KeyboardButton("🔗 Refer")],
        [KeyboardButton("💳 Buy Credits"),      KeyboardButton("❓ Help")],
    ]
    if is_admin_user:
        kb.append([KeyboardButton("⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

# ══════════════════════════════════════════════
#               MEMBERSHIP CHECK
# ══════════════════════════════════════════════
async def check_membership(bot, user_id, chat):
    try:
        m = await bot.get_chat_member(chat, user_id)
        return m.status not in ["kicked", "left"]
    except BadRequest as e:
        return "user not found" not in str(e).lower()
    except Exception:
        return True

async def force_join_check(bot, user_id):
    if user_id == ADMIN_ID: return True
    return (await check_membership(bot, user_id, f"@{FORCE_CHANNEL_USERNAME}")
            and await check_membership(bot, user_id, FORCE_GROUP2_ID))

def join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=FORCE_CHANNEL_LINK)],
        [InlineKeyboardButton("👥 Join Group 1", url=FORCE_GROUP1_LINK)],
        [InlineKeyboardButton("👥 Join Group 2", url=FORCE_GROUP2_LINK)],
    ])

# ══════════════════════════════════════════════
#               SECURITY — WEBHOOK PROTECTION
# ══════════════════════════════════════════════
async def post_init(app):
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        print("[SECURITY] Webhook cleared.")
    except Exception as e:
        print(f"[SECURITY] post_init error: {e}")
    asyncio.create_task(webhook_watchdog(app))

async def webhook_watchdog(app):
    while True:
        try:
            info = await app.bot.get_webhook_info()
            if info.url:
                print(f"[SECURITY] Rogue webhook: {info.url} — deleting")
                await app.bot.delete_webhook(drop_pending_updates=True)
        except Exception as e:
            print(f"[SECURITY] watchdog: {e}")
        await asyncio.sleep(30)

# ══════════════════════════════════════════════
#               NON-BLOCKING HTTP + POLLING
# ══════════════════════════════════════════════
async def _blocking_get(url, timeout_sec):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: requests.get(url, timeout=timeout_sec))

async def fetch_api1_with_polling(url, max_attempts=6, wait_seconds=15, per_timeout=30):
    last_raw = ""; last_data = {}
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await _blocking_get(url, per_timeout)
            raw = resp.text.strip(); last_raw = raw
            if not raw:
                if attempt < max_attempts: await asyncio.sleep(wait_seconds); continue
                return ("empty", {}, "", attempt)
            try:
                data = json.loads(raw); last_data = data
            except json.JSONDecodeError:
                if attempt < max_attempts: await asyncio.sleep(wait_seconds); continue
                return ("invalid_json", {}, raw, attempt)

            success = data.get("success")
            msg_raw = (data.get("message") or data.get("msg") or data.get("error") or data.get("detail") or "")
            msg_lower = str(msg_raw).lower()
            results = data.get("results") or data.get("result") or []

            if success is True:
                return ("success", data, raw, attempt) if results else ("not_found", data, raw, attempt)

            processing_kw = ["processing","please wait","retry","queued","in progress","try again",
                             "loading","being fetched","fetching","on the way","wait for","please retry","still"]
            if any(k in msg_lower for k in processing_kw):
                if attempt < max_attempts: await asyncio.sleep(wait_seconds); continue
                return ("processing_timeout", data, raw, attempt)

            not_found_kw = ["not found","no record","no data","no result","invalid number",
                            "not exist","no information","not available"]
            if any(k in msg_lower for k in not_found_kw):
                return ("not_found", data, raw, attempt)

            if results: return ("success", data, raw, attempt)
            if attempt < max_attempts: await asyncio.sleep(wait_seconds); continue
            return ("unknown", data, raw, attempt)
        except requests.exceptions.Timeout:
            if attempt < max_attempts: await asyncio.sleep(wait_seconds); continue
            return ("http_timeout", {}, last_raw, attempt)
        except requests.exceptions.ConnectionError:
            if attempt < max_attempts: await asyncio.sleep(wait_seconds); continue
            return ("connection_error", {}, last_raw, attempt)
        except Exception as e:
            if attempt < max_attempts: await asyncio.sleep(wait_seconds); continue
            return ("unknown", {"exception": str(e)}, last_raw, attempt)
    return ("unknown", last_data, last_raw, max_attempts)

# ══════════════════════════════════════════════
#               START
# ══════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    name = update.effective_user.full_name
    bot = context.bot

    referred_by = None
    if context.args and context.args[0].startswith("ref_"):
        ref_code = context.args[0][4:]
        ref = await users.find_one({"ref_code": ref_code})
        if ref and ref["user_id"] != user_id: referred_by = ref["user_id"]

    user = await get_user(user_id)
    if user is None:
        user = await create_user(user_id, referred_by, username, name, force_joined=False)
    else:
        await users.update_one({"user_id": user_id}, {"$set": {"username": username, "name": name}})

    if user.get("banned"):
        await update.message.reply_text("<b>🚫 Access Denied</b>\n\nYou have been banned.\nContact @DarkGalaxxyy.",
                                        parse_mode="HTML"); return

    if not await force_join_check(bot, user_id):
        await update.message.reply_text(
            "╔══════════════════════╗\n        🔐 <b>ACCESS RESTRICTED</b>\n╚══════════════════════╝\n\n"
            "To use this bot, you must join\nall of the following:\n\n"
            "📢 Official Channel\n👥 Group 1  •  👥 Group 2\n\nAfter joining, send /start again ↩️",
            parse_mode="HTML", reply_markup=join_keyboard()); return

    if not user.get("force_joined"):
        final_ref = referred_by or user.get("referred_by")
        await users.update_one({"user_id": user_id},
                               {"$set": {"force_joined": True}, "$inc": {"credits": START_CREDITS}})
        if final_ref and final_ref != user_id:
            await users.update_one({"user_id": final_ref}, {"$inc": {"credits": REFER_CREDITS, "referrals": 1}})
        is_new = True; user = await get_user(user_id)
    else:
        is_new = False

    links_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Channel", url=FORCE_CHANNEL_LINK),
         InlineKeyboardButton("👥 Group 1", url=FORCE_GROUP1_LINK)],
        [InlineKeyboardButton("👥 Group 2", url=FORCE_GROUP2_LINK)],
    ])
    welcome = (f"🎊 <b>Welcome aboard, {name}!</b>\n\n🎁 You've received <b>{START_CREDITS} free credits</b>!\n\n"
               if is_new else f"👋 <b>Welcome back, {name}!</b>\n\n")
    unlimited_note = "♾️ <b>Unlimited Mode is ON</b> — searches are free!\n\n" if UNLIMITED_MODE else ""
    msg = (f"{welcome}{unlimited_note}"
           "━━━━━━━━━━━━━━━━━━━━\n🔍 <b>DeepTrace</b> — Fetch detailed info about any mobile number instantly.\n"
           "━━━━━━━━━━━━━━━━━━━━\n\n📌 <b>Available APIs & Commands</b>\n\n"
           "<code>/num &lt;number&gt;</code> — Mobile Number Info (API 1)\n"
           "<code>/tgnum &lt;number&gt;</code> — Telegram UID Lookup (API 2)\n"
           "<code>/vehicle &lt;reg_no&gt;</code> — Vehicle Registration Info 🚗\n"
           "<code>/referstat</code> — Refer leaderboard\n"
           "<code>/redeem &lt;code&gt;</code> — Redeem voucher\n\n"
           "💡 Use the buttons below to navigate.")
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=links_kb)
    await update.message.reply_text("🗂 <b>Main Menu</b>", parse_mode="HTML",
                                    reply_markup=get_main_keyboard(user_id, await is_admin(user_id)))

def insufficient_credits_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Buy Credits", callback_data="credits_buy"),
         InlineKeyboardButton("🔗 Refer", callback_data="credits_refer")]
    ])

# ══════════════════════════════════════════════
#               PROCESS NUMBER
# ══════════════════════════════════════════════
async def process_number(update, context, number, api_num=1):
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    bot = context.bot

    if MODE == "maintenance":
        await update.message.reply_text("<b>🔧 Maintenance Mode</b>", parse_mode="HTML"); return
    if MODE == "group" and chat_type == "private":
        await update.message.reply_text("⚠️ This bot only works in groups."); return
    if MODE == "private" and chat_type in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ This bot only works in private chat."); return

    if not await force_join_check(bot, user_id):
        await update.message.reply_text("⚠️ <b>Access Restricted</b>", parse_mode="HTML", reply_markup=join_keyboard()); return

    user = await get_user(user_id) or await create_user(user_id)
    if user.get("banned"):
        await update.message.reply_text("🚫 Banned."); return
    if not UNLIMITED_MODE and user["credits"] <= 0:
        await update.message.reply_text(
            "❌ <b>Insufficient Credits</b>\n\nYou have <b>0 credits</b> remaining.\n\n"
            "💡 Earn credits: Refer, Redeem voucher, or Buy.",
            parse_mode="HTML", reply_markup=insufficient_credits_kb()); return

    await update.message.reply_text(
        f"🔍 <b>Searching for the number</b> <code>{number}</code>...\n"
        "⏳ <i>Please wait, this may take up to 2 minutes.</i>", parse_mode="HTML")

    if api_num == 1:
        url = API_URL.format(number)
        if not url.startswith("http"): url = "https://" + url
    else:
        url = API_URL2.format(number)

    # ════════ API 1 — POLLING ════════
    if api_num == 1:
        status, data, raw, attempts = await fetch_api1_with_polling(url, 6, 15, 30)
        if status == "success":
            if not data.get("success"): data["success"] = True
            data["credit"] = {"name": "Dark Galaxy", "developer": "@DarkGalaxxyy",
                              "contact": "@DarkGalaxxyy", "footer": "Powered by @Siee1234"}
            if "tag" in data: data["tag"] = "@DarkGalaxxyy"
            if UNLIMITED_MODE:
                credit_note = "♾️ <i>Unlimited — no credits deducted</i>"
            else:
                nb = await update_credits(user_id, -DEDUCTION_CREDITS)
                credit_note = f"💰 <i>Credits remaining: {nb}</i>"
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
            total = data.get("total_results", len(data.get("results", [])))
            summary = (f"📞 <b>Number Search Result</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                       f"🔢 Number: <code>{number}</code>\n📊 Records found: <b>{total}</b>\n\n{credit_note}")
            fb = BytesIO(pretty.encode("utf-8")); fb.name = f"{number}.txt"
            await bot.send_document(chat_id=update.effective_chat.id, document=fb, caption=summary, parse_mode="HTML")
            return

        if status == "not_found":
            m = data.get("message") or data.get("msg") or "No records found."
            await update.message.reply_text(f"❌ <b>No Result Found</b>\n\n<b>API says:</b> {m}", parse_mode="HTML"); return
        if status == "processing_timeout":
            m = data.get("message") or data.get("msg") or "Still processing"
            await update.message.reply_text(
                f"⏱ <b>API Still Processing</b>\n\nTried <b>{attempts}</b> times.\n\n"
                f"<b>Last message:</b> {m}\n\n<i>Try again in a minute.</i>", parse_mode="HTML"); return
        if status == "http_timeout":
            await update.message.reply_text("⏱ <b>API Timeout</b>\n\nPlease try again.", parse_mode="HTML"); return
        if status == "connection_error":
            await update.message.reply_text("📡 <b>Connection Error</b>", parse_mode="HTML"); return
        if status == "empty":
            await update.message.reply_text("❌ <b>Empty Response</b>", parse_mode="HTML"); return
        if status == "invalid_json":
            excerpt = (raw[:500] + "…") if len(raw) > 500 else raw
            await update.message.reply_text(
                f"❌ <b>Invalid API Response</b>\n\n<code>{excerpt}</code>", parse_mode="HTML"); return
        excerpt = (raw[:500] + "…") if len(raw) > 500 else raw
        m = data.get("message") or data.get("msg") or data.get("error") or "(no message)"
        await update.message.reply_text(
            f"❌ <b>Unexpected Response</b>\n\n<b>Message:</b> {m}\n\n<code>{excerpt}</code>",
            parse_mode="HTML"); return

    # ════════ API 2 — SINGLE REQUEST ════════
    try:
        resp = await _blocking_get(url, 15)
        result = resp.text.strip()
    except requests.exceptions.Timeout:
        await update.message.reply_text("⏱ <b>Timeout</b>", parse_mode="HTML"); return
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("📡 <b>Connection Error</b>", parse_mode="HTML"); return
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}"); return

    if not result:
        await update.message.reply_text("❌ <b>No Result Found</b>", parse_mode="HTML"); return
    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        await update.message.reply_text(f"❌ <b>Invalid API Response</b>\n\n<code>{result[:500]}</code>",
                                        parse_mode="HTML"); return

    if data.get("status") == False and "Daily limit exceeded" in data.get("error", ""):
        await update.message.reply_text("❌ <b>TG API Limit Reached</b>\n\n<i>No credits deducted.</i>", parse_mode="HTML"); return
    if data.get("success") == False:
        m = data.get("msg", "")
        if "not found" in m.lower():
            await update.message.reply_text(f"❌ <b>TG Lookup Failed</b>\n\n{m}\n\n<i>No credits deducted.</i>", parse_mode="HTML"); return
    r = data.get("result", {})
    if r.get("status") == False:
        err = r.get("error", "") or r.get("msg", "")
        if "not found" in err.lower() or "wait" in err.lower():
            await update.message.reply_text(f"❌ <b>TG Lookup Failed</b>\n\n{err}\n\n<i>No credits deducted.</i>", parse_mode="HTML"); return

    if "tag" in data: data["tag"] = "@DarkGalaxxyy"
    if UNLIMITED_MODE:
        credit_note = "♾️ <i>Unlimited</i>"
    else:
        nb = await update_credits(user_id, -DEDUCTION_CREDITS)
        credit_note = f"💰 <i>Credits remaining: {nb}</i>"
    pretty = json.dumps(data, indent=2, ensure_ascii=False)
    summary = f"🔎 <b>TG Search Result</b>\n━━━━━━━━━━━━━━━━━━━━\n{credit_note}"
    fb = BytesIO(pretty.encode("utf-8")); fb.name = f"{number}.txt"
    await bot.send_document(chat_id=update.effective_chat.id, document=fb, caption=summary, parse_mode="HTML")

async def num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📌 <b>Usage:</b> <code>/num &lt;number&gt;</code>", parse_mode="HTML"); return
    await process_number(update, context, context.args[0], api_num=1)

async def tgnum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📌 <b>Usage:</b> <code>/tgnum &lt;number&gt;</code>", parse_mode="HTML"); return
    await process_number(update, context, context.args[0], api_num=2)

# ══════════════════════════════════════════════
#               VEHICLE SEARCH
# ══════════════════════════════════════════════
async def process_vehicle(update, context, rc_number):
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    bot = context.bot
    if MODE == "maintenance":
        await update.message.reply_text("<b>🔧 Maintenance Mode</b>", parse_mode="HTML"); return
    if MODE == "group" and chat_type == "private":
        await update.message.reply_text("⚠️ Only groups."); return
    if MODE == "private" and chat_type in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Only private chat."); return
    if not await force_join_check(bot, user_id):
        await update.message.reply_text("⚠️ <b>Access Restricted</b>", parse_mode="HTML", reply_markup=join_keyboard()); return
    user = await get_user(user_id) or await create_user(user_id)
    if user.get("banned"):
        await update.message.reply_text("🚫 Banned."); return
    if not UNLIMITED_MODE and user["credits"] <= 0:
        await update.message.reply_text("❌ <b>Insufficient Credits</b>", parse_mode="HTML",
                                        reply_markup=insufficient_credits_kb()); return
    try:
        url = VEHICLE_API.format(rc_number.upper())
        resp = await _blocking_get(url, 15)
        data = resp.json()
        values = [v for k, v in data.items() if k != "copyright"]
        non_null = [v for v in values if v not in (None, "NA", "")]
        if not non_null:
            await update.message.reply_text("❌ <b>No Result Found</b>", parse_mode="HTML"); return
        if UNLIMITED_MODE:
            credit_note = "♾️ <i>Unlimited</i>"
        else:
            nb = await update_credits(user_id, -DEDUCTION_CREDITS)
            credit_note = f"💰 <i>Credits remaining: {nb}</i>"
        if "tag" in data: data["tag"] = "@DarkGalaxxyy"
        pretty = json.dumps(data, indent=2, ensure_ascii=False)
        summary = f"🚗 <b>Vehicle Result</b>\n🔖 <code>{rc_number}</code>\n\n{credit_note}"
        fb = BytesIO(pretty.encode("utf-8")); fb.name = f"{rc_number}.txt"
        await bot.send_document(chat_id=update.effective_chat.id, document=fb, caption=summary, parse_mode="HTML")
    except requests.exceptions.Timeout:
        await update.message.reply_text("⏱ <b>Timeout</b>", parse_mode="HTML")
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("📡 <b>Connection Error</b>", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📌 <b>Usage:</b> <code>/vehicle &lt;reg_no&gt;</code>", parse_mode="HTML"); return
    await process_vehicle(update, context, context.args[0])

# ══════════════════════════════════════════════
#               /id (ADMIN)
# ══════════════════════════════════════════════
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only."); return
    if not context.args:
        await update.message.reply_text("📌 Usage: /id @username"); return
    username = context.args[0].lstrip('@')
    try:
        chat = await context.bot.get_chat(f"@{username}")
        await update.message.reply_text(
            f"🆔 <b>@{username}:</b> <code>{chat.id}</code>\n👤 {chat.full_name or 'N/A'}", parse_mode="HTML")
    except BadRequest as e:
        await update.message.reply_text(f"❌ {e.message}", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

# ══════════════════════════════════════════════
#               BAN / UNBAN / BANLIST
# ══════════════════════════════════════════════
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("📌 /ban <uid>"); return
    uid = int(context.args[0])
    r = await users.update_one({"user_id": uid},
                               {"$set": {"banned": True, "banned_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")}})
    if r.modified_count:
        await log_admin_action(update.effective_user.id, "ban", uid, f"Banned {uid}")
        await update.message.reply_text(f"🚫 <code>{uid}</code> banned.", parse_mode="HTML")
        try: await context.bot.send_message(uid, "🚫 You have been banned.")
        except: pass
    else:
        await update.message.reply_text("❌ Not found.")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("📌 /unban <uid>"); return
    uid = int(context.args[0])
    r = await users.update_one({"user_id": uid}, {"$set": {"banned": False, "banned_at": None}})
    if r.modified_count:
        await log_admin_action(update.effective_user.id, "unban", uid, f"Unbanned {uid}")
        await update.message.reply_text(f"✅ <code>{uid}</code> unbanned.", parse_mode="HTML")
        try: await context.bot.send_message(uid, "✅ You have been unbanned!")
        except: pass
    else:
        await update.message.reply_text("❌ Not found.")

async def banusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    lst = await users.find({"banned": True}).to_list(length=100)
    if not lst:
        await update.message.reply_text("✅ No banned users."); return
    msg = "🚫 <b>Banned Users</b>\n\n"
    for u in lst:
        name = u.get("name") or f"User {u['user_id']}"
        msg += f'🆔 <a href="tg://user?id={u["user_id"]}">{name}</a> (<code>{u["user_id"]}</code>)\n📅 {u.get("banned_at","?")}\n\n'
    await update.message.reply_text(msg, parse_mode="HTML")

# ══════════════════════════════════════════════
#               CHECK USER
# ══════════════════════════════════════════════
async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("📌 /check <uid>"); return
    uid = int(context.args[0])
    user = await get_user(uid)
    if not user:
        await update.message.reply_text("❌ Not found."); return
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user['ref_code']}"
    uname = f"@{user['username']}" if user.get("username") else "No username"
    name = user.get("name") or "Unknown"
    ref_text = "None"
    if user.get("referred_by"):
        ru = await get_user(user["referred_by"])
        ref_text = f'<a href="tg://user?id={ru["user_id"]}">{ru.get("name","?")}</a>' if ru else "Unknown"
    referred = await users.find({"referred_by": uid}, {"username":1,"user_id":1,"name":1}).to_list(length=100)
    ref_list = "".join(f'  • <a href="tg://user?id={r["user_id"]}">{r.get("name","?")}</a>\n' for r in referred)
    msg = (f"👤 <b>User Details</b>\n\n📛 <a href='tg://user?id={uid}'>{name}</a>\n"
           f"🔖 {uname}\n🆔 <code>{uid}</code>\n💰 {user['credits']}\n"
           f"💸 ₹{user.get('earned_commission',0)}\n🏧 ₹{user.get('withdrawn',0)}\n"
           f"📅 {user['joined']}\n👥 {user['referrals']}\n🔗 Referred By: {ref_text}\n"
           f"🚫 Banned: {'Yes' if user.get('banned') else 'No'}\n🔗 <a href='{ref_link}'>Refer Link</a>\n")
    msg += f"\n👥 Referred:\n{ref_list}" if ref_list else "\n👥 Referred: None"
    await update.message.reply_text(msg, parse_mode="HTML")

# ══════════════════════════════════════════════
#               MSG USER / REFER LIST / LEADERBOARD
# ══════════════════════════════════════════════
async def msg_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("📌 /msg <uid> <msg>"); return
    uid = int(context.args[0]); message = " ".join(context.args[1:])
    if not await get_user(uid):
        await update.message.reply_text("❌ Not found."); return
    try:
        await context.bot.send_message(uid, message)
        await update.message.reply_text(f"✅ Sent to <code>{uid}</code>", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def referlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    lst = await users.find({"referrals":{"$gt":0},"user_id":{"$ne":ADMIN_ID}},
                           {"username":1,"user_id":1,"referrals":1,"name":1}).sort("referrals",-1).to_list(length=100)
    if not lst:
        await update.message.reply_text("None."); return
    msg = "📋 <b>Full Refer List</b>\n\n"
    for i, u in enumerate(lst, 1):
        msg += f'{i}. <a href="tg://user?id={u["user_id"]}">{u.get("name","?")}</a> — {u["referrals"]}\n'
    await update.message.reply_text(msg, parse_mode="HTML")

async def referstat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lst = await users.find({"referrals":{"$gt":0},"user_id":{"$ne":ADMIN_ID}},
                           {"username":1,"user_id":1,"referrals":1,"name":1}).sort("referrals",-1).to_list(length=500)
    if not lst:
        await update.message.reply_text("🔗 No referrals yet!"); return
    medals = ["🥇","🥈","🥉"]
    msg = "🏆 <b>Refer Leaderboard</b>\n\n"
    for i, u in enumerate(lst):
        medal = medals[i] if i < 3 else f"{i+1}."
        msg += f'{medal} <a href="tg://user?id={u["user_id"]}">{u.get("name","?")}</a> — <b>{u["referrals"]}</b>\n'
    await update.message.reply_text(msg, parse_mode="HTML")

# ══════════════════════════════════════════════
#               VOUCHERS
# ══════════════════════════════════════════════
async def createvoucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 3:
        await update.message.reply_text("📌 /createvoucher <code> <credits> <uses>"); return
    code = context.args[0].upper(); credits = int(context.args[1]); max_uses = int(context.args[2])
    if await vouchers.find_one({"code": code}):
        await update.message.reply_text(f"❌ Exists."); return
    await vouchers.insert_one({"code":code,"credits":credits,"max_uses":max_uses,"uses":0,"used_by":[]})
    await log_admin_action(update.effective_user.id, "createvoucher", None, f"{code} x{credits}")
    await update.message.reply_text(f"🎟️ <b>Created!</b>\n<code>{code}</code> — {credits} credits, {max_uses} uses",
                                    parse_mode="HTML")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await force_join_check(context.bot, user_id):
        await update.message.reply_text("⚠️ Join channels first.", reply_markup=join_keyboard()); return
    if not context.args:
        await update.message.reply_text("📌 /redeem <code>"); return
    code = context.args[0].upper()
    v = await vouchers.find_one({"code": code})
    if not v: await update.message.reply_text("❌ Invalid."); return
    if v["uses"] >= v["max_uses"]: await update.message.reply_text("❌ Expired."); return
    if user_id in v["used_by"]: await update.message.reply_text("❌ Already used."); return
    await vouchers.update_one({"code": code}, {"$inc": {"uses": 1}, "$push": {"used_by": user_id}})
    nb = await update_credits(user_id, v["credits"])
    await update.message.reply_text(f"🎉 +{v['credits']} credits! Balance: <b>{nb}</b>", parse_mode="HTML")

async def deletevoucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("📌 /deletevoucher <code>"); return
    code = context.args[0].upper()
    r = await vouchers.delete_one({"code": code})
    if r.deleted_count: await log_admin_action(update.effective_user.id, "deletevoucher", None, code)
    await update.message.reply_text(f"✅ Deleted." if r.deleted_count else "❌ Not found.")

async def listvouchers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    lst = await vouchers.find({}).to_list(length=50)
    if not lst: await update.message.reply_text("None."); return
    msg = "🎟️ <b>Vouchers</b>\n\n"
    for v in lst:
        msg += f"<code>{v['code']}</code> — {v['credits']}c — {v['uses']}/{v['max_uses']}\n"
    await update.message.reply_text(msg, parse_mode="HTML")

# ══════════════════════════════════════════════
#               BUY CREDITS
# ══════════════════════════════════════════════
async def buy_credits_menu(update, context):
    kb = [
        [InlineKeyboardButton("₹10 → 10 Credits", callback_data="buy_preset_10")],
        [InlineKeyboardButton("₹25 → 30 Credits", callback_data="buy_preset_25")],
        [InlineKeyboardButton("₹50 → 65 Credits", callback_data="buy_preset_50")],
        [InlineKeyboardButton("💰 Custom Amount", callback_data="buy_custom")],
    ]
    await update.message.reply_text(
        "💳 <b>Buy Credits</b>\n\n💵 <b>Select:</b>\n\n✨ Bonus on higher packs!\n\n🚫 <b>Credits non-refundable</b>",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def process_payment(update, query, amount, credits):
    user_id = query.from_user.id
    order_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    await orders.insert_one({"order_id":order_id,"user_id":user_id,"amount":amount,"credits":credits,
                             "status":"pending","type":"buy",
                             "created":datetime.now(IST).strftime("%Y-%m-%d %H:%M")})
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Paid", callback_data=f"paid_{order_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")],
        [InlineKeyboardButton("🔙 Back", callback_data="buy_menu_back")]
    ])
    await query.message.delete()
    await query.message.reply_photo(
        photo=UPI_QR_LINK,
        caption=(f"📱 <b>UPI Payment</b>\n\n💵 ₹{amount}\n💰 {credits} credits\n\n"
                 f"🏦 <code>{UPI_ID}</code>\n\n<i>Scan QR then tap I've Paid</i>\n\n🔖 <code>{order_id}</code>"),
        parse_mode="HTML", reply_markup=kb)

# ══════════════════════════════════════════════
#               CALLBACKS
# ══════════════════════════════════════════════
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; data = query.data; user_id = query.from_user.id
    await query.answer()

    if data.startswith("buy_preset_"):
        key = data.split("_")[2]
        if key not in PRESET_PAYMENTS:
            await query.answer("Invalid.", show_alert=True); return
        await process_payment(update, query, int(key), PRESET_PAYMENTS[key]); return

    if data == "buy_custom":
        context.user_data["upi_custom"] = True
        await query.message.edit_text(
            "💰 <b>Custom Amount</b>\n\nEnter amount in ₹:\n<i>Min: ₹5</i>\n\nExample: <code>50</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]]))
        return

    if data == "credits_refer":
        u = await get_user(user_id) or await create_user(user_id)
        ref = f"https://t.me/{BOT_USERNAME}?start=ref_{u['ref_code']}"
        msg = (f"🔗 <b>Refer & Earn</b>\n\n🔗 <code>{ref}</code>\n\n"
               f"💰 {REFER_CREDITS}c/refer\n👥 {u['referrals']}\n💸 ₹{u.get('earned_commission',0)}\n"
               f"🏧 Min withdraw: ₹{MIN_WITHDRAW}")
        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw_start")]]))
        return

    if data == "credits_buy":
        await buy_credits_menu(query, context); return

    if data == "withdraw_start":
        u = await get_user(user_id)
        if not u: await query.answer("Not found.", show_alert=True); return
        if u.get("earned_commission", 0) < MIN_WITHDRAW:
            await query.answer(f"Min ₹{MIN_WITHDRAW}. You have ₹{u.get('earned_commission',0)}.", show_alert=True); return
        context.user_data["withdraw_step"] = "amount"
        await query.message.reply_text(
            f"💸 <b>Withdraw</b>\n\nBalance: ₹{u.get('earned_commission',0)}\nMin: ₹{MIN_WITHDRAW}\n\nEnter amount:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]]))
        return

    if data == "cancel_withdraw":
        for k in ("withdraw_step","withdraw_amount","withdraw_bank_name","withdraw_account_name","withdraw_upi"):
            context.user_data.pop(k, None)
        try: await query.message.edit_text("❌ Cancelled.", reply_markup=None)
        except: pass
        return

    if data == "buy_menu_back":
        await query.message.delete(); await buy_credits_menu(query, context); return

    if data == "cancel_search":
        context.user_data.pop("waiting_for_number", None); context.user_data.pop("waiting_for_vehicle", None)
        try: await query.message.edit_text("❌ Cancelled.", parse_mode="HTML", reply_markup=None)
        except: pass
        return

    if data == "cancel_payment":
        context.user_data.pop("upi_custom", None)
        try: await query.message.edit_text("❌ Cancelled.", parse_mode="HTML", reply_markup=None)
        except: pass
        return

    if data.startswith("paid_"):
        oid = data.split("_", 1)[1]
        order = await orders.find_one({"order_id": oid})
        if not order: await query.answer("Not found.", show_alert=True); return
        if order.get("submitted"): await query.answer("Already submitted!", show_alert=True); return
        await orders.update_one({"order_id": oid}, {"$set": {"submitted": True}})
        username = query.from_user.username; name = query.from_user.full_name
        amount = order["amount"]; credits = order["credits"]
        uname = f"@{username}" if username else name or f"User {user_id}"
        payout_msg = (f"💳 <b>New Payment Order</b>\n\n📛 {name}\n👤 {uname}\n🆔 <code>{user_id}</code>\n"
                      f"💵 ₹{amount}\n💰 {credits} credits\n📊 Pending ⏳\n\n🔖 <code>{oid}</code>")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Done", callback_data=f"done_{oid}_{user_id}_{credits}"),
                                     InlineKeyboardButton("❌ Cancel", callback_data=f"cancelorder_{oid}_{user_id}")]])
        try:
            await context.bot.send_message(PAYOUT_CHANNEL, payout_msg, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            await query.answer(f"❌ Failed: {str(e)}", show_alert=True)
            await orders.update_one({"order_id": oid}, {"$set": {"submitted": False}}); return
        txt = f"✅ <b>Submitted!</b>\n\nOrder: <code>{oid}</code>\n<i>Wait for verification.</i>"
        try: await query.message.edit_caption(txt, parse_mode="HTML", reply_markup=None)
        except: pass
        return

    if data.startswith("done_"):
        parts = data.split("_"); oid = parts[1]; uid = int(parts[2]); credits = int(parts[3])
        await update_credits(uid, credits)
        await orders.update_one({"order_id": oid}, {"$set": {"status": "done"}})
        order = await orders.find_one({"order_id": oid})
        if order and order.get("type", "buy") == "buy":
            buyer = await get_user(uid)
            if buyer and buyer.get("referred_by"):
                ref_uid = buyer["referred_by"]
                comm = int(order["amount"] * REFERRAL_COMMISSION_PERCENT / 100)
                if comm > 0:
                    await users.update_one({"user_id": ref_uid}, {"$inc": {"earned_commission": comm}})
                    try:
                        await context.bot.send_message(ref_uid,
                            f"🎉 <b>Commission!</b>\n\nYour referral <a href='tg://user?id={uid}'>{buyer.get('name','User')}</a> purchased.\n"
                            f"You earned ₹{comm}!", parse_mode="HTML")
                    except: pass
        new_text = query.message.text.replace("📊 Pending ⏳", "📊 Done ✅")
        try: await query.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
        except: pass
        try:
            await context.bot.send_message(uid, f"🎉 <b>Approved!</b>\n\n+{credits} credits!", parse_mode="HTML")
        except: pass
        return

    if data.startswith("withdrawdone_"):
        parts = data.split("_"); oid = parts[1]; uid = int(parts[2]); amount = int(parts[3])
        await orders.update_one({"order_id": oid}, {"$set": {"status": "done"}})
        await users.update_one({"user_id": uid}, {"$inc": {"earned_commission": -amount, "withdrawn": amount}})
        new_text = query.message.text.replace("📊 Pending ⏳", "📊 Done ✅")
        try: await query.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
        except: pass
        order = await orders.find_one({"order_id": oid})
        upi = order.get("upi_id", "N/A") if order else "N/A"
        try:
            await context.bot.send_message(uid,
                f"✅ <b>Withdrawn!</b>\n\n₹{amount}\nTo: <code>{upi}</code>\n\nThanks!", parse_mode="HTML")
        except: pass
        return

    if data.startswith("cancelwithdraworder_") or data.startswith("cancelorder_"):
        parts = data.split("_"); oid = parts[1]
        uid = int(parts[-1]) if data.startswith("cancelwithdraworder_") else int(parts[2])
        await orders.update_one({"order_id": oid}, {"$set": {"status": "cancelled"}})
        new_text = query.message.text.replace("📊 Pending ⏳", "📊 Cancelled ❌")
        try: await query.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
        except: pass
        try: await context.bot.send_message(uid, "❌ Order cancelled. Contact @DarkGalaxxyy")
        except: pass
        return

    if data == "refresh_stats":
        if user_id != ADMIN_ID: return
        tu = await users.count_documents({}); ju = await users.count_documents({"force_joined": True})
        tc = sum([u["credits"] async for u in users.find({}, {"credits": 1})])
        tv = await vouchers.count_documents({})
        new_text = (f"📊 <b>Stats</b>\n\n👤 {tu}\n✅ {ju}\n⏳ {tu-ju}\n\n"
                    f"💰 {tc}\n🔧 <code>{MODE}</code>\n♾️ {'ON' if UNLIMITED_MODE else 'OFF'}\n"
                    f"🎁 {START_CREDITS}\n🔗 {REFER_CREDITS}\n🎟️ {tv}")
        try: await query.message.edit_text(new_text, parse_mode="HTML",
                                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄", callback_data="refresh_stats")]]))
        except: pass

# ══════════════════════════════════════════════
#               BUTTON HANDLERS
# ══════════════════════════════════════════════
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text; user_id = update.effective_user.id; bot = context.bot

    if context.user_data.get("withdraw_step"):
        step = context.user_data["withdraw_step"]
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]])
        if step == "amount":
            if text.isdigit():
                amt = int(text); u = await get_user(user_id)
                if amt > u.get("earned_commission", 0) or amt < MIN_WITHDRAW:
                    await update.message.reply_text(f"❌ Must be ₹{MIN_WITHDRAW}-₹{u.get('earned_commission',0)}", reply_markup=cancel_kb); return
                context.user_data["withdraw_amount"] = amt
                context.user_data["withdraw_step"] = "bank_name"
                await update.message.reply_text("🏦 Bank Name:", reply_markup=cancel_kb)
            else:
                await update.message.reply_text("❌ Invalid.", reply_markup=cancel_kb)
            return
        if step == "bank_name":
            context.user_data["withdraw_bank_name"] = text
            context.user_data["withdraw_step"] = "account_name"
            await update.message.reply_text("📛 Account Name:", reply_markup=cancel_kb); return
        if step == "account_name":
            context.user_data["withdraw_account_name"] = text
            context.user_data["withdraw_step"] = "upi"
            await update.message.reply_text("📱 UPI ID:", reply_markup=cancel_kb); return
        if step == "upi":
            upi = text.strip()
            if not upi:
                await update.message.reply_text("❌ Invalid."); return
            context.user_data["withdraw_upi"] = upi
            amt = context.user_data["withdraw_amount"]; bank = context.user_data["withdraw_bank_name"]
            acc = context.user_data["withdraw_account_name"]
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Confirm", callback_data="confirm_withdraw"),
                                         InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]])
            await update.message.reply_text(
                f"💸 <b>Confirm</b>\n\n₹{amt}\n🏦 {bank}\n📛 {acc}\n📱 <code>{upi}</code>",
                parse_mode="HTML", reply_markup=kb)
            context.user_data.pop("withdraw_step")
            return
        return

    if context.user_data.get("upi_custom"):
        if text.isdigit() and int(text) >= MIN_CUSTOM_AMOUNT:
            amt = int(text); oid = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            context.user_data.pop("upi_custom")
            await orders.insert_one({"order_id":oid,"user_id":user_id,"amount":amt,"credits":amt,
                                     "status":"pending","type":"buy",
                                     "created":datetime.now(IST).strftime("%Y-%m-%d %H:%M")})
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ I've Paid", callback_data=f"paid_{oid}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")],
                [InlineKeyboardButton("🔙 Back", callback_data="buy_menu_back")]])
            await update.message.reply_photo(
                photo=UPI_QR_LINK,
                caption=(f"📱 <b>UPI Payment</b>\n\n💵 ₹{amt}\n💰 {amt} credits\n\n"
                         f"🏦 <code>{UPI_ID}</code>\n\n🔖 <code>{oid}</code>"),
                parse_mode="HTML", reply_markup=kb)
        else:
            await update.message.reply_text(f"❌ Min ₹{MIN_CUSTOM_AMOUNT}.")
        return

    if text == "🔍 Search Number":
        if not await force_join_check(bot, user_id):
            await update.message.reply_text("⚠️ Join channels.", reply_markup=join_keyboard()); return
        context.user_data["waiting_for_number"] = 1
        await update.message.reply_text(
            "🔍 <b>Number Search — API 1</b>\n\nEnter number (digits only):\n\nExample: <code>9876543210</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_search")]]))
        return

    if text == "🔎 Search TG Number":
        if not await force_join_check(bot, user_id):
            await update.message.reply_text("⚠️ Join channels.", reply_markup=join_keyboard()); return
        context.user_data["waiting_for_number"] = 2
        await update.message.reply_text(
            "🔎 <b>Search TG Number</b>\n\nEnter User ID or Username:\n\nExample: <code>6116093010</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_search")]]))
        return

    if text == "🚗 Vehicle Search":
        if not await force_join_check(bot, user_id):
            await update.message.reply_text("⚠️ Join channels.", reply_markup=join_keyboard()); return
        context.user_data["waiting_for_vehicle"] = True
        await update.message.reply_text(
            "🚗 <b>Vehicle Search</b>\n\nEnter reg number:\n\nExample: <code>UP78AB1234</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_search")]]))
        return

    if context.user_data.get("waiting_for_vehicle"):
        context.user_data.pop("waiting_for_vehicle")
        rc = text.strip().upper()
        if rc: await process_vehicle(update, context, rc)
        else: await update.message.reply_text("❌ Invalid.")
        return

    if context.user_data.get("waiting_for_number"):
        api_num = context.user_data.pop("waiting_for_number")
        clean = text.strip().lstrip("@")
        if api_num == 1:
            if text.isdigit(): await process_number(update, context, text, api_num=1)
            else: await update.message.reply_text("❌ Invalid input.")
        else:
            if clean: await process_number(update, context, clean, api_num=2)
            else: await update.message.reply_text("❌ Invalid input.")
        return

    if text == "👤 My Account":
        u = await get_user(user_id) or await create_user(user_id)
        note = "\n♾️ <i>Unlimited ON</i>" if UNLIMITED_MODE else ""
        await update.message.reply_text(
            f"👤 <b>My Account</b>\n\n🆔 <code>{user_id}</code>\n💰 <b>{u['credits']}</b>{note}\n"
            f"💸 ₹{u.get('earned_commission',0)}\n📅 {u['joined']}\n👥 {u['referrals']}\n\n"
            f"🚫 <b>Credits non-refundable</b>", parse_mode="HTML")
        return

    if text == "💰 Credits":
        u = await get_user(user_id) or await create_user(user_id)
        note = "\n♾️ <i>Unlimited ON</i>" if UNLIMITED_MODE else ""
        msg = (f"💰 <b>Credits</b>\n\n💳 <b>Balance:</b> <code>{u['credits']}</code>{note}\n\n"
               f"Cost: <b>{DEDUCTION_CREDITS}</b>/search\n\n"
               f"📌 <b>Earn credits:</b>\n🎁 {START_CREDITS} free (new users)\n"
               f"🔗 {REFER_CREDITS}/refer\n🎟️ <code>/redeem</code> (vouchers in @siee1234)\n"
               f"💳 Buy: ₹1 = 1 credit\n🚫 <b>Non-refundable</b>")
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Refer", callback_data="credits_refer"),
             InlineKeyboardButton("💳 Buy", callback_data="credits_buy")]]))
        return

    if text == "🔗 Refer":
        u = await get_user(user_id) or await create_user(user_id)
        ref = f"https://t.me/{BOT_USERNAME}?start=ref_{u['ref_code']}"
        msg = (f"🔗 <b>Refer & Earn</b>\n\n🔗 <code>{ref}</code>\n\n"
               f"💰 {REFER_CREDITS}c/refer\n👥 {u['referrals']}\n💸 ₹{u.get('earned_commission',0)}\n"
               f"🏧 Min withdraw: ₹{MIN_WITHDRAW}")
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw_start")]]))
        return

    if text == "💳 Buy Credits":
        await buy_credits_menu(update, context); return

    if text == "❓ Help":
        await update.message.reply_text(
            "❓ <b>Help</b>\n\nContact: @DarkGalaxxyy\n\n<i>Fast response.</i>", parse_mode="HTML")
        return

    if text == "⚙️ Admin Panel":
        if not await is_admin(user_id):
            await update.message.reply_text("❌ Denied."); return
        tu = await users.count_documents({}); ju = await users.count_documents({"force_joined": True})
        refresh_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]])
        if user_id != ADMIN_ID:
            await update.message.reply_text(
                f"🛡️ <b>Admin Panel</b>\n\n👤 {tu}\n✅ {ju}\n⏳ {tu-ju}\n\n"
                "Commands:\n/addcredits, /removecredits, /setcredits, /checkbalance,\n"
                "/ban, /unban, /banusers, /broadcast",
                parse_mode="HTML", reply_markup=refresh_kb); return
        tc = sum([u["credits"] async for u in users.find({}, {"credits": 1})])
        tv = await vouchers.count_documents({}); ta = await admins.count_documents({})
        await update.message.reply_text(
            f"👑 <b>Owner Panel</b>\n\n🔧 {MODE}\n♾️ {'ON' if UNLIMITED_MODE else 'OFF'}\n\n"
            f"👤 {tu}\n✅ {ju}\n⏳ {tu-ju}\n\n💰 {tc}\n🎁 {START_CREDITS}\n🔗 {REFER_CREDITS}\n"
            f"💸 {DEDUCTION_CREDITS}\n🎟️ {tv}\n🛡️ {ta}\n\n"
            "See /adminhelp for all commands.",
            parse_mode="HTML", reply_markup=refresh_kb)
        return

# ══════════════════════════════════════════════
#               ADMIN COMMANDS
# ══════════════════════════════════════════════
async def setmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MODE
    if update.effective_user.id != ADMIN_ID: return
    if not context.args or context.args[0].lower() not in ["dual","group","private","maintenance"]:
        await update.message.reply_text("📌 /setmode dual|group|private|maintenance"); return
    MODE = context.args[0].lower()
    await log_admin_action(update.effective_user.id, "setmode", None, MODE)
    await update.message.reply_text(f"✅ <code>{MODE}</code>", parse_mode="HTML")

async def unlimited(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global UNLIMITED_MODE
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("📌 /unlimited on|off"); return
    v = context.args[0].lower()
    if v == "on":
        UNLIMITED_MODE = True
        await update.message.reply_text("♾️ ON")
    elif v == "off":
        UNLIMITED_MODE = False
        await update.message.reply_text("✅ OFF")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    parts = update.message.text.split(" ", 1)
    if len(parts) < 2: await update.message.reply_text("📌 /broadcast <msg>"); return
    msg = parts[1]; ok = fail = 0
    async for u in users.find({}, {"user_id": 1}):
        try: await context.bot.send_message(u["user_id"], msg); ok += 1
        except: fail += 1
    await update.message.reply_text(f"📢 Sent: {ok} | Failed: {fail}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    tu = await users.count_documents({}); ju = await users.count_documents({"force_joined": True})
    tc = sum([u["credits"] async for u in users.find({}, {"credits": 1})])
    tv = await vouchers.count_documents({})
    await update.message.reply_text(
        f"📊 <b>Stats</b>\n\n👤 {tu}\n✅ {ju}\n⏳ {tu-ju}\n\n💰 {tc}\n🔧 <code>{MODE}</code>\n"
        f"♾️ {'ON' if UNLIMITED_MODE else 'OFF'}\n🎁 {START_CREDITS}\n🔗 {REFER_CREDITS}\n🎟️ {tv}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄", callback_data="refresh_stats")]]))

async def addcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    if len(context.args) < 2: await update.message.reply_text("📌 /addcredits <uid> <amt>"); return
    uid = int(context.args[0]); amt = int(context.args[1])
    nb = await update_credits(uid, amt)
    if nb is None: await update.message.reply_text("❌ Not found."); return
    await log_admin_action(update.effective_user.id, "addcredits", uid, f"+{amt}")
    await update.message.reply_text(f"✅ +{amt} to <code>{uid}</code>. Balance: <b>{nb}</b>", parse_mode="HTML")
    try:
        await context.bot.send_message(uid, f"🎉 +{amt} credits! Balance: <b>{nb}</b>", parse_mode="HTML")
    except: pass

async def removecredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    if len(context.args) < 2: await update.message.reply_text("📌 /removecredits <uid> <amt>"); return
    uid = int(context.args[0]); amt = int(context.args[1])
    nb = await update_credits(uid, -amt)
    if nb is None: await update.message.reply_text("❌ Not found."); return
    await log_admin_action(update.effective_user.id, "removecredits", uid, f"-{amt}")
    await update.message.reply_text(f"✅ -{amt} from <code>{uid}</code>. Balance: <b>{nb}</b>", parse_mode="HTML")

async def setcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    if len(context.args) < 2: await update.message.reply_text("📌 /setcredits <uid> <amt>"); return
    uid = int(context.args[0]); amt = int(context.args[1])
    if await set_credits(uid, amt):
        await log_admin_action(update.effective_user.id, "setcredits", uid, f"={amt}")
        await update.message.reply_text(f"✅ Set {amt} for <code>{uid}</code>", parse_mode="HTML")
    else:
        await update.message.reply_text("❌ Not found.")

async def checkbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    if not context.args: await update.message.reply_text("📌 /checkbalance <uid>"); return
    u = await get_user(int(context.args[0]))
    if not u: await update.message.reply_text("❌ Not found."); return
    await update.message.reply_text(
        f"👤 <code>{context.args[0]}</code>\n💰 {u['credits']}\n📅 {u['joined']}\n👥 {u['referrals']}",
        parse_mode="HTML")

async def setstartcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global START_CREDITS
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("📌 /setstartcredits <amt>"); return
    START_CREDITS = int(context.args[0])
    await update.message.reply_text(f"✅ {START_CREDITS}")

async def setrefercredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global REFER_CREDITS
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("📌 /setrefercredits <amt>"); return
    REFER_CREDITS = int(context.args[0])
    await update.message.reply_text(f"✅ {REFER_CREDITS}")

async def setdeductioncredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DEDUCTION_CREDITS
    if update.effective_user.id != ADMIN_ID: return
    if not context.args or not context.args[0].isdigit() or int(context.args[0]) < 1:
        await update.message.reply_text("📌 /setdeductioncredits <amt>"); return
    DEDUCTION_CREDITS = int(context.args[0])
    await update.message.reply_text(f"✅ Cost = {DEDUCTION_CREDITS}")

async def orderid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("📌 /orderid <id>"); return
    o = await orders.find_one({"order_id": context.args[0]})
    if not o: await update.message.reply_text("❌ Not found."); return
    msg = (f"📦 <b>Order</b>\n\n🔖 <code>{o['order_id']}</code>\n👤 <code>{o['user_id']}</code>\n"
           f"💵 ₹{o['amount']}\n📊 {o['status']}\n📅 {o['created']}\n")
    if o.get("type") == "withdraw":
        msg += f"🏦 {o.get('bank_name','?')}\n📛 {o.get('account_name','?')}\n📱 <code>{o.get('upi_id','?')}</code>\n"
    else:
        msg += f"💰 {o.get('credits','?')}\n"
    await update.message.reply_text(msg, parse_mode="HTML")

# ══════════════════════════════════════════════
#               ADMIN MANAGEMENT
# ══════════════════════════════════════════════
async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("📌 /addadmin <uid>"); return
    uid = int(context.args[0])
    u = await get_user(uid)
    if not u: await update.message.reply_text("❌ Not found."); return
    if await admins.find_one({"user_id": uid}):
        await update.message.reply_text("⚠️ Already admin."); return
    await admins.insert_one({"user_id": uid, "username": u.get("username"), "name": u.get("name"),
                             "added": datetime.now(IST).strftime("%Y-%m-%d %H:%M")})
    await update.message.reply_text(f"✅ <code>{uid}</code> admin.", parse_mode="HTML")
    try: await context.bot.send_message(uid, "🛡️ Admin access granted.")
    except: pass

async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("📌 /removeadmin <uid>"); return
    uid = int(context.args[0]); r = await admins.delete_one({"user_id": uid})
    if r.deleted_count:
        await update.message.reply_text(f"✅ <code>{uid}</code> removed.", parse_mode="HTML")
        try: await context.bot.send_message(uid, "⚠️ Admin revoked.")
        except: pass
    else:
        await update.message.reply_text("❌ Not admin.")

async def adminlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    lst = await admins.find({}).to_list(length=100)
    msg = f"🛡️ <b>Admins</b>\n\n👑 <a href='tg://user?id={ADMIN_ID}'>Owner</a>\n\n"
    for i, a in enumerate(lst, 1):
        msg += f'{i}. <a href="tg://user?id={a["user_id"]}">{a.get("name","?")}</a> — {a.get("added","?")}\n'
    await update.message.reply_text(msg or "None.", parse_mode="HTML")

async def checkadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("📌 /checkadmin <uid>"); return
    uid = int(context.args[0])
    logs = await adminlogs.find({"admin_id": uid}).sort("time", -1).limit(50).to_list(length=50)
    adm = await admins.find_one({"user_id": uid})
    msg = f"🛡️ <b>Admin Check</b> <code>{uid}</code>\n\nStatus: {'✅' if adm or uid == ADMIN_ID else '❌'}\n\n"
    for log in logs:
        tgt = f" → <code>{log.get('target')}</code>" if log.get("target") else ""
        det = f" ({log.get('details')})" if log.get("details") else ""
        msg += f"• <code>{log['action']}</code>{tgt}{det} — {log['time']}\n"
    await update.message.reply_text(msg or "No logs.", parse_mode="HTML")

# ══════════════════════════════════════════════
#               CONFIRM WITHDRAW
# ══════════════════════════════════════════════
async def confirm_withdraw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; user_id = q.from_user.id
    await q.answer()
    if not context.user_data.get("withdraw_amount"):
        await q.message.edit_text("❌ Session expired."); return
    amt = context.user_data["withdraw_amount"]; bank = context.user_data["withdraw_bank_name"]
    acc = context.user_data["withdraw_account_name"]; upi = context.user_data["withdraw_upi"]
    oid = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    await orders.insert_one({"order_id":oid,"user_id":user_id,"amount":amt,"status":"pending",
                             "type":"withdraw","bank_name":bank,"account_name":acc,"upi_id":upi,
                             "created":datetime.now(IST).strftime("%Y-%m-%d %H:%M")})
    u = await get_user(user_id); uname = f"@{u['username']}" if u.get("username") else u.get("name") or f"User {user_id}"
    payout = (f"🏧 <b>New Withdrawal</b>\n\n📛 {u.get('name','?')}\n👤 {uname}\n🆔 <code>{user_id}</code>\n"
              f"💵 ₹{amt}\n🏦 {bank}\n📛 {acc}\n📱 <code>{upi}</code>\n📊 Pending ⏳\n\n🔖 <code>{oid}</code>")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Done", callback_data=f"withdrawdone_{oid}_{user_id}_{amt}"),
                                 InlineKeyboardButton("❌ Cancel", callback_data=f"cancelwithdraworder_{oid}_{user_id}")]])
    try:
        await context.bot.send_message(PAYOUT_CHANNEL, payout, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        await q.message.edit_text(f"❌ Failed: {e}"); return
    for k in ("withdraw_amount","withdraw_bank_name","withdraw_account_name","withdraw_upi"):
        context.user_data.pop(k, None)
    await q.message.edit_text("✅ Withdrawal submitted!")

# ══════════════════════════════════════════════
#               MAIN
# ══════════════════════════════════════════════
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("num", num))
    app.add_handler(CommandHandler("tgnum", tgnum))
    app.add_handler(CommandHandler("vehicle", vehicle))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("referstat", referstat))
    app.add_handler(CommandHandler("referlist", referlist))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CommandHandler("createvoucher", createvoucher))
    app.add_handler(CommandHandler("deletevoucher", deletevoucher))
    app.add_handler(CommandHandler("listvouchers", listvouchers))
    app.add_handler(CommandHandler("unlimited", unlimited))
    app.add_handler(CommandHandler("setmode", setmode))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("addcredits", addcredits))
    app.add_handler(CommandHandler("removecredits", removecredits))
    app.add_handler(CommandHandler("setcredits", setcredits))
    app.add_handler(CommandHandler("checkbalance", checkbalance))
    app.add_handler(CommandHandler("setstartcredits", setstartcredits))
    app.add_handler(CommandHandler("setrefercredits", setrefercredits))
    app.add_handler(CommandHandler("setdeductioncredits", setdeductioncredits))
    app.add_handler(CommandHandler("orderid", orderid))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("banusers", banusers))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("msg", msg_user))
    app.add_handler(CommandHandler("addadmin", addadmin))
    app.add_handler(CommandHandler("removeadmin", removeadmin))
    app.add_handler(CommandHandler("adminlist", adminlist))
    app.add_handler(CommandHandler("checkadmin", checkadmin))
    app.add_handler(CallbackQueryHandler(confirm_withdraw_callback, pattern="confirm_withdraw"))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    print("Bot is running...")
    app.run_polling()
