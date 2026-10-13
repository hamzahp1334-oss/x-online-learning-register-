"""Optional email notifications over stdlib smtplib.

Nothing is pretended: if SMTP is not configured, send() returns a
"not_configured" status and the admin dashboard displays that fact.
"""
import os
import smtplib
from email.message import EmailMessage

import db


def smtp_config() -> dict:
    return {
        "host": os.environ.get("SMTP_HOST", "").strip(),
        "port": int(os.environ.get("SMTP_PORT", "587") or 587),
        "username": os.environ.get("SMTP_USERNAME", "").strip(),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from": os.environ.get("SMTP_FROM", os.environ.get("SMTP_USERNAME", "")).strip(),
        "use_tls": os.environ.get("SMTP_USE_TLS", "true").lower() != "false",
        "notify_admin": os.environ.get("NOTIFY_ADMIN_EMAIL", "").strip(),
    }


def is_configured() -> bool:
    cfg = smtp_config()
    return bool(cfg["host"] and cfg["username"] and cfg["notify_admin"])


def status() -> dict:
    return {
        "configured": is_configured(),
        "admin_email_configured": bool(smtp_config()["notify_admin"]),
    }


def send(to: str, subject: str, body: str) -> str:
    """Returns 'sent', 'not_configured', or an error description."""
    cfg = smtp_config()
    if not (cfg["host"] and cfg["username"] and cfg["password"]):
        return "not_configured"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from"] or cfg["username"]
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
            if cfg["use_tls"]:
                server.starttls()
            server.login(cfg["username"], cfg["password"])
            server.send_message(msg)
        return "sent"
    except Exception as e:  # notification failures must never break registration
        return f"error: {str(e)[:200]}"


def notify_admin_new_registration(reg: dict) -> str:
    cfg = smtp_config()
    if not cfg["notify_admin"]:
        return "not_configured"
    body = (
        f"A new registration was submitted.\n\n"
        f"Registration ID: {reg['reg_id']}\n"
        f"Student: {reg['full_name']}\n"
        f"Program: {reg['program_name_snapshot']}\n"
        f"Preferred schedule: {reg['preferred_schedule']}\n\n"
        f"Open the admin dashboard to review it."
    )
    return send(cfg["notify_admin"], f"New registration {reg['reg_id']}", body)


def send_student_confirmation(reg: dict, email: str) -> str:
    if not email:
        return "no_email_provided"
    body = (
        f"Assalamu alaikum {reg['full_name']},\n\n"
        f"Your registration has been received.\n\n"
        f"Registration ID: {reg['reg_id']}\n"
        f"Program: {reg['program_name_snapshot']}\n"
        f"Date: {reg['created_at']}\n\n"
        f"The academy will contact you to confirm class availability and schedule.\n\n"
        f"If you did not submit this registration, please contact the academy."
    )
    return send(email, f"Registration received — {reg['reg_id']}", body)
