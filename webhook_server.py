"""Chapa webhook server for processing payment callbacks."""

from __future__ import annotations

import os
import hmac
import hashlib
import logging
import json
from flask import Flask, request, jsonify
from datetime import datetime

from config import CHAPA_SECRET_KEY, BOT_TOKEN
import db_supabase as db

logger = logging.getLogger(__name__)
app = Flask(__name__)


def verify_chapa_signature(body: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 signature from Chapa."""
    if not CHAPA_SECRET_KEY or not signature:
        return False

    expected = hmac.new(
        CHAPA_SECRET_KEY.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


@app.route("/webhook/chapa", methods=["POST"])
def chapa_webhook():
    """
    Receive and process Chapa payment callbacks.
    tx_ref format: euee-{telegram_user_id}-{plan}-{unix_timestamp}
    """
    signature = request.headers.get("Chapa-Signature") or request.headers.get("x-chapa-signature")

    if not signature:
        logger.warning("Chapa webhook received without signature")
        return jsonify({"error": "Missing signature"}), 401

    body = request.get_data()

    if not verify_chapa_signature(body, signature):
        logger.warning(f"Invalid Chapa signature: {signature}")
        return jsonify({"error": "Invalid signature"}), 401

    try:
        payload = request.get_json()
    except Exception as e:
        logger.error(f"Failed to parse Chapa webhook JSON: {e}")
        return jsonify({"error": "Invalid JSON"}), 400

    status = payload.get("status")
    tx_ref = payload.get("tx_ref")

    logger.info(f"Chapa webhook received: status={status}, tx_ref={tx_ref}")

    if status != "success" or not tx_ref:
        logger.info(f"Chapa webhook status not success or missing tx_ref")
        return jsonify({"status": "ok"}), 200

    # Parse tx_ref: euee-{user_id}-{plan}-{timestamp}
    try:
        parts = tx_ref.split("-")
        if len(parts) < 3:
            logger.error(f"Invalid tx_ref format: {tx_ref}")
            return jsonify({"status": "ok"}), 200

        user_id = int(parts[1])
        plan = parts[2]

        logger.info(f"Processing payment for user {user_id}, plan {plan}")

        # Grant the subscription
        success = db.grant_pro_access(user_id, plan)

        if not success:
            logger.error(f"Failed to grant access to user {user_id}")
            return jsonify({"status": "ok"}), 200

        # Send Telegram confirmation
        try:
            from telegram import Bot
            bot = Bot(token=BOT_TOKEN)

            user_data = db.get_user(user_id)
            lang = user_data.get("language", "en") if user_data else "en"

            if lang == "en":
                msg = (
                    f"🎉 **PAYMENT SUCCESSFUL!**\n\n"
                    f"Your account has been upgraded to **{plan.upper()}** instantly.\n"
                    f"Go to /menu to start using your new features! 🚀"
                )
            else:
                msg = (
                    f"🎉 **ክፍያዎ ተሳክቷል!**\n\n"
                    f"አካውንትዎ ወዲያውኑ ወደ **{plan.upper()}** አድጓል።\n"
                    f"አዲሶቹን አገልግሎቶች መጠቀም ለመጀመር /menu ይሂዱ! 🚀"
                )

            bot.send_message(
                chat_id=user_id,
                text=msg,
                parse_mode="Markdown"
            )
            logger.info(f"Sent confirmation message to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message to user {user_id}: {e}")

        logger.info(f"✅ Successfully processed payment for user {user_id}")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Error processing Chapa webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "chapa-webhook"}), 200


def start_webhook_server(port: int = 8080, debug: bool = False):
    """Start the webhook server in a non-blocking manner."""
    try:
        logger.info(f"Starting Chapa webhook server on port {port}")
        app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
    except Exception as e:
        logger.error(f"Failed to start webhook server: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_webhook_server()
