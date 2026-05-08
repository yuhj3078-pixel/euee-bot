"""FastAPI endpoints for payments and the parent dashboard."""

from __future__ import annotations

import logging
import os
import hmac
import time
import hashlib
import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, Header, Depends, APIRouter, Response
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telegram import Update

import payments
import notes
from config import ADMIN_TOKEN, WEBHOOK_SECRET, BASE_WEB_URL, TIER_PRICES, BOT_TOKEN, CHAPA_SECRET_KEY, validate_env

import db_supabase as db

app = FastAPI(title="Abebe EUEE Bot Web Services")
logger = logging.getLogger(__name__)

# FIX: Defer bot application build to startup so importing server.py never triggers
# Firebase init, scheduler start, or Telegram token validation at import time.
application = None  # STEP 3 - Shared module-level instance


def get_application():
    global application
    if application is None:
        from main import build_app as build_bot_app
        application = build_bot_app()
    return application

# ── Redis Rate Limiting (Pass 6.3) ──────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL")
r = None
if REDIS_URL:
    try:
        import redis
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        logger.info("📡 Connected to Redis for rate limiting.")
    except ImportError:
        logger.warning("⚠️ Redis package not installed. Falling back to in-memory limiting.")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {e}. Falling back to in-memory limiting.")
        r = None

_auth_attempts = {} # Fallback in-memory dict

def check_rate_limit(client_ip: str) -> bool:
    """Returns True if allowed, False if blocked."""
    key = f"auth_fail:{client_ip}"
    if r:
        try:
            count = r.get(key)
            if count and int(count) > 100:
                return False
            return True
        except Exception:
            pass
    
    # Fallback to in-memory
    now = time.time()
    attempts, last_reset = _auth_attempts.get(client_ip, [0, now])
    if now - last_reset > 3600:
        attempts = 0
        last_reset = now
        _auth_attempts[client_ip] = [attempts, last_reset]
    
    return attempts <= 100

def increment_rate_limit(client_ip: str):
    key = f"auth_fail:{client_ip}"
    if r:
        try:
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, 3600)
            pipe.execute()
            return
        except Exception:
            pass
    
    # Fallback
    attempts, last_reset = _auth_attempts.get(client_ip, [0, time.time()])
    _auth_attempts[client_ip] = [attempts + 1, last_reset]

# ── Pydantic Models (Pass 4.1) ──────────────────────────────────────────────
class PaymentActionRequest(BaseModel):
    tx_id: str

class AdminLoginRequest(BaseModel):
    token: str

# ── Auth Dependency (Pass 3.1/3.5) ───────────────────────────────────────────
async def admin_auth(request: Request):
    """Verifies session cookie or Bearer token."""
    client_ip = request.client.host
    
    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(status_code=429, detail="Too many authentication attempts.")

    if not ADMIN_TOKEN or ADMIN_TOKEN == "change-me-immediately":
        raise HTTPException(status_code=500, detail="Admin token not configured securely.")
    
    # 1. Try Cookie
    token = request.cookies.get("abebe_admin_session")
    
    # 2. Try Header
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "", 1)
    
    if not token or not hmac.compare_digest(token, ADMIN_TOKEN):
        increment_rate_limit(client_ip)
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return True

# ── Admin Router (Pass 3.2 Default-Deny) ─────────────────────────────────────
admin_router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin_auth)])

# ── Request Logging Middleware (Diagnostic) ──────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"🌐 [{request.method}] {request.url.path} from {request.client.host}")
    response = await call_next(request)
    logger.info(f"🔙 [{request.method}] {request.url.path} -> {response.status_code}")
    return response

