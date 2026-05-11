"""Railway entrypoint for the Abebe Telegram bot web service."""

from __future__ import annotations

import os
import signal
import sys
import threading
import logging

import uvicorn


logger = logging.getLogger(__name__)


def _on_sigterm(signum, frame):
    # FIX: Explicit SIGTERM handling for graceful Railway shutdowns.
    raise SystemExit(0)


def start_webhook_server_daemon():
    """Start the Chapa webhook server in a background daemon thread."""
    try:
        from webhook_server import start_webhook_server
        webhook_port = int(os.getenv("WEBHOOK_PORT", "8081"))
        thread = threading.Thread(
            target=start_webhook_server,
            args=(webhook_port, False),
            daemon=True,
            name="chapa-webhook-server"
        )
        thread.start()
        logger.info(f"✅ Started Chapa webhook server on port {webhook_port}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to start webhook server: {e}")


def main() -> None:
    signal.signal(signal.SIGTERM, _on_sigterm)

    # Start webhook server in background daemon thread
    start_webhook_server_daemon()

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, lifespan="on")


if __name__ == "__main__":
    main()

