"""
main.py — EUEE Abebe Bot Entry Point
=====================================
Wires all handlers, schedulers, and starts polling.
Run: python main.py
"""
import logging
import sys
import asyncio
from datetime import datetime
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, CallbackQueryHandler, filters,
    ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    BOT_TOKEN, CHOOSE_LANGUAGE, CHOOSE_SUBJECT, ASKING_QUESTION, 
    CONFESSION_BOX, BOSS_FIGHT, AWAITING_FEATURE_SUGGESTION, 
    validate_env
)
# Use Supabase database (new default)
import db_supabase as db
sys.modules["db"] = db
import ai
from handlers import (
    start, set_language, menu_handler, choose_subject, handle_question,
    button_callback, handle_confession, cmd_progress, cmd_leaderboard,
    cmd_radar, cmd_predict, error_handler, handle_boss_answer, handle_telebirr_tx, handle_telebirr_photo,
    handle_suggestion, AWAITING_TELEBIRR_TX, AWAITING_TELEBIRR_PHOTO, cmd_id, cmd_demo_upgrade,
    cmd_admin, cmd_manual_upgrade, handle_upgrade_button, cmd_admin_build, cmd_invite, cmd_review_sheet, cmd_plan,
    cmd_textbooks, handle_textbook_download,
    safe_handler, run_blocking
)
from helpers import format_countdown, safe_user_ref

