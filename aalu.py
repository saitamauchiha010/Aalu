import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import BadRequest

# ============================================================
#                     CONFIGURATION
# ============================================================

API_URL     = "num.zvx.workers.dev/?key=DxD&mobile={}"
BOT_TOKEN   = "8693982920:AAH_fwloRRWwRCgNyYyVNeZlY1PoVcyPcG0"
CUSTOM_NAME = "@ROLEX_SIR009 & @Darkdon01 & @DarkGalaxxyy & @R4HULxTRUSTED"
ADMIN_ID    = 6131370190

# Mode: dual / group / private / maintenance
MODE = "dual"

# Force Join Settings
FORCE_CHANNEL_USERNAME = "siee1234"
FORCE_CHANNEL_LINK     = "https://t.me/siee1234"
FORCE_GROUP1_LINK      = "https://t.me/+QmnlbCK1x045MzZl"
FORCE_GROUP2_ID        = -1003416250413
FORCE_GROUP2_LINK      = "https://t.me/+cePuY51FkgE5MzY1"

# ============================================================


async def check_membership(bot, user_id, chat):
    try:
        member = await bot.get_chat_member(chat, user_id)
        if member.status in ["kicked", "left"]:
            return False
        return True
    except BadRequest as e:
        error = str(e).lower()
        if "user not found" in error:
            return False
        return True
    except Exception:
        return True


# ============================================================
#                     START COMMAND
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📢 Channel", url=FORCE_CHANNEL_LINK),
            InlineKeyboardButton("👥 Group 1", url=FORCE_GROUP1_LINK),
        ],
        [
            InlineKeyboardButton("👥 Group 2", url=FORCE_GROUP2_LINK),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = (
        "👋 Welcome to NumBot!\n\n"
        "🔍 This bot allows you to fetch detailed information about any number.\n"
        "Powered by @siee1234\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📌 Available Commands:\n\n"
        "/num <number> — Fetch info about a number\n"
        "/start — Show this message\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ Make sure you have joined all required channels and groups to use this bot."
    )
    await update.message.reply_text(msg, reply_markup=reply_markup)


# ============================================================
#                     ADMIN PANEL
# ============================================================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return

    msg = (
        "⚙️ Admin Panel\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔧 Current Mode: {MODE}\n\n"
        "📌 Commands:\n\n"
        "/setmode <mode> — Change bot mode\n"
        "   Modes: dual | group | private | maintenance\n\n"
        "/broadcast <message> — Send message to all users\n\n"
        "/stats — Bot statistics\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(msg)


# ============================================================
#                     SET MODE
# ============================================================

async def setmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MODE
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return

    if not context.args:
        await update.message.reply_text(
            "📌 Usage: /setmode <mode>\n"
            "Modes: dual | group | private | maintenance"
        )
        return

    new_mode = context.args[0].lower()
    if new_mode not in ["dual", "group", "private", "maintenance"]:
        await update.message.reply_text("❌ Invalid mode.\nUse: dual | group | private | maintenance")
        return

    MODE = new_mode
    await update.message.reply_text(f"✅ Mode successfully set to: {MODE}")


# ============================================================
#                     BROADCAST
# ============================================================

user_ids = set()  # Track all users who have used the bot

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return

    if not context.args:
        await update.message.reply_text("📌 Usage: /broadcast <message>")
        return

    message = " ".join(context.args)
    success = 0
    failed = 0

    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            success += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"📢 Broadcast Complete\n\n"
        f"✅ Sent: {success}\n"
        f"❌ Failed: {failed}"
    )


# ============================================================
#                     STATS
# ============================================================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied.")
        return

    await update.message.reply_text(
        f"📊 Bot Statistics\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Total Users: {len(user_ids)}\n"
        f"🔧 Current Mode: {MODE}"
    )


# ============================================================
#                     NUM COMMAND
# ============================================================

async def num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_ids
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    bot = context.bot

    # Track user
    user_ids.add(user_id)

    # Mode check
    if MODE == "maintenance":
        await update.message.reply_text("🔧 Bot is under maintenance. Please try again later.")
        return
    if MODE == "group" and chat_type == "private":
        await update.message.reply_text("⚠️ This bot only works in groups.")
        return
    if MODE == "private" and chat_type in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ This bot only works in private chat.")
        return

    # Force join check
    in_channel = await check_membership(bot, user_id, f"@{FORCE_CHANNEL_USERNAME}")
    in_group2  = await check_membership(bot, user_id, FORCE_GROUP2_ID)

    if not in_channel or not in_group2:
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel", url=FORCE_CHANNEL_LINK)],
            [InlineKeyboardButton("👥 Join Group 1", url=FORCE_GROUP1_LINK)],
            [InlineKeyboardButton("👥 Join Group 2", url=FORCE_GROUP2_LINK)],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        msg = (
            "⚠️ Access Restricted\n\n"
            "To use this bot, please join all of the following:\n\n"
            "Once joined or request sent, try again with /num <number>"
        )
        await update.message.reply_text(msg, reply_markup=reply_markup)
        return

    if not context.args:
        await update.message.reply_text(
            "📌 Usage: /num <number>\n"
            "Example: /num 1234567890"
        )
        return

    number = context.args[0]

    try:
        url = API_URL.format(number)
        if not url.startswith("http"):
            url = "https://" + url
        response = requests.get(url, timeout=10)
        result = response.text.strip()

        if not result:
            await update.message.reply_text("❌ No result found for this number.")
            return

        try:
            data = json.loads(result)
            if "Api_BY" in data:
                data["Api_BY"] = CUSTOM_NAME
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
            await update.message.reply_text(f"```\n{pretty}\n```", parse_mode="Markdown")
        except json.JSONDecodeError:
            await update.message.reply_text(result)

    except requests.exceptions.Timeout:
        await update.message.reply_text("❌ Request timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("❌ Unable to connect to the API.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


# ============================================================
#                     MAIN
# ============================================================

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("num", num))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("setmode", setmode))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    print("Bot is running...")
    app.run_polling()