@app.on_event("startup")
async def on_startup():
    validate_env()
    # FIX: [startup DB check] — [fail fast if database is unreachable or credentials are invalid]
    try:
        # Test database connection by getting a user (will fail if DB is down)
        db.init_database()
        test_user = db.get_user(1)  # Non-existent user, just to test connection
        logger.info("Database connection test passed.")
    except Exception as exc:
        logger.error(f"🔴 DATABASE CONNECTION TEST FAILED: {exc}")
        logger.error("The app will start, but database-dependent features will fail. Check Supabase credentials.")

    bot = get_application()
    try:
        await bot.initialize()
        await bot.start()
        logger.info("🤖 Bot initialized and started successfully.")
    except Exception as exc:
        logger.error(f"🔴 BOT INITIALIZATION FAILED: {exc}")
        logger.error("The web server will stay up, but the Telegram bot will NOT respond.")
        return # Stop here if bot failed

    dev_mode = os.getenv("DEV_MODE", "").lower() in ("1", "true", "yes")
    webhook_url = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")
    
    # ── Background Worker / Scheduler Hardening ────────────────────────────────
    # FIX: Ensure scheduler only starts ONCE.
    if getattr(app, "scheduler_started", False):
        logger.info("📅 Scheduler already running. Skipping duplicate start.")
    else:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from main import daily_reminder, panic_reminder, weekly_parent_report, reset_weekly_counters
            scheduler = AsyncIOScheduler()
            scheduler.add_job(daily_reminder, "cron", hour=4, minute=0, args=[bot])
            scheduler.add_job(panic_reminder, "cron", hour=9, minute=0, args=[bot], id="panic_noon")
            scheduler.add_job(panic_reminder, "cron", hour=17, minute=0, args=[bot], id="panic_evening")
            scheduler.add_job(weekly_parent_report, "cron", day_of_week="sun", hour=15, minute=0, args=[bot])
            scheduler.add_job(reset_weekly_counters, "cron", day_of_week="mon", hour=21, minute=0, args=[bot])
            scheduler.add_job(db.check_and_expire_subscriptions, "interval", hours=1, args=[bot])
            scheduler.start()
            app.scheduler_started = True
            logger.info("📅 Scheduler started in server.py.")
        except ImportError:
            logger.error("❌ apscheduler not installed. Background jobs will NOT run.")
        except Exception as exc:
            logger.error(f"❌ Failed to start scheduler: {exc}")

    if dev_mode:
        logger.info("🛠️ DEV_MODE detected — using long-polling for local testing.")
        # Ensure any old webhook is removed so polling works
        await bot.bot.delete_webhook(drop_pending_updates=True)
        # Start the polling in the background (non-blocking)
        await bot.updater.start_polling()
        logger.info("✅ Polling started. The bot should now respond to messages locally.")
    elif webhook_url:
        # Clean up common mistakes in WEBHOOK_URL (stripping accidental path suffixes)
        if webhook_url.endswith("/webhook"):
            webhook_url = webhook_url[:-8]
        if webhook_url.endswith("/telegram/webhook"):
            webhook_url = webhook_url[:-17]
            
        final_webhook_url = f"{webhook_url}/telegram/webhook"
        logger.info(f"📤 Setting webhook to: {final_webhook_url}")
        
        # Pass 3.4/3.6 Hardening: Ensure webhook is set with clean slate
        await bot.bot.delete_webhook(drop_pending_updates=True)
        success = await bot.bot.set_webhook(
            url=final_webhook_url,
            allowed_updates=["message", "callback_query", "pre_checkout_query", "poll_answer"]
        )
        if success:
            logger.info(f"✅ Webhook set successfully to {final_webhook_url}")
        else:
            logger.error(f"❌ FAILED TO SET WEBHOOK to {final_webhook_url}. Check BOT_TOKEN and URL accessibility.")
    else:
        logger.warning("⚠️ No WEBHOOK_URL and not in DEV_MODE. The bot will NOT receive updates.")

@app.on_event("shutdown")
async def on_shutdown():
    # FIX: Graceful shutdown on SIGTERM — finish processing updates before exiting.
    bot = get_application()
    logger.info("Shutting down PTB application...")
    await bot.stop()
    await bot.shutdown()


# FIX: SIGTERM handler for Railway zero-downtime redeploys.
import signal

def _handle_sigterm(signum, frame):
    logger.info("Received SIGTERM — initiating graceful shutdown...")
    # FastAPI will trigger shutdown events automatically; this just ensures logging.

signal.signal(signal.SIGTERM, _handle_sigterm)

@app.get("/test")
async def test_route():
    return {"status": "route working", "time": str(datetime.now())}

@app.get("/")
@app.get("/health")
@app.get("/healthz")
async def root_health(request: Request):
    """Core health check and diagnostic endpoint."""
    logger.info(f"🩺 Health check hit from {request.client.host}")
    return {
        "status": "ok",
        "service": "Abebe EUEE Bot",
        "version": "2.1",
        "detected_url": str(request.url),
        "host_header": request.headers.get("host")
    }