MENU_REGEX = (
    r"(?i)(Practice|Random Challenge|Mock Exam|Audio|Flashcard|Memory Trick|Progress|Leaderboard|"
    r"Battle|Confession|Boss|Predictor|Upgrade|Plan|Parent|Exam Tips|Weak Radar|Model Exam|Study Notes|E-Book|Textbooks|Invite Friend|Review Sheet|/menu|"
    r"ልምምድ|ለማዳ|የዘፈቀደ ጥያቄ|የሙከራ ፈተና|ሙሉ ፈተና|የኦዲዮ ትምህርት|ኦዲዮ|"
    r"ፍላሽ|የማስታወሻ ዘዴ|እድገቴ|ሰንጠረዥ|የውድድር ሁነታ|ውድድር|የምስጢር ሳጥን|ምስጢር|የቦስ ውጊያ|ቦስ|"
    r"ውጤት ትንቢት|ትንቢት|አሳድግ|የወላጅ ሊንክ|ወላጅ|የፈተና ምክሮች|ፈተና ምክር|የድክመት ራዳር|ድክመት ራዳር|ሞዴል ፈተና|ማስታወሻ|ማስታወቂያ|ኢ-መጽሐፍት|መጽሐፍት|ጓደኛ ይጋብዙ|የክለሳ ወረቀት|ተመለስ|"
    r"🎯|🎲|📝|📚|🎧|🗂️|🧠|📊|🏆|⚔️|🤫|👾|🔮|💡|📡|👑|👨‍👩‍👦|📒|🤝|🔙)"
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Validate env on startup ──────────────────────────────────────────────────
validate_env()

# Global app instance for Shadow Monitor
bot_app = None
scheduler = None


# ── Scheduled jobs ────────────────────────────────────────────────────────────
async def _batch_stream_users(batch_size=500):
    """FIX: Yield users in batches to avoid OOM when streaming 50k+ users."""
    query = db.db.collection("users").limit(batch_size)

    while True:
        docs = list(query.stream())
        if not docs:
            break

        for doc in docs:
            yield doc

        query = query.start_after(docs[-1])
        await asyncio.sleep(0)


async def daily_reminder(app):
    """Send daily study reminder + streak + countdown + Voice of the Topper tip."""
    # FIX: Process users in batches; never load entire collection into memory.
    # FIX: Wrap sync AI call in run_blocking so the scheduler never blocks the event loop.
    tip = None
    count = 0
    async for doc in _batch_stream_users(batch_size=500):
        user = doc.to_dict()
        tid = user.get("telegram_id")
        lang = user.get("language", "en")
        streak = user.get("streak", 0)

        # Generate tip once
        if tip is None:
            tip = await run_blocking(ai.generate_topper_tip, lang)
            db.save_daily_tip(tip)

        countdown = format_countdown(lang)
        if lang == "en":
            msg = (
                f"🌅 Good morning, {user.get('name', 'Student')}!\n\n"
                f"🔥 Streak: {streak} days — don't break it!\n"
                f"{countdown}\n\n"
                f"💡 Voice of the Topper:\n\"{tip}\"\n\n"
                "Press /start to study now! 📚"
            )
        else:
            msg = (
                f"🌅 እንደምን አደርክ {user.get('name', 'ተማሪ')}!\n\n"
                f"🔥 ስትሪክ: {streak} ቀን — አታቋርጥ!\n"
                f"{countdown}\n\n"
                f"💡 ከምርጥ ተማሪ:\n\"{tip}\"\n\n"
                "ለመማር /start ጫን 📚"
            )

        # Check panic mode (7 days before EUEE)
        if db.is_panic_mode():
            panic_msg = ("\n\n🚨 PANIC MODE ACTIVATED 🚨\n"
                        "EUEE is in less than 7 days!\n"
                        "Abebe is sending you 3 reminders today!\n"
                        "Use /start → Practice to study NOW!"
                        if lang == "en" else
                        "\n\n🚨 ድንጋጤ ሁነታ 🚨\n"
                        "EUEE 7 ቀን ቀረ!\n"
                        "አቤቤ ዛሬ 3 ጊዜ ያስታውስሃል!\n"
                        "/start ጫን!")
            msg += panic_msg

        try:
            await app.bot.send_message(chat_id=tid, text=msg)
            count += 1
        except Exception:
            pass  # user may have blocked bot
    logger.info(f"📅 Daily reminder sent to {count} users.")


async def panic_reminder(app):
    """Send extra reminders only during the final panic-mode window."""
    if db.is_panic_mode():
        await daily_reminder(app)


async def weekly_parent_report(app):
    """Send Parent Shock Report every Sunday."""
    count = 0
    async for doc in _batch_stream_users(batch_size=500):
        user = doc.to_dict()
        token = user.get("parent_token")
        if not token:
            continue
        name = user.get("name", "Student")
        try:
            # FIX: Wrap sync AI call in run_blocking so the scheduler never blocks.
            report = await run_blocking(ai.generate_parent_shock_report, user, name)
            db.db.collection("parent_reports").add({
                "parent_token": token,
                "report": report,
                "week": datetime.now().isocalendar()[1],
                "created_at": db._now(),
            })
            count += 1
        except Exception:
            logger.exception("Parent report generation failed for %s", safe_user_ref(user.get("telegram_id")))
    logger.info(f"📊 Parent reports generated for {count} users.")


async def reset_weekly_counters(app):
    """Reset weekly question counters every Monday."""
    count = 0
    async for doc in _batch_stream_users(batch_size=500):
        try:
            db.update_user(doc.to_dict().get("telegram_id"), {
                "questions_this_week": 0,
                "week_start": db._today(),
            })
            count += 1
        except Exception:
            logger.exception("Failed to reset weekly counters for user")
    logger.info(f"🔄 Weekly counters reset for {count} users.")


# ── Build application ────────────────────────────────────────────────────────
async def post_init(application):
    # FIX: Removed eager worker start to prevent loop-closure crashes on startup.
    # The worker will now start lazily when first needed.

    # FIX: Scheduler runs only in standalone mode (polling). When server.py is the entry point,
    # scheduler is started there to avoid duplicate jobs.
    from config import WEBHOOK_URL
    if os.getenv("RAILWAY_ENVIRONMENT") or WEBHOOK_URL:
        logger.info("🔧 Railway/webhook mode detected — scheduler will be started by server.py.")
        return

    global scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_reminder, "cron", hour=4, minute=0, args=[application])
    scheduler.add_job(panic_reminder, "cron", hour=9, minute=0, args=[application], id="panic_noon")
    scheduler.add_job(panic_reminder, "cron", hour=17, minute=0, args=[application], id="panic_evening")
    scheduler.add_job(weekly_parent_report, "cron", day_of_week="sun", hour=15, minute=0, args=[application])
    scheduler.add_job(reset_weekly_counters, "cron", day_of_week="mon", hour=21, minute=0, args=[application])
    scheduler.add_job(db.check_and_expire_subscriptions, "interval", hours=1, args=[application])
    scheduler.start()
    logger.info("📅 Scheduler started in standalone mode.")


