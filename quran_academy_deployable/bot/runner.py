"""Unified bot runner for Online Quran Academy (Dual-bot or Unified mode)."""
import asyncio
import logging
import signal
import sys

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, TypeHandler

import db
from bot import admin_bot, config, scheduler, student_bot

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("quran_bot_runner")


async def auto_register_admin_subscriber_middleware(update: Update, context) -> None:
    """Ensure ANY user who interacts with the Admin Bot is registered as an alert subscriber."""
    user = update.effective_user
    if user and user.id:
        db.register_admin_subscriber(user.id, getattr(user, "first_name", "") or "", getattr(user, "username", "") or "")
        if user.id not in config.ADMIN_TELEGRAM_IDS:
            config.ADMIN_TELEGRAM_IDS.append(user.id)


async def global_error_handler(update: object, context) -> None:
    """Log exceptions while preventing application crash on stale callback queries."""
    log.warning("Update error encountered: %s", context.error)


def build_unified_app(token: str) -> Application:
    """Build single application with both student and admin handlers."""
    app = ApplicationBuilder().token(token).build()
    app.add_handler(TypeHandler(Update, auto_register_admin_subscriber_middleware), group=-1)
    student_bot.register_student_handlers(app)
    admin_bot.register_admin_handlers(app)
    app.add_error_handler(global_error_handler)
    return app


def build_student_app(token: str) -> Application:
    app = ApplicationBuilder().token(token).build()
    student_bot.register_student_handlers(app)
    app.add_error_handler(global_error_handler)
    return app


def build_admin_app(token: str) -> Application:
    app = ApplicationBuilder().token(token).build()
    app.add_handler(TypeHandler(Update, auto_register_admin_subscriber_middleware), group=-1)
    admin_bot.register_admin_handlers(app)
    app.add_error_handler(global_error_handler)
    return app


async def run_bots_async() -> None:
    # Ensure database is initialized and migrated
    db.init_db()

    # Start background scheduler for reminders & sheets
    sched_thread, stop_event = scheduler.start_scheduler_thread()

    if config.IS_UNIFIED_MODE:
        log.info("Starting Quran Academy Bot in UNIFIED MODE (Token: ...%s)", config.STUDENT_BOT_TOKEN[-6:])
        app = build_unified_app(config.STUDENT_BOT_TOKEN)

        for attempt in range(1, 6):
            try:
                await app.initialize()
                break
            except Exception as ex:
                log.warning("App initialize attempt %s failed: %s; retrying in 3s...", attempt, ex)
                if attempt == 5:
                    raise
                await asyncio.sleep(3)

        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        log.info("Quran Academy Bot is live and polling updates!")

        stop_signal = asyncio.Event()

        try:
            await stop_signal.wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            log.info("Stopping bot gracefully...")
            stop_event.set()
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

    else:
        log.info("Starting Quran Academy in DUAL-BOT MODE (Student & Admin bots separate)")
        stu_app = build_student_app(config.STUDENT_BOT_TOKEN)
        adm_app = build_admin_app(config.ADMIN_BOT_TOKEN)

        for attempt in range(1, 6):
            try:
                await asyncio.gather(stu_app.initialize(), adm_app.initialize())
                break
            except Exception as ex:
                log.warning("Dual bot initialize attempt %s failed: %s; retrying in 3s...", attempt, ex)
                if attempt == 5:
                    raise
                await asyncio.sleep(3)

        await asyncio.gather(stu_app.start(), adm_app.start())
        await asyncio.gather(
            stu_app.updater.start_polling(allowed_updates=Update.ALL_TYPES),
            adm_app.updater.start_polling(allowed_updates=Update.ALL_TYPES),
        )
        log.info("Both Student Bot and Admin Bot are live and polling updates!")

        stop_signal = asyncio.Event()

        try:
            await stop_signal.wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            log.info("Stopping dual bots gracefully...")
            stop_event.set()
            await asyncio.gather(
                stu_app.updater.stop(),
                adm_app.updater.stop(),
                return_exceptions=True,
            )
            await asyncio.gather(
                stu_app.stop(),
                adm_app.stop(),
                stu_app.shutdown(),
                adm_app.shutdown(),
                return_exceptions=True,
            )


def main() -> None:
    try:
        asyncio.run(run_bots_async())
    except (KeyboardInterrupt, SystemExit):
        log.info("Process terminated by user.")


if __name__ == "__main__":
    main()
