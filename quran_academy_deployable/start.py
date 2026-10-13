"""Online Quran Academy — Unified Cloud & Local Deployment Runner.

Runs both the Web Application and the Telegram Bot Services concurrently.
Can also run individual components via CLI flags:
  python start.py            # Runs both Web and Bots (Standard Render deployment)
  python start.py --web-only # Runs Web Application only
  python start.py --bot-only # Runs Telegram Bots only
"""
import asyncio
import logging
import os
import sys
import threading
import time

# Ensure base directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import db
from app import create_app, load_dotenv, seed_admin_from_env
import sheets
from bot import config, runner, scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("quran_academy_entrypoint")


def run_web(port: int, host: str = "0.0.0.0") -> None:
    """Start the WSGI web server."""
    app = create_app()
    log.info("Serving Online Quran Academy web app on http://%s:%s", host, port)
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=8)
    except ImportError:
        app.run(host=host, port=port, threaded=True)


def main() -> None:
    load_dotenv()
    db.init_db()
    seed_admin_from_env()

    args = sys.argv[1:]
    port = int(os.environ.get("PORT", "3000"))
    host = os.environ.get("HOST", "0.0.0.0")

    if "--bot-only" in args:
        log.info("Running in BOT-ONLY mode...")
        runner.main()
        return

    if "--web-only" in args:
        log.info("Running in WEB-ONLY mode...")
        stop_event = threading.Event()
        worker = threading.Thread(target=sheets.worker_loop, args=(stop_event,), daemon=True, name="sheets-worker")
        worker.start()
        run_web(port, host)
        return

    # Default: Run BOTH Web Application and Telegram Bots concurrently
    log.info("Starting Online Quran Academy in UNIFIED CLOUD MODE (Web + Telegram Bots)...")

    # Start sheets sync background worker thread
    stop_event = threading.Event()
    sheets_worker = threading.Thread(target=sheets.worker_loop, args=(stop_event,), daemon=True, name="sheets-worker")
    sheets_worker.start()

    # Start telegram bot runner in a background daemon thread
    bot_thread = threading.Thread(target=runner.main, daemon=True, name="bot-runner")
    bot_thread.start()

    # Run web server in main thread (binds $PORT for Render HTTP health checks)
    run_web(port, host)


if __name__ == "__main__":
    main()
