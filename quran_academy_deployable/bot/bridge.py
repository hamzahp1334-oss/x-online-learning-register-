"""Notification bridge between Academy core / website and Telegram bots."""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

import db
from bot import config

log = logging.getLogger(__name__)


def send_telegram_message(token: str, chat_id: int | str, text: str, reply_markup: dict | None = None, parse_mode: str = "HTML") -> bool:
    """Send a message using Telegram Bot API via standard urllib."""
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return bool(res.get("ok"))
    except urllib.error.HTTPError as ex:
        err_msg = ""
        try:
            err_msg = ex.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        log.warning("Telegram send failed (HTTP %s): %s", ex.code, err_msg)
        return False
    except Exception as ex:
        log.warning("Telegram send error to chat %s: %s", chat_id, ex)
        return False


import os
import httpx


def send_telegram_photo(token: str, chat_id: int | str, photo: str, caption: str, reply_markup: dict | None = None, parse_mode: str = "HTML") -> bool:
    """Send photo using Telegram Bot API. Supports local files on disk or remote URL/file_id."""
    if not token or not chat_id or not photo:
        return False
    url = f"https://api.telegram.org/bot{token}/sendPhoto"

    # If photo is a local file on disk, upload using multipart/form-data
    if os.path.isfile(photo):
        try:
            with open(photo, "rb") as f:
                files = {"photo": (os.path.basename(photo), f, "image/jpeg")}
                data = {
                    "chat_id": str(chat_id),
                    "caption": caption[:1024],
                    "parse_mode": parse_mode,
                }
                if reply_markup is not None:
                    data["reply_markup"] = json.dumps(reply_markup)
                resp = httpx.post(url, data=data, files=files, timeout=25.0)
                res = resp.json()
                if res.get("ok"):
                    return True
                log.warning("Telegram photo upload failed: %s", res)
        except Exception as ex:
            log.warning("Telegram photo upload error to chat %s: %s", chat_id, ex)

    # Otherwise send via JSON (for URL or file_id)
    payload = {
        "chat_id": chat_id,
        "photo": photo,
        "caption": caption[:1024],
        "parse_mode": parse_mode,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return bool(res.get("ok"))
    except Exception as ex:
        log.warning("Telegram photo send failed to %s: %s", chat_id, ex)
        return False


def notify_admins_new_registration(reg: dict) -> int:
    """Send instant interactive alert with receipt photo to all authorized administrators."""
    admin_ids = db.get_all_admin_telegram_ids(config.ADMIN_TELEGRAM_IDS)
    if not admin_ids:
        log.info("No admin Telegram IDs configured to receive registration alert.")
        return 0

    reg_id = reg.get("reg_id", "")
    student_name = reg.get("full_name") or "Student"
    age = reg.get("age", "")
    age_str = f" ({age} yrs)" if age else ""
    country = reg.get("country") or "Not specified"
    city = reg.get("city") or ""
    loc_str = f"{city}, {country}" if city else country
    phone = reg.get("phone") or "—"
    whatsapp = f"(WA: {reg['whatsapp']})" if reg.get("whatsapp") else ""
    category_key = reg.get("category_snapshot") or reg.get("category") or "qaida"
    category_title = db.CATEGORIES.get(category_key, category_key.capitalize())
    price = reg.get("monthly_price_snapshot")
    curr = reg.get("currency_snapshot") or "ETB"
    price_str = f"{price:g} {curr}/mo" if price is not None else "Contact Academy"
    schedule = reg.get("preferred_schedule") or "Flexible"
    created = reg.get("created_at") or db.utcnow()
    receipt_path = reg.get("receipt_url") or ""
    receipt_file_id = reg.get("receipt_file_id") or ""
    photo_target = receipt_path if (receipt_path and os.path.isfile(receipt_path)) else receipt_file_id

    receipt_status_str = "🧾 <b>Payment Receipt:</b> Photo Attached Below" if photo_target else "⏳ <b>Payment:</b> Awaiting Receipt"

    guardian_str = ""
    if reg.get("age") and reg["age"] < 18 and reg.get("parent_name"):
        guardian_str = (
            f"👨‍👩‍👦 <b>Parent/Guardian:</b> {reg['parent_name']}\n"
            f"📞 <b>Guardian Phone:</b> {reg.get('parent_phone', '')}\n"
            f"🤝 <b>Relationship:</b> {reg.get('parent_relationship', 'Guardian')}\n"
        )

    text = (
        f"🔔 <b>New Student Registration & Payment Receipt!</b>\n\n"
        f"🆔 <b>Registration ID:</b> <code>{reg_id}</code>\n"
        f"👤 <b>Student Name:</b> <b>{student_name}</b>{age_str}\n"
        f"🎂 <b>Age:</b> {age or '—'} years\n"
        f"{guardian_str}"
        f"📍 <b>Location:</b> {loc_str}\n"
        f"📞 <b>Phone:</b> {phone} {whatsapp}\n"
        f"📂 <b>Selected Course:</b> <b>{category_title}</b>\n"
        f"💰 <b>Monthly Tuition:</b> <b>{price_str}</b>\n"
        f"📅 <b>Preferred Schedule:</b> {schedule}\n"
        f"💳 <b>Payment Status:</b> ⏳ <b>Pending Verification (Receipt Attached)</b>\n"
        f"⏱ <b>Submitted At:</b> {created}\n"
    )

    markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Verify & Approve", "callback_data": f"adm_appr:{reg_id}"},
                {"text": "❌ Reject", "callback_data": f"adm_rejc:{reg_id}"},
            ],
            [
                {"text": "👨‍🏫 Assign Teacher", "callback_data": f"adm_asgn:{reg_id}"},
                {"text": "👁️ Full Details", "callback_data": f"adm_view:{reg_id}"},
            ],
        ]
    }

    sent = 0
    token = config.ADMIN_BOT_TOKEN
    for aid in admin_ids:
        # If receipt photo is present, send photo directly with caption!
        delivered = False
        if photo_target:
            delivered = send_telegram_photo(token, aid, photo_target, text, reply_markup=markup)
        if not delivered:
            delivered = send_telegram_message(token, aid, text, reply_markup=markup)
        if delivered:
            sent += 1
    return sent