async def post_stop(application):
    """Cleanup on shutdown."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("📅 Scheduler shut down.")


# [Unified build_app is now located below in the FastAPI section]



from fastapi import FastAPI, Request, HTTPException
import uvicorn
import hmac

# ── FastAPI App Configuration ────────────────────────────────────────────────
# Defer server import to main() to avoid circular dependency



def build_app():
    global bot_app
    if bot_app is not None:
        return bot_app
        
    # Fix Windows console emoji/Unicode output
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).post_stop(post_stop).build()

    # (Previous handler registration logic remains same)
    def _guard(handler_func):
        return safe_handler(handler_func)

    def _safe(handler_func):
        return safe_handler(handler_func)

    # Conversation handler ...
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", _safe(start)),
            CommandHandler("menu", _safe(start)),
            CallbackQueryHandler(_safe(handle_upgrade_button), pattern="^upgrade_"),
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.Regex(MENU_REGEX),
                _safe(menu_handler)
            )
        ],
        states={
            CHOOSE_LANGUAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _safe(set_language))
            ],
            CHOOSE_SUBJECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _safe(choose_subject))
            ],
            ASKING_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _guard(handle_question))
            ],
            CONFESSION_BOX: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _guard(handle_confession))
            ],
            BOSS_FIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _guard(handle_boss_answer))
            ],
            AWAITING_TELEBIRR_TX: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _guard(handle_telebirr_tx))
            ],
            AWAITING_TELEBIRR_PHOTO: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, _guard(handle_telebirr_photo))
            ],
            AWAITING_FEATURE_SUGGESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _guard(handle_suggestion))
            ],
        },
        fallbacks=[
            CommandHandler("menu", _safe(start)),
            # Fallback to start if confused
            MessageHandler(filters.ALL & ~filters.COMMAND, _safe(start))
        ],
        per_user=True,
        per_chat=True,
        per_message=False, # BUG FIX: per_message=True breaks conversations across separate messages
        allow_reentry=True,
    )

    app.add_handler(conv)
    # Global catch-all should respond to user if nothing else matched
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, _safe(start)))
    async def safe_log_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_ref = safe_user_ref(getattr(update.effective_user, "id", None))
        if update.message and update.message.text:
            text = (update.message.text or "").strip()
            if text.startswith("/"):
                logger.info("[MSG] user=%s command=%s", user_ref, text.split()[0])
            else:
                logger.info("[MSG] user=%s text_chars=%s", user_ref, len(text))
        elif update.callback_query:
            logger.info("[BTN] user=%s data=%s", user_ref, str(update.callback_query.data)[:80])

    app.add_handler(MessageHandler(filters.ALL, safe_log_messages), group=-1)
    app.add_handler(CallbackQueryHandler(_safe(button_callback)), group=1)
    app.add_handler(CallbackQueryHandler(_safe(handle_textbook_download), pattern="^dl_textbook_.*$"))
    
    # Global commands
    for cmd in ["start", "menu", "progress", "leaderboard", "radar", "predict", "id", "demo_upgrade", "admin", "manualupgrade", "admin_build", "invite", "review", "plan", "status"]:
        handler = locals().get(f"cmd_{cmd}") or globals().get(f"cmd_{cmd}") or (start if cmd in ["start", "menu"] else None)
        if handler:
            app.add_handler(CommandHandler(cmd, _safe(handler)))

    app.add_error_handler(error_handler)
    bot_app = app
    return app

def main():
    # The bot and scheduler are now initialized via server.py's @app.on_event("startup")
    # which is triggered when uvicorn starts.
    port = int(os.environ.get("PORT", 8080))
    
    # Start FastAPI with Uvicorn (Defer import to break circular dependency)
    from server import app as web_app
    logger.info(f"🚀 Starting Uvicorn on port {port}...")
    uvicorn.run(web_app, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")

if __name__ == "__main__":
    main()