@app.get("/telegram/webhook")
@app.get("/telegram/webhook/")
async def telegram_webhook_info(request: Request):
    """Diagnostic endpoint to check webhook status."""
    logger.info(f"🔍 Webhook info requested from {request.client.host if request.client else 'unknown'}")
    try:
        bot_app = get_application()
        info = await bot_app.bot.get_webhook_info()
        return {
            "url": info.url,
            "pending_update_count": info.pending_update_count,
            "last_error_message": info.last_error_message,
            "last_error_date": info.last_error_date,
            "detected_host": request.headers.get("host"),
            "bot_initialized": bot_app is not None
        }
    except Exception as e:
        logger.error(f"Error in webhook info: {e}")
        return {"error": str(e)}

@app.get("/debug/bot")
async def debug_bot():
    """Check if the bot application is initialized and running."""
    bot = get_application()
    return {
        "initialized": bot is not None,
        "token_configured": bool(BOT_TOKEN),
        "webhook_url": os.getenv("WEBHOOK_URL"),
        "railway_env": os.getenv("RAILWAY_ENVIRONMENT")
    }

# STEP 4 - Test route
@app.get("/test")
async def test():
    return {"status": "route working"}

@app.get("/ping")
async def ping():
    return "pong"



# STEP 2 - The exact webhook handler requested
@app.post("/telegram/webhook")
@app.post("/telegram/webhook/")
async def telegram_webhook(request: Request):
    logger.info("📨 Telegram POST received")
    print("Webhook hit")  # Extra logging for diagnostic
    try:
        # 1. Capture raw body first for logging
        body = await request.body()
        body_str = body.decode(errors="replace")
        print(f"Update Body: {body_str[:500]}") # Extra logging for diagnostic
        logger.info(f"📦 Raw Update (first 500 chars): {body_str[:500]}")
        
        if not body:
            logger.warning("⚠️ Received empty body in webhook")
            return Response(content="Empty body", status_code=200)

        bot_app = get_application()
        if bot_app is None:
            logger.error("🔴 Bot application not initialized")
            return JSONResponse({"ok": False, "error": "Application not initialized"}, status_code=200)
        
        # 2. Parse JSON
        import json
        try:
            data = json.loads(body_str)
            logger.debug(f"Parsed Update JSON: {data}")
        except Exception as je:
            logger.error(f"❌ Failed to parse JSON: {je} | Body: {body_str[:200]}")
            return Response(content="Invalid JSON", status_code=200)

        # 3. Process Update
        update = Update.de_json(data, bot_app.bot)
        if update:
            user_id = update.effective_user.id if update.effective_user else "N/A"
            logger.info(f"✅ Processing update {update.update_id} for user {user_id}")
            await bot_app.process_update(update)
            logger.info(f"✅ Update {update.update_id} processed successfully")
        else:
            logger.warning("⚠️ Update.de_json returned None for valid JSON")
            
        return Response(content="OK", status_code=200)
    except Exception as e:
        logger.error(f"❌ Webhook handling error: {e}", exc_info=True)
        # Always return 200 to Telegram to stop retries if the error is unrecoverable
        return Response(status_code=200)

# (duplicate route removed — root_health is defined above at /health and /)

