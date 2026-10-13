"""Background scheduler for class reminders and Google Sheets sync draining."""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import db
import sheets
from bot import bridge

log = logging.getLogger(__name__)


def check_and_send_class_reminders() -> int:
    """Find scheduled classes needing 24h or 30m reminders and dispatch them."""
    reminders_sent = 0
    now_utc = datetime.now(timezone.utc)

    # 1. Classes roughly 24 hours away (23h to 25h)
    start_24h = (now_utc + timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_24h = (now_utc + timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%SZ")

    due_24h = db.query(
        "SELECT cs.*, s.telegram_user_id, s.full_name as student_name, t.name as teacher_name "
        "FROM class_schedules cs "
        "JOIN students s ON s.id = cs.student_id "
        "LEFT JOIN teachers t ON t.id = cs.teacher_id "
        "WHERE cs.status='scheduled' AND cs.reminder_24h_sent=0 "
        "AND cs.scheduled_at >= ? AND cs.scheduled_at <= ? "
        "AND s.telegram_user_id IS NOT NULL",
        (start_24h, end_24h),
    )
    for row in due_24h:
        if bridge.notify_class_reminder(row["telegram_user_id"], row, minutes_before=1440):
            db.execute("UPDATE class_schedules SET reminder_24h_sent=1, updated_at=? WHERE id=?", (db.utcnow(), row["id"]))
            reminders_sent += 1

    # 2. Classes roughly 30 minutes away (20m to 40m)
    start_30m = (now_utc + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_30m = (now_utc + timedelta(minutes=40)).strftime("%Y-%m-%dT%H:%M:%SZ")

    due_30m = db.query(
        "SELECT cs.*, s.telegram_user_id, s.full_name as student_name, t.name as teacher_name "
        "FROM class_schedules cs "
        "JOIN students s ON s.id = cs.student_id "
        "LEFT JOIN teachers t ON t.id = cs.teacher_id "
        "WHERE cs.status='scheduled' AND cs.reminder_30m_sent=0 "
        "AND cs.scheduled_at >= ? AND cs.scheduled_at <= ? "
        "AND s.telegram_user_id IS NOT NULL",
        (start_30m, end_30m),
    )
    for row in due_30m:
        if bridge.notify_class_reminder(row["telegram_user_id"], row, minutes_before=30):
            db.execute("UPDATE class_schedules SET reminder_30m_sent=1, updated_at=? WHERE id=?", (db.utcnow(), row["id"]))
            reminders_sent += 1

    return reminders_sent


def scheduler_worker(stop_event: threading.Event) -> None:
    """Continuous background worker loop for reminders and Sheets sync."""
    log.info("Scheduler worker thread started.")
    last_sheets_check = 0.0

    while not stop_event.wait(15):  # Check every 15 seconds
        try:
            # Check class reminders
            check_and_send_class_reminders()

            # Process Sheets queue every 30s
            now = time.time()
            if now - last_sheets_check >= 30:
                last_sheets_check = now
                if hasattr(sheets, "process_pending"):
                    sheets.process_pending(force=False, limit=50)

        except Exception as ex:
            log.warning("Scheduler cycle warning: %s", ex)
            continue

    log.info("Scheduler worker thread stopped.")


def start_scheduler_thread() -> tuple[threading.Thread, threading.Event]:
    stop_event = threading.Event()
    thread = threading.Thread(target=scheduler_worker, args=(stop_event,), daemon=True, name="bot-scheduler")
    thread.start()
    return thread, stop_event