def notify_student_status_update(student_tg_id: int, reg_id: str, new_status: str, explanation: str = "") -> bool:
    """Notify student on Telegram when registration status changes."""
    if not student_tg_id:
        return False

    status_titles = {
        "confirmed": "✅ <b>Registration Confirmed!</b>",
        "active": "🎉 <b>Student Enrollment Active!</b>",
        "rejected": "⚠️ <b>Registration Update</b>",
        "contacted": "📞 <b>Academy Update</b>",
        "cancelled": "ℹ️ <b>Registration Cancelled</b>",
    }
    title = status_titles.get(new_status, "ℹ️ <b>Registration Update</b>")

    body = f"{title}\n\nYour registration (<code>{reg_id}</code>) status is now: <b>{new_status.upper()}</b>."
    if explanation:
        body += f"\n\n<b>Note from Academy:</b>\n{explanation}"

    body += "\n\nYou can view your profile and details anytime in the student menu."
    return send_telegram_message(config.STUDENT_BOT_TOKEN, student_tg_id, body)


def notify_class_reminder(student_tg_id: int, schedule: dict, minutes_before: int) -> bool:
    """Send upcoming class reminder to student."""
    if not student_tg_id:
        return False

    time_str = f"in {minutes_before} minutes" if minutes_before < 60 else "tomorrow"
    title = schedule.get("title") or "Quran Class"
    teacher = schedule.get("teacher_name") or "Assigned Teacher"
    sched_at = schedule.get("scheduled_at", "").replace("T", " ")[:16]
    link = schedule.get("meeting_link") or ""

    text = (
        f"⏰ <b>Class Reminder</b>\n\n"
        f"Your class <b>{title}</b> is scheduled {time_str}!\n"
        f"📅 <b>Time:</b> {sched_at} ({schedule.get('timezone', 'UTC')})\n"
        f"👨‍🏫 <b>Teacher:</b> {teacher}\n"
        f"⏱ <b>Duration:</b> {schedule.get('duration_min', 45)} minutes\n"
    )
    if link:
        text += f"\n🔗 <b>Online Meeting Link:</b>\n<a href='{link}'>{link}</a>\n"
    else:
        text += "\n<i>The teacher will provide the meeting details shortly.</i>\n"

    return send_telegram_message(config.STUDENT_BOT_TOKEN, student_tg_id, text)