# ── Chapa Payment Webhook (Automated Real-Time Upgrade) ─────────────────────
@app.post("/api/payments/chapa/callback")
async def chapa_webhook(request: Request):
    """
    Chapa sends a POST request here when a payment is successful.
    We verify the signature and upgrade the user instantly.
    """
    # 1. Verify Signature (Pass 4.6 Hardening)
    signature = request.headers.get("x-chapa-signature")
    body = await request.body()
    
    if not CHAPA_SECRET_KEY:
        logger.error("CHAPA_SECRET_KEY missing - cannot verify webhook")
        raise HTTPException(status_code=500)
        
    expected = hmac.new(CHAPA_SECRET_KEY.encode(), body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        logger.warning("Invalid Chapa signature received")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    payload = await request.json()
    status = payload.get("status")
    tx_ref = payload.get("tx_ref")
    
    if status == "success" and tx_ref:
        # tx_ref format: euee_{tier}_{telegram_id}_{random}
        parts = tx_ref.split("_")
        if len(parts) >= 3:
            tier_req = parts[1]
            telegram_id = int(parts[2])
            
            # Perform the upgrade
            success = db.upgrade_user_chapa(telegram_id, tier_req, tx_ref)
            if success:
                logger.info(f"✅ Automated upgrade: User {telegram_id} to {tier_req} via Chapa")
                # Notify the user via bot
                bot = get_application()
                lang = "en"
                try:
                    user_data = db.get_user(telegram_id)
                    lang = user_data.get("language", "en")
                except: pass
                
                msg = (
                    f"🎉 **PAYMENT SUCCESSFUL!**\n\n"
                    f"Your account has been upgraded to **{tier_req.upper()}** instantly.\n"
                    f"Go to the menu to start using your new features! 🚀"
                    if lang == "en" else
                    f"🎉 **ክፍያዎ ተሳክቷል!**\n\n"
                    f"አካውንትዎ ወዲያውኑ ወደ **{tier_req.upper()}** አድጓል።\n"
                    f"አዲሶቹን አገልግሎቶች መጠቀም ለመጀመር ወደ ማውጫው ይሂዱ! 🚀"
                )
                try:
                    await bot.bot.send_message(chat_id=telegram_id, text=msg, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Failed to notify user {telegram_id}: {e}")
                    
    return {"status": "ok"}

@app.get("/api/payments/verify/{tx_ref}")
async def verify_payment_api(tx_ref: str):
    """Manual sync endpoint for the bot to check status if webhook was delayed."""
    res = await payments.verify_payment(tx_ref)
    if res.get("verified"):
        # Upgrade if not already done
        parts = tx_ref.split("_")
        if len(parts) >= 3:
            tier_req = parts[1]
            telegram_id = int(parts[2])
            db.upgrade_user_chapa(telegram_id, tier_req, tx_ref)
        return {"status": "success", "message": "Payment verified and account upgraded."}
    return {"status": "pending", "message": "Payment not yet confirmed by Chapa."}


# (Duplicate /health removed)

_allowed_origins = [BASE_WEB_URL] if (BASE_WEB_URL and "your-url" not in BASE_WEB_URL) else ["http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins, 
    allow_credentials=True, # Enabled for cookies
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: https://cdn.pixabay.com https://images.unsplash.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    if request.url.path.startswith("/api/admin") or request.url.path.startswith("/parent/"):
        response.headers.setdefault("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        response.headers.setdefault("Pragma", "no-cache")
    return response

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ── Admin Login (Pass 3.5/6.2) ───────────────────────────────────────────────
@app.post("/api/admin/login")
async def admin_login(req: AdminLoginRequest, request: Request):
    client_ip = request.client.host
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many attempts")

    if hmac.compare_digest(req.token, ADMIN_TOKEN):
        response = JSONResponse(content={"status": "success"})
        response.set_cookie(
            key="abebe_admin_session",
            value=req.token,
            httponly=True,
            secure=True, 
            samesite="strict",
            max_age=86400 * 7
        )
        return response
    
    increment_rate_limit(client_ip)
    raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/api/admin/logout")
async def admin_logout():
    response = JSONResponse(content={"status": "logged_out"})
    response.delete_cookie("abebe_admin_session")
    return response

# ── Admin API Endpoints (Now using Router) ───────────────────────────────────

@admin_router.get("/overview")
async def admin_overview():
    # Get user statistics from Supabase
    total, free, pro, max_tier = 0, 0, 0, 0
    recent_users = []

    user_query = db.db.collection("users").limit(500)
    last_doc = None
    while True:
        page_query = user_query.start_after(last_doc) if last_doc else user_query
        docs = list(page_query.stream())
        if not docs:
            break

        for doc in docs:
            total += 1
            d = doc.to_dict()
            t = str(d.get("tier", "free")).lower()
            if t == "free":
                free += 1
            elif t.startswith("pro"):
                pro += 1
            elif t.startswith("max"):
                max_tier += 1

            if len(recent_users) < 50:
                recent_users.append({
                    "telegram_id": d.get("telegram_id"),
                    "name": d.get("name", "Unknown"),
                    "tier": d.get("tier", "free"),
                    "joined": str(d.get("joined_at", d.get("joined", "")))
                })
        last_doc = docs[-1]
        await asyncio.sleep(0)

    recent_users.sort(key=lambda x: x.get("joined", ""), reverse=True)
    pending_payments = db.get_pending_payments()
    suggestions = db.get_feature_suggestions()

    return {
        "stats": {
            "total_users": total,
            "free_users": free,
            "pro_users": pro,
            "max_users": max_tier,
            "pending_payments": len(pending_payments),
            "earnings_etb": (pro * TIER_PRICES.get("pro_monthly", 100)) + (max_tier * TIER_PRICES.get("max_monthly", 200))
        },
        "users": recent_users,
        "payments": pending_payments,
        "suggestions": suggestions
    }

@admin_router.post("/payments/approve")
async def admin_approve_payment(req: PaymentActionRequest):
    if db.approve_payment(req.tx_id):
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="Failed to approve")

@admin_router.post("/payments/reject")
async def admin_reject_payment(req: PaymentActionRequest):
    if db.reject_payment(req.tx_id):
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="Failed to reject")

@admin_router.post("/payments/auto_approve")
async def admin_auto_approve():
    pending = db.get_pending_payments()
    approved, skipped = [], []
    for p in pending:
        tx = p.get("tx_id") or p.get("transaction_id")
        if tx and payments.validate_telebirr_tx_id(tx) and p.get("screenshot_url"):
            if db.approve_payment(tx):
                approved.append(tx)
                continue
        skipped.append(tx)
    return {"approved": approved, "skipped": skipped}

@admin_router.get("/notes")
async def admin_notes():
    from config import SUBJECTS
    results = []
    for subject in SUBJECTS.keys():
        files = notes.get_generated_notes_files(subject)
        results.append({
            "subject": subject,
            "has_pdf": bool(files.get("pdf")),
            "has_md": bool(files.get("md")),
            "has_flashcards": bool(files.get("flashcards"))
        })
    return results

@admin_router.post("/notes/{subject}/regenerate")
async def admin_regenerate_notes(subject: str):
    await asyncio.to_thread(notes.ensure_subject_notes_generated, subject, True)
    return {"status": "success"}

app.include_router(admin_router)

# ── Public / Student Endpoints ──────────────────────────────────────────────

@app.get("/api/textbooks/download/{filename}")
async def download_textbook(filename: str, user_id: int, sig: str):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    from helpers import verify_download_signature
    if not verify_download_signature(user_id, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    user = db.get_user(user_id)
    if not user or user.get("tier") == "free":
        raise HTTPException(status_code=403, detail="Unauthorized")

    file_path = os.path.join(os.path.dirname(__file__), "textbooks", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Not found")
        
    return FileResponse(file_path, filename=filename)

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard_view():
    admin_path = os.path.join(TEMPLATES_DIR, "admin_dashboard.html")
    return FileResponse(admin_path, media_type="text/html")

@app.get("/parent/{token}", response_class=HTMLResponse)
async def parent_dashboard(request: Request, token: str):
    user = db.get_user_by_parent_token(token)
    if not user:
        raise HTTPException(status_code=404, detail="Not found")

    # Get parent reports using Supabase-compatible API
    reports = []
    for doc in db.db.collection("parent_reports").where("parent_token", "==", token).stream():
        reports.append(doc.to_dict())
    reports.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    report_text = reports[0].get("report") if reports else "No report yet."

    context = {
        "request": request,
        "name": user.get("name", "Student"),
        "streak": user.get("streak", 0),
        "questions_total": user.get("questions_total", 0),
        "tier": user.get("tier", "free"),
        "report": report_text,
    }
    return templates.TemplateResponse("dashboard.html", context)

# ── Catch-all Diagnostic Route ──────────────────────────────────────────────
@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(request: Request, path_name: str):
    """Logs any request that doesn't match an existing route to help debug 404s."""
    logger.warning(f"🚩 CATCH-ALL HIT: [{request.method}] /{path_name} from {request.client.host if request.client else 'unknown'}")
    return JSONResponse(
        status_code=404,
        content={"error": "Not Found", "path": path_name, "method": request.method}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
