"""Admin Bot handlers and features for Online Quran Academy."""
import asyncio
import html
import json
import logging
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db
import sheets
from bot import bridge, config

import os
import re
import time

log = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# Authorization Check & Login
# ---------------------------------------------------------------------------

OPEN_DEMO_ACCESS = os.environ.get("ADMIN_DEMO_MODE", "true").lower() != "false"

def is_authorized_admin(user_id: int | None) -> bool:
    if not user_id:
        return False
    if OPEN_DEMO_ACCESS:
        return True
    return db.is_telegram_admin(user_id, config.ADMIN_TELEGRAM_IDS)


def require_admin(handler_func):
    """Decorator to enforce strict admin authorization."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        uid = user.id if user else None
        if not is_authorized_admin(uid):
            msg = (
                "⛔ <b>Access Restricted</b>\n\n"
                f"Your Telegram User ID is: <code>{uid}</code>\n\n"
                "This bot is restricted to authorized Quran Academy administrators.\n\n"
                "To authorize your account, send:\n"
                "<code>/login &lt;admin_password&gt;</code>\n"
                "(or add your ID to <code>ADMIN_TELEGRAM_IDS</code> in <code>.env</code>)."
            )
            if update.callback_query:
                await update.callback_query.answer("Access Restricted", show_alert=True)
                try:
                    await update.callback_query.edit_message_text(msg, parse_mode="HTML")
                except Exception:
                    pass
            elif update.message:
                await update.message.reply_text(msg, parse_mode="HTML")
            return
        return await handler_func(update, context, *args, **kwargs)
    return wrapper


async def admin_login_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow authorized administrator to authenticate via password."""
    user = update.effective_user
    uid = user.id if user else None
    if not update.message or not uid:
        return
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Please provide the administrator password:\n<code>/login &lt;password&gt;</code>",
            parse_mode="HTML",
        )
        return

    pwd = args[0].strip()
    env_pwd = os.environ.get("ADMIN_PASSWORD", "adminpass12345").strip()

    from auth import verify_password
    admin_row = db.query_one("SELECT * FROM admin_users LIMIT 1")
    authorized = False
    if env_pwd and pwd == env_pwd:
        authorized = True
    elif admin_row and verify_password(pwd, admin_row.get("password_hash", "")):
        authorized = True

    if authorized:
        if admin_row:
            db.execute("UPDATE admin_users SET telegram_user_id=?, updated_at=? WHERE id=?", (uid, db.utcnow(), admin_row["id"]))
        if uid not in config.ADMIN_TELEGRAM_IDS:
            config.ADMIN_TELEGRAM_IDS.append(uid)
        await update.message.reply_text(
            f"✅ <b>Authentication Successful!</b>\n\n"
            f"Your Telegram ID (<code>{uid}</code>) is now authorized as an Administrator.\n\n"
            "Welcome to the Administrator Panel!",
            reply_markup=admin_main_keyboard(),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text("❌ Incorrect password. Access denied.")


# ---------------------------------------------------------------------------
# Admin Navigation & Main Menu
# ---------------------------------------------------------------------------

def admin_main_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("📊 Dashboard", callback_data="adm_dash"),
            InlineKeyboardButton("📝 Registrations", callback_data="adm_regs"),
        ],
        [
            InlineKeyboardButton("👨‍🎓 Students", callback_data="adm_students"),
            InlineKeyboardButton("📚 Manage Courses", callback_data="adm_courses"),
        ],
        [
            InlineKeyboardButton("💰 Manage Pricing", callback_data="adm_pricing"),
            InlineKeyboardButton("👨‍🏫 Teachers", callback_data="adm_teachers"),
        ],
        [
            InlineKeyboardButton("📅 Class Schedules", callback_data="adm_schedules"),
            InlineKeyboardButton("📖 Learning Progress", callback_data="adm_progress"),
        ],
        [
            InlineKeyboardButton("💳 Payment Status", callback_data="adm_payments"),
            InlineKeyboardButton("📢 Announcements", callback_data="adm_announcements"),
        ],
        [
            InlineKeyboardButton("📄 Google Sheets", callback_data="adm_sheets"),
            InlineKeyboardButton("⚙️ Settings", callback_data="adm_settings"),
        ],
    ]
    if config.IS_UNIFIED_MODE:
        buttons.append([InlineKeyboardButton("🎓 Switch to Student Mode", callback_data="stu_menu")])
    return InlineKeyboardMarkup(buttons)


@require_admin
async def admin_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    academy_name = db.get_setting("academy_name", "Online Quran Academy")
    user = update.effective_user
    uid = user.id if user else None
    if uid and uid not in config.ADMIN_TELEGRAM_IDS:
        config.ADMIN_TELEGRAM_IDS.append(uid)
    text = (
        f"🛡️ <b>{academy_name} — Administrator Panel (Demo Mode)</b>\n\n"
        "Welcome to the Administrator Panel! Select a management section below to test:"
    )
    kb = admin_main_keyboard()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


# ---------------------------------------------------------------------------
# A. Dashboard
# ---------------------------------------------------------------------------

@require_admin
async def dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    # Query real database metrics
    total_reg = db.query_one("SELECT COUNT(*) c FROM registrations WHERE archived_at IS NULL")["c"]
    new_reg = db.query_one("SELECT COUNT(*) c FROM registrations WHERE status='new' AND archived_at IS NULL")["c"]
    pending_reg = db.query_one("SELECT COUNT(*) c FROM registrations WHERE status='contacted' AND archived_at IS NULL")["c"]
    confirmed_reg = db.query_one("SELECT COUNT(*) c FROM registrations WHERE status='confirmed' AND archived_at IS NULL")["c"]
    active_reg = db.query_one("SELECT COUNT(*) c FROM registrations WHERE status='active' AND archived_at IS NULL")["c"]

    total_stu = db.query_one("SELECT COUNT(*) c FROM students")["c"]
    active_stu = db.query_one("SELECT COUNT(*) c FROM students WHERE status='active'")["c"]

    upcoming_classes = db.query_one("SELECT COUNT(*) c FROM class_schedules WHERE status='scheduled' AND scheduled_at >= datetime('now')")["c"]
    pending_reqs = db.query_one("SELECT COUNT(*) c FROM schedule_requests WHERE status='pending'")["c"]

    # Google Sheets status
    sheets_info = sheets.status() if hasattr(sheets, "status") else {}
    sync_status = "✅ Configured" if sheets_info.get("configured") else "⚠️ Not Configured"
    pending_sync = sheets_info.get("pending", 0)

    # Payments status
    unpaid = db.query_one("SELECT COUNT(*) c FROM payment_records WHERE status='not_paid'")["c"]
    paid = db.query_one("SELECT COUNT(*) c FROM payment_records WHERE status='paid'")["c"]

    # Course breakdown
    course_counts = db.query(
        "SELECT program_name_snapshot, COUNT(*) c FROM registrations "
        "WHERE archived_at IS NULL GROUP BY program_name_snapshot ORDER BY c DESC LIMIT 4"
    )
    course_summary = "\n".join([f"  • {r['program_name_snapshot']}: {r['c']}" for r in course_counts]) or "  • None yet"

    text = (
        "📊 <b>Administrator Dashboard</b>\n\n"
        f"<b>Registrations:</b>\n"
        f"• Total: <b>{total_reg}</b> | 🆕 New: <b>{new_reg}</b>\n"
        f"• Contacted: <b>{pending_reg}</b> | Confirmed: <b>{confirmed_reg}</b>\n"
        f"• Active Enrolled: <b>{active_reg}</b>\n\n"
        f"<b>Students:</b>\n"
        f"• Total Students: <b>{total_stu}</b> (Active: <b>{active_stu}</b>)\n\n"
        f"<b>Courses Popularity:</b>\n{course_summary}\n\n"
        f"<b>Operations:</b>\n"
        f"• Upcoming Classes: <b>{upcoming_classes}</b>\n"
        f"• Pending Schedule Requests: <b>{pending_reqs}</b>\n"
        f"• Payments: <b>{paid} Paid</b> | <b>{unpaid} Pending</b>\n"
        f"• Google Sheets Sync: <b>{sync_status}</b> ({pending_sync} in queue)\n"
    )

    buttons = [
        [InlineKeyboardButton("🔄 Refresh Stats", callback_data="adm_dash")],
        [InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="adm_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


# ---------------------------------------------------------------------------
# B. Registration Management
# ---------------------------------------------------------------------------

@require_admin
async def registrations_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    # List newest registrations
    regs = db.query(
        "SELECT r.*, s.full_name, s.phone, s.country FROM registrations r "
        "JOIN students s ON s.id = r.student_id "
        "WHERE r.archived_at IS NULL ORDER BY r.created_at DESC LIMIT 6"
    )

    text = "📝 <b>Registration Management</b>\n\nRecent registrations:"
    buttons = []
    if not regs:
        text += "\nNo registrations submitted yet."
    else:
        for r in regs:
            status_icon = "🆕" if r["status"] == "new" else ("✅" if r["status"] == "confirmed" else "ℹ️")
            label = f"{status_icon} {r['reg_id']} — {r['full_name']} ({r['status'].upper()})"
            buttons.append([InlineKeyboardButton(label, callback_data=f"adm_view:{r['reg_id']}")])

    buttons.append([InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="adm_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def registration_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    reg_id = query.data.split(":", 1)[1]
    r = db.query_one(
        "SELECT r.*, s.full_name, s.age, s.country, s.city, s.phone, s.whatsapp, s.email, "
        "s.parent_name, s.parent_phone, s.telegram_user_id "
        "FROM registrations r JOIN students s ON s.id = r.student_id "
        "WHERE r.reg_id=?",
        (reg_id,),
    )
    if not r:
        await query.edit_message_text("Registration not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_regs")]]))
        return

    price = r.get("monthly_price_snapshot")
    curr = r.get("currency_snapshot") or "ETB"
    price_str = f"{price:g} {curr}/mo" if price is not None else "Contact Academy"

    guardian_info = ""
    if r.get("age") and r["age"] < 18:
        guardian_info = (
            f"\n<b>Parent/Guardian:</b> {r.get('parent_name')} ({r.get('parent_relationship', 'Guardian')})\n"
            f"<b>Guardian Phone:</b> {r.get('parent_phone')}\n"
        )

    receipt_exists = bool(r.get("receipt_url") or r.get("receipt_file_id"))
    receipt_status = "✅ Attached (Photo Available)" if receipt_exists else "⏳ Not Uploaded"

    text = (
        f"📄 <b>Registration Details — {r['reg_id']}</b>\n\n"
        f"👤 <b>Student:</b> {r['full_name']} ({r.get('age', '—')} yrs)\n"
        f"📍 <b>Location:</b> {r.get('city', '')}, {r.get('country', '')}\n"
        f"📞 <b>Phone:</b> {r['phone']} (WA: {r.get('whatsapp') or '—'})\n"
        f"✉️ <b>Email:</b> {r.get('email') or '—'}\n"
        f"💬 <b>Telegram ID:</b> <code>{r.get('telegram_user_id') or 'Not linked'}</code>\n"
        f"{guardian_info}"
        f"\n📚 <b>Program:</b> {r['program_name_snapshot']}\n"
        f"💰 <b>Fee Snapshot:</b> {price_str}\n"
        f"🎯 <b>Level:</b> {r.get('reading_level')}\n"
        f"📅 <b>Preferred Schedule:</b> {r.get('preferred_schedule')}\n"
        f"💻 <b>Format:</b> {r.get('class_format')}\n"
        f"🧾 <b>Receipt:</b> {receipt_status}\n"
        f"📊 <b>Status:</b> <b>{r['status'].upper()}</b>\n"
        f"⏱ <b>Submitted:</b> {r['created_at']}\n"
        f"📝 <b>Admin Notes:</b> {r.get('admin_notes') or 'None'}\n"
    )

    action_row = [
        InlineKeyboardButton("✅ Approve", callback_data=f"adm_appr:{r['reg_id']}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"adm_rejc:{r['reg_id']}"),
    ]
    buttons = [action_row]

    if receipt_exists:
        buttons.append([InlineKeyboardButton("📸 View Receipt Photo", callback_data=f"adm_rcpt:{r['reg_id']}")])

    buttons.append([
        InlineKeyboardButton("👨‍🏫 Assign Teacher", callback_data=f"adm_asgn:{r['reg_id']}"),
        InlineKeyboardButton("📝 Edit Notes", callback_data=f"adm_notes:{r['reg_id']}"),
    ])
    buttons.append([
        InlineKeyboardButton("🔙 Back to Registrations", callback_data="adm_regs"),
    ])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def registration_view_receipt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    reg_id = query.data.split(":", 1)[1]
    r = db.query_one("SELECT * FROM registrations WHERE reg_id=?", (reg_id,))
    if not r:
        await query.answer("Registration not found.", show_alert=True)
        return

    import os
    local_path = r.get("receipt_url") or ""
    file_id = r.get("receipt_file_id") or ""
    chat_id = update.effective_chat.id

    if local_path and os.path.isfile(local_path):
        with open(local_path, "rb") as f:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=f,
                caption=f"📸 <b>Payment Receipt for</b> <code>{reg_id}</code>\nStudent: <b>{r['program_name_snapshot']}</b>",
                parse_mode="HTML",
            )
    elif file_id:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=file_id,
                caption=f"📸 <b>Payment Receipt for</b> <code>{reg_id}</code>",
                parse_mode="HTML",
            )
        except Exception:
            await query.answer("Could not load receipt directly from Telegram server.", show_alert=True)
    else:
        await query.answer("No receipt photo found for this registration.", show_alert=True)


@require_admin
async def registration_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, reg_id = query.data.split(":", 1)
    now = db.utcnow()

    r = db.query_one(
        "SELECT r.*, s.telegram_user_id, s.full_name FROM registrations r "
        "JOIN students s ON s.id = r.student_id WHERE r.reg_id=?",
        (reg_id,),
    )
    if not r:
        await query.answer("Registration not found.", show_alert=True)
        return

    if action == "adm_appr":
        db.execute("UPDATE registrations SET status='confirmed', updated_at=? WHERE reg_id=?", (now, reg_id))
        db.execute("UPDATE students SET status='confirmed', updated_at=? WHERE id=?", (now, r["student_id"]))
        db.execute(
            "UPDATE payment_records SET status='paid', amount_received=amount_due, received_at=?, updated_at=? WHERE reg_id=? OR student_id=?",
            (now, now, reg_id, r["student_id"]),
        )
        sheets.enqueue_registration(reg_id)
        if r.get("telegram_user_id"):
            course_name = r.get("program_name_snapshot") or "Quran Program"
            bridge.notify_student_status_update(
                r["telegram_user_id"],
                reg_id,
                "confirmed",
                f"Your payment for {course_name} has been verified and your registration is confirmed! "
                "The academy administration will assign your teacher and class schedule shortly.",
            )
        await query.answer("Registration & payment approved!", show_alert=True)
        try:
            await registration_view_callback(update, context)
        except Exception:
            pass

    elif action == "adm_rejc":
        db.execute("UPDATE registrations SET status='rejected', updated_at=? WHERE reg_id=?", (now, reg_id))
        sheets.enqueue_registration(reg_id)
        if r.get("telegram_user_id"):
            bridge.notify_student_status_update(r["telegram_user_id"], reg_id, "rejected", "Please contact academy administration for details regarding your registration.")
        await query.answer("Registration marked as rejected.", show_alert=True)
        try:
            await registration_view_callback(update, context)
        except Exception:
            pass

    elif action == "adm_asgn":
        # Prompt to select a teacher
        teachers = db.query("SELECT * FROM teachers WHERE status='active' ORDER BY name")
        if not teachers:
            await query.answer("No active teachers found. Add a teacher first under Teachers menu.", show_alert=True)
            return
        buttons = []
        for t in teachers:
            buttons.append([InlineKeyboardButton(f"👨‍🏫 {t['name']}", callback_data=f"adm_do_asgn:{reg_id}:{t['id']}")])
        buttons.append([InlineKeyboardButton("🔙 Cancel", callback_data=f"adm_view:{reg_id}")])
        await query.edit_message_text(
            f"Select teacher to assign to registration <code>{reg_id}</code> ({r['full_name']}):",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML",
        )


@require_admin
async def registration_assign_teacher_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    reg_id = parts[1]
    teacher_id = int(parts[2])

    r = db.query_one("SELECT * FROM registrations WHERE reg_id=?", (reg_id,))
    t = db.query_one("SELECT * FROM teachers WHERE id=?", (teacher_id,))
    if not r or not t:
        await query.answer("Record not found.", show_alert=True)
        return

    now = db.utcnow()
    # Upsert teacher assignment
    db.execute(
        "INSERT INTO teacher_assignments(teacher_id, student_id, program_id, status, assigned_at) "
        "VALUES(?, ?, ?, 'active', ?)",
        (teacher_id, r["student_id"], r["program_id"], now),
    )
    db.execute("UPDATE students SET status='active', updated_at=? WHERE id=?", (now, r["student_id"]))
    db.execute("UPDATE registrations SET status='active', updated_at=? WHERE reg_id=?", (now, reg_id))

    await query.answer(f"Assigned to {t['name']} successfully!", show_alert=True)
    # Refresh detail view
    query.data = f"adm_view:{reg_id}"
    await registration_view_callback(update, context)


# ---------------------------------------------------------------------------
# C. Student Management
# ---------------------------------------------------------------------------

@require_admin
async def students_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    students = db.query("SELECT * FROM students ORDER BY id DESC LIMIT 8")
    text = "👨‍🎓 <b>Student Management</b>\n\nRecent students:"
    buttons = []
    for s in students:
        tg_flag = "📱" if s.get("telegram_user_id") else "🌐"
        buttons.append([InlineKeyboardButton(f"{tg_flag} {s['full_name']} ({s.get('status', 'new').upper()})", callback_data=f"adm_stu:{s['id']}")])

    buttons.append([InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="adm_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def student_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    sid = int(query.data.split(":", 1)[1])
    s = db.query_one("SELECT * FROM students WHERE id=?", (sid,))
    if not s:
        await query.answer("Student not found.", show_alert=True)
        return

    regs = db.get_student_registrations(sid)
    courses_txt = ", ".join([r["program_name_snapshot"] for r in regs]) or "None"

    # Assigned teacher
    asgn = db.query_one(
        "SELECT t.name FROM teacher_assignments ta JOIN teachers t ON t.id=ta.teacher_id "
        "WHERE ta.student_id=? AND ta.status='active' LIMIT 1",
        (sid,),
    )
    teacher = asgn["name"] if asgn else "None"

    text = (
        f"👨‍🎓 <b>Student: {s['full_name']}</b>\n\n"
        f"🆔 <b>Student ID:</b> <code>#{s['id']}</code>\n"
        f"📊 <b>Status:</b> <b>{s.get('status', 'new').upper()}</b>\n"
        f"📍 <b>Location:</b> {s.get('city', '')}, {s.get('country', '')}\n"
        f"📞 <b>Phone:</b> {s['phone']} (WA: {s.get('whatsapp') or '—'})\n"
        f"✉️ <b>Email:</b> {s.get('email') or '—'}\n"
        f"💬 <b>Telegram ID:</b> <code>{s.get('telegram_user_id') or 'Not linked'}</code>\n"
        f"📚 <b>Courses:</b> {courses_txt}\n"
        f"👨‍🏫 <b>Teacher:</b> {teacher}\n"
    )

    buttons = [
        [
            InlineKeyboardButton("📊 View Progress", callback_data=f"adm_view_prog:{sid}"),
            InlineKeyboardButton("➕ Add Progress", callback_data=f"adm_add_prog:{sid}"),
        ],
        [
            InlineKeyboardButton("📅 Schedule Class", callback_data=f"adm_new_sched:{sid}"),
            InlineKeyboardButton("💳 Payments", callback_data=f"adm_stu_pay:{sid}"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Students", callback_data="adm_students"),
        ],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


# ---------------------------------------------------------------------------
# D. Course & Kitab Management
# ---------------------------------------------------------------------------

@require_admin
async def courses_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    core_progs = db.query(
        "SELECT * FROM programs WHERE category != 'kitab' AND active=1 ORDER BY sort_order, id"
    )
    kitab_count = db.query_one("SELECT COUNT(*) c FROM programs WHERE category='kitab' AND active=1")["c"]
    total_kitabs = db.query_one("SELECT COUNT(*) c FROM programs WHERE category='kitab'")["c"]
    show_extra = db.get_setting("show_button_extra_details", False)
    display_mode = "Detailed (With Fees & Badges)" if show_extra else "Clean Titles Only (Uncluttered)"

    text = (
        "📚 <b>Course & Kitab Management</b>\n\n"
        "Configure available academy courses, manage the Kitab books catalog, and customize student display mode.\n\n"
        f"<b>Student Display Mode:</b> <code>{display_mode}</code>\n\n"
        "<b>Core Academic Courses:</b>"
    )
    buttons = []
    for p in core_progs:
        active_mark = "🟢" if p.get("active") else "🔴"
        price_txt = f"{p['monthly_price']:g} {p['currency']}" if p.get("monthly_price") is not None else "No price"
        buttons.append([InlineKeyboardButton(f"{active_mark} {p['name']} ({price_txt})", callback_data=f"adm_prog_edit:{p['id']}")])

    # Dedicated Kitab management entry
    buttons.append([
        InlineKeyboardButton(f"📖 Manage Kitabs Catalog ({kitab_count}/{total_kitabs} Active)", callback_data="adm_kitabs")
    ])

    # Display mode toggle for student bot presentation
    toggle_label = "🔘 Switch Display: Clean Titles" if show_extra else "🔘 Switch Display: Detailed (+Fees)"
    buttons.append([InlineKeyboardButton(toggle_label, callback_data="adm_toggle_btn_details")])

    buttons.append([InlineKeyboardButton("➕ Add New Course", callback_data="adm_prog_new")])
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="adm_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def admin_toggle_btn_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    curr = db.get_setting("show_button_extra_details", False)
    new_val = not curr
    db.set_setting("show_button_extra_details", new_val)
    mode_str = "Detailed (+Fees & Badges)" if new_val else "Clean Titles Only (Uncluttered)"
    await query.answer(f"Student display mode set to: {mode_str}", show_alert=True)
    await courses_callback(update, context)


@require_admin
async def admin_kitabs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    kitabs = db.query("SELECT * FROM programs WHERE category='kitab' ORDER BY sort_order, id")
    text = (
        "📚 <b>Kitab Management (Islamic Books Catalog)</b>\n\n"
        "Manage classical texts and Kitab books taught at the academy.\n"
        "Tap any Kitab below to edit its title, author, fee, description, or delete it.\n\n"
        f"Total Kitabs in Catalog: <b>{len(kitabs)}</b>"
    )
    buttons = []
    for k in kitabs:
        active_mark = "🟢" if k.get("active") else "🔴"
        price = k.get("monthly_price")
        price_txt = f"{price:g} {k.get('currency', 'ETB')}" if price is not None else "No fee"
        author_txt = f" • {k.get('author_or_subject')}" if k.get('author_or_subject') else ""
        label = f"{active_mark} {k['name']}{author_txt} ({price_txt})"
        buttons.append([InlineKeyboardButton(label, callback_data=f"adm_k_view:{k['id']}")])

    buttons.append([InlineKeyboardButton("➕ Add New Kitab Type", callback_data="adm_k_new")])
    buttons.append([InlineKeyboardButton("🔙 Back to Courses", callback_data="adm_courses")])
    buttons.append([InlineKeyboardButton("🏠 Admin Menu", callback_data="adm_menu")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def admin_kitab_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    kid = int(query.data.split(":", 1)[1])
    k = db.query_one("SELECT * FROM programs WHERE id=? AND category='kitab'", (kid,))
    if not k:
        await query.answer("Kitab not found.", show_alert=True)
        await admin_kitabs_callback(update, context)
        return

    price = k.get("monthly_price")
    curr = k.get("currency") or "ETB"
    price_str = f"<b>{price:g} {curr} / month</b>" if price is not None else "<i>Contact Academy (No price)</i>"
    status_str = "🟢 ACTIVE (Public to Students)" if k.get("active") else "🔴 INACTIVE (Hidden)"

    text = (
        f"📖 <b>Kitab: {k['name']}</b>\n\n"
        f"👤 <b>Author / Subject:</b> {k.get('author_or_subject') or 'Not specified'}\n"
        f"📚 <b>Book Title:</b> {k.get('book_title') or k['name']}\n"
        f"💰 <b>Monthly Fee:</b> {price_str}\n"
        f"🎯 <b>Level / Target:</b> {k.get('level_info') or 'All levels'}\n"
        f"📦 <b>Required Materials:</b> {k.get('required_materials') or 'None specified'}\n"
        f"📊 <b>Status:</b> {status_str}\n\n"
        f"📝 <b>Description:</b>\n{k.get('description') or 'None'}"
    )

    toggle_btn = "🔴 Deactivate" if k.get("active") else "🟢 Activate"
    buttons = [
        [
            InlineKeyboardButton("✏️ Edit Title", callback_data=f"adm_k_edt_name:{kid}"),
            InlineKeyboardButton("✍️ Edit Author", callback_data=f"adm_k_edt_auth:{kid}"),
        ],
        [
            InlineKeyboardButton("💰 Set Monthly Fee", callback_data=f"adm_k_edt_fee:{kid}"),
            InlineKeyboardButton("📝 Edit Description", callback_data=f"adm_k_edt_desc:{kid}"),
        ],
        [
            InlineKeyboardButton("📦 Edit Materials", callback_data=f"adm_k_edt_mat:{kid}"),
            InlineKeyboardButton(toggle_btn, callback_data=f"adm_k_toggle:{kid}"),
        ],
        [
            InlineKeyboardButton("🗑️ Delete Kitab", callback_data=f"adm_k_del_ask:{kid}"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Kitabs List", callback_data="adm_kitabs"),
        ],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def admin_kitab_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    kid = int(query.data.split(":", 1)[1])
    k = db.query_one("SELECT active FROM programs WHERE id=? AND category='kitab'", (kid,))
    if k:
        new_active = 0 if k["active"] else 1
        db.execute("UPDATE programs SET active=?, updated_at=? WHERE id=?", (new_active, db.utcnow(), kid))
        status_txt = "activated" if new_active else "deactivated"
        await query.answer(f"Kitab {status_txt} successfully!", show_alert=True)
    query.data = f"adm_k_view:{kid}"
    await admin_kitab_view_callback(update, context)


@require_admin
async def admin_kitab_del_ask_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    kid = int(query.data.split(":", 1)[1])
    k = db.query_one("SELECT name FROM programs WHERE id=? AND category='kitab'", (kid,))
    if not k:
        await query.answer("Kitab not found.", show_alert=True)
        return

    text = (
        f"🗑️ <b>Delete Kitab: {k['name']}</b>\n\n"
        "Are you sure you want to permanently delete this Kitab from the academy catalog?\n\n"
        "⚠️ <i>This action cannot be undone.</i>"
    )
    buttons = [
        [InlineKeyboardButton("⚠️ Yes, Delete Kitab", callback_data=f"adm_k_del_yes:{kid}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"adm_k_view:{kid}")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def admin_kitab_del_yes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    kid = int(query.data.split(":", 1)[1])
    k = db.query_one("SELECT name FROM programs WHERE id=? AND category='kitab'", (kid,))
    name = k["name"] if k else f"#{kid}"

    reg_count = db.query_one("SELECT COUNT(*) c FROM registrations WHERE program_id=?", (kid,))["c"]
    if reg_count > 0:
        db.execute("UPDATE programs SET active=0, public_visible=0, updated_at=? WHERE id=?", (db.utcnow(), kid))
        await query.answer(f"Kitab '{name}' has existing student registrations. Deactivated and hidden from catalog.", show_alert=True)
    else:
        db.execute("DELETE FROM programs WHERE id=? AND category='kitab'", (kid,))
        await query.answer(f"Kitab '{name}' deleted successfully!", show_alert=True)

    await admin_kitabs_callback(update, context)


@require_admin
async def admin_kitab_new_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    db.save_bot_session(uid, "adm_k_new_name", {})
    text = (
        "➕ <b>Add New Kitab Type</b>\n\n"
        "<b>Step 1 of 3:</b> Please enter the <b>Title / Name of the Kitab</b>:\n\n"
        "<i>(Type and send the Kitab title, e.g. 'Bulugh al-Maram' or 'Umdat al-Ahkam')</i>"
    )
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="adm_kitabs")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def admin_kitab_edit_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    action, kid_s = query.data.split(":", 1)
    kid = int(kid_s)
    k = db.query_one("SELECT * FROM programs WHERE id=? AND category='kitab'", (kid,))
    if not k:
        await query.answer("Kitab not found.", show_alert=True)
        return

    field_map = {
        "adm_k_edt_name": ("Title", "adm_k_in_name", k["name"]),
        "adm_k_edt_auth": ("Author / Subject", "adm_k_in_auth", k.get("author_or_subject") or "None"),
        "adm_k_edt_fee": ("Monthly Fee (ETB)", "adm_k_in_fee", f"{k.get('monthly_price') or 'None'}"),
        "adm_k_edt_desc": ("Description", "adm_k_in_desc", k.get("description") or "None"),
        "adm_k_edt_mat": ("Required Materials", "adm_k_in_mat", k.get("required_materials") or "None"),
    }

    field_title, step, current_val = field_map[action]
    db.save_bot_session(uid, step, {"kitab_id": kid})

    text = (
        f"✏️ <b>Edit {field_title} for {k['name']}</b>\n\n"
        f"Current: <i>{current_val}</i>\n\n"
        f"Please send the new <b>{field_title}</b> as a message below:"
    )
    buttons = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"adm_k_view:{kid}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def course_new_prompt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = (
        "➕ <b>Add New Course</b>\n\n"
        "What type of course do you wish to add?\n\n"
        "• <b>Kitab (Classical Islamic Book):</b> Add a specific book to the Kitab catalog.\n"
        "• <b>General Subject:</b> Add an academic program (e.g. Arabic or Islamic Studies)."
    )
    buttons = [
        [InlineKeyboardButton("📖 Add New Kitab", callback_data="adm_k_new")],
        [InlineKeyboardButton("📚 Add General Subject", callback_data="adm_prog_new_gen")],
        [InlineKeyboardButton("🔙 Back to Courses", callback_data="adm_courses")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def course_new_gen_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    db.save_bot_session(uid, "adm_p_new_name", {})
    text = (
        "➕ <b>Add General Academic Subject</b>\n\n"
        "Please enter the <b>Course Name</b>:\n"
        "<i>(e.g., 'Advanced Tajweed' or 'Classical Arabic')</i>"
    )
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="adm_courses")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def course_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    pid = int(query.data.split(":", 1)[1])
    p = db.query_one("SELECT * FROM programs WHERE id=?", (pid,))
    if not p:
        await query.answer("Course not found.", show_alert=True)
        return

    price = p.get("monthly_price")
    curr = p.get("currency") or "ETB"
    price_str = f"{price:g} {curr}/mo" if price is not None else "Contact Academy"
    status_str = "ACTIVE (Public)" if p.get("active") else "INACTIVE"

    text = (
        f"📚 <b>Course: {p['name']}</b>\n\n"
        f"📂 <b>Category:</b> {p.get('category')}\n"
        f"💰 <b>Monthly Fee:</b> <b>{price_str}</b>\n"
        f"⏱ <b>Lessons:</b> {p.get('lessons_per_week') or 'Flexible'}/week ({p.get('lesson_duration_min') or 45} min)\n"
        f"🎯 <b>Level / Age:</b> {p.get('level_info')} | {p.get('age_group')}\n"
        f"📊 <b>Status:</b> {status_str}\n"
    )
    if p.get("category") == "kitab":
        text += (
            f"\n📖 <b>Kitab Text:</b> {p.get('book_title') or 'None'}\n"
            f"👤 <b>Author:</b> {p.get('author_or_subject') or 'None'}\n"
            f"📦 <b>Materials:</b> {p.get('required_materials') or 'None'}\n"
        )

    toggle_btn = "🔴 Deactivate" if p.get("active") else "🟢 Activate"
    buttons = [
        [
            InlineKeyboardButton("💰 Set Price", callback_data=f"adm_set_price:{pid}"),
            InlineKeyboardButton(toggle_btn, callback_data=f"adm_toggle_active:{pid}"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Courses", callback_data="adm_courses"),
        ],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def course_toggle_active_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    pid = int(query.data.split(":", 1)[1])
    p = db.query_one("SELECT active FROM programs WHERE id=?", (pid,))
    if p:
        new_active = 0 if p["active"] else 1
        db.execute("UPDATE programs SET active=?, updated_at=? WHERE id=?", (new_active, db.utcnow(), pid))
    query.data = f"adm_prog_edit:{pid}"
    await course_edit_callback(update, context)



# ---------------------------------------------------------------------------
# E. Pricing Management
# ---------------------------------------------------------------------------

@require_admin
async def pricing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    progs = db.query("SELECT * FROM programs ORDER BY sort_order, id")
    text = "💰 <b>Dynamic Monthly Pricing Management</b>\n\nTap a course to modify its price:"
    buttons = []
    for p in progs:
        curr = p.get("currency") or "ETB"
        price_txt = f"{p['monthly_price']:g} {curr}" if p.get("monthly_price") is not None else "Not set"
        buttons.append([InlineKeyboardButton(f"{p['name']} ➔ {price_txt}", callback_data=f"adm_set_price:{p['id']}")])

    buttons.append([InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="adm_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def set_price_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    pid = int(query.data.split(":", 1)[1])

    p = db.query_one("SELECT name, monthly_price, currency FROM programs WHERE id=?", (pid,))
    db.save_bot_session(uid, "adm_input_price", {"program_id": pid})

    curr = p.get("currency") or "ETB"
    curr_price = f"{p['monthly_price']:g}" if p.get("monthly_price") is not None else "None"

    await query.edit_message_text(
        f"💰 <b>Set Monthly Price for {p['name']}</b>\n\n"
        f"Current Price: <b>{curr_price} {curr}</b>\n\n"
        "Please type the new monthly price (number, or type '0' to clear price):\n\n"
        "<i>(Send number as message)</i>",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# F. Teacher Management
# ---------------------------------------------------------------------------

@require_admin
async def teachers_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    teachers = db.query("SELECT * FROM teachers ORDER BY id DESC")
    text = "👨‍🏫 <b>Teacher Management</b>\n\nRegistered teachers:"
    buttons = []
    if not teachers:
        text += "\nNo teacher profiles added yet."
    else:
        for t in teachers:
            buttons.append([InlineKeyboardButton(f"👨‍🏫 {t['name']} ({t.get('specialization') or 'Teacher'})", callback_data=f"adm_t_view:{t['id']}")])

    buttons.append([InlineKeyboardButton("➕ Add Teacher", callback_data="adm_t_new")])
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="adm_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def teacher_new_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    db.save_bot_session(uid, "adm_input_t_name", {})
    await query.edit_message_text(
        "➕ <b>Add New Teacher Profile</b>\n\n"
        "Please enter the <b>Full Name</b> of the teacher:\n"
        "<i>(Send name as message)</i>",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# G. Class Schedule Management
# ---------------------------------------------------------------------------

@require_admin
async def schedules_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    schedules = db.query(
        "SELECT cs.*, s.full_name, t.name as teacher_name FROM class_schedules cs "
        "LEFT JOIN students s ON s.id = cs.student_id "
        "LEFT JOIN teachers t ON t.id = cs.teacher_id "
        "ORDER BY cs.scheduled_at DESC LIMIT 6"
    )

    text = "📅 <b>Class Schedule Management</b>\n\nScheduled classes:"
    buttons = []
    if not schedules:
        text += "\nNo scheduled classes."
    else:
        for s in schedules:
            time_s = s["scheduled_at"].replace("T", " ")[:16]
            label = f"{s.get('full_name', 'Student')} @ {time_s}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"adm_sched_view:{s['id']}")])

    buttons.append([InlineKeyboardButton("➕ Schedule a New Class", callback_data="adm_sched_pick_stu")])
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="adm_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


# ---------------------------------------------------------------------------
# H. Learning Progress Entry
# ---------------------------------------------------------------------------

@require_admin
async def progress_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    students = db.query("SELECT * FROM students ORDER BY id DESC LIMIT 8")
    text = "📖 <b>Learning Progress Management</b>\n\nSelect student to record or view progress:"
    buttons = []
    for s in students:
        buttons.append([InlineKeyboardButton(f"👤 {s['full_name']}", callback_data=f"adm_add_prog:{s['id']}")])

    buttons.append([InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="adm_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def add_progress_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    sid = int(query.data.split(":", 1)[1])
    s = db.query_one("SELECT full_name FROM students WHERE id=?", (sid,))

    buttons = [
        [InlineKeyboardButton("🧠 Hifz Progress", callback_data=f"adm_prog_cat:{sid}:hifz")],
        [InlineKeyboardButton("📖 Qaida Progress", callback_data=f"adm_prog_cat:{sid}:qaida")],
        [InlineKeyboardButton("📖 Nezer / Tajweed", callback_data=f"adm_prog_cat:{sid}:tajweed")],
        [InlineKeyboardButton("📚 Kitab Progress", callback_data=f"adm_prog_cat:{sid}:kitab")],
        [InlineKeyboardButton("🔙 Back", callback_data="adm_progress")],
    ]
    await query.edit_message_text(
        f"Select subject to record progress for <b>{s['full_name']}</b>:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML",
    )


@require_admin
async def add_progress_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    parts = query.data.split(":")
    sid = int(parts[1])
    cat = parts[2]

    db.save_bot_session(uid, f"adm_prog_in_{cat}", {"student_id": sid, "category": cat})

    if cat == "hifz":
        msg = (
            "🧠 <b>Record Hifz Progress</b>\n\n"
            "Please send the Surah and Ayah range memorized or revised\n"
            "<i>(Example: Surah Al-Baqarah, Ayahs 1-25. Quality: Excellent)</i>:"
        )
    elif cat == "qaida":
        msg = "📖 <b>Record Qaida Progress</b>\n\nPlease send the current lesson or page completed and notes:"
    elif cat == "kitab":
        msg = "📚 <b>Record Kitab Progress</b>\n\nPlease send the chapter/topic covered and homework task:"
    else:
        msg = "🎙️ <b>Record Recitation Progress</b>\n\nPlease send the recitation topic, lesson, and feedback:"

    await query.edit_message_text(msg, parse_mode="HTML")


# ---------------------------------------------------------------------------
# I. Payment Status Tracking
# ---------------------------------------------------------------------------

@require_admin
async def payments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    pays = db.query(
        "SELECT pr.*, s.full_name FROM payment_records pr "
        "JOIN students s ON s.id = pr.student_id "
        "ORDER BY pr.id DESC LIMIT 8"
    )

    text = "💳 <b>Manual Payment Status Management</b>\n\nRecent student payment records:"
    buttons = []
    if not pays:
        text += "\nNo payment records yet."
    else:
        for p in pays:
            status_ico = "✅" if p["status"] == "paid" else ("⏳" if p["status"] == "awaiting_verification" else "🔴")
            due_val = 0.0 if p.get("amount_due") is None else float(p["amount_due"])
            buttons.append([InlineKeyboardButton(f"{status_ico} {p['full_name']} — {due_val:g} {p['currency']} ({p['status'].upper()})", callback_data=f"adm_pay_view:{p['id']}")])

    buttons.append([InlineKeyboardButton("➕ Record New Payment Due", callback_data="adm_pay_new_pick")])
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="adm_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


# ---------------------------------------------------------------------------
# J. Announcements Broadcast
# ---------------------------------------------------------------------------

@require_admin
async def announcements_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    text = (
        "📢 <b>Broadcast Announcement</b>\n\n"
        "Send an announcement message to students with preview and confirmation.\n"
        "Select your target audience:"
    )
    buttons = [
        [InlineKeyboardButton("📢 All Registered Students", callback_data="adm_ann_aud:all")],
        [InlineKeyboardButton("🟢 Active Students Only", callback_data="adm_ann_aud:active")],
        [InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="adm_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def announcement_audience_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    aud = query.data.split(":", 1)[1]

    db.save_bot_session(uid, "adm_ann_text", {"audience": aud})
    await query.edit_message_text(
        f"📢 <b>Compose Announcement ({aud.upper()} STUDENTS)</b>\n\n"
        "Please type and send the announcement message text below:\n"
        "<i>(You will get a preview before sending)</i>",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# K. Google Sheets
# ---------------------------------------------------------------------------

@require_admin
async def sheets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    status = sheets.status() if hasattr(sheets, "status") else {}
    cfg = "✅ Configured" if status.get("configured") else "❌ Not Configured"
    synced = status.get("synced_registrations", 0)
    pending = status.get("pending", 0)
    failed = status.get("failed", 0)
    last_err = status.get("last_error") or "None"

    text = (
        "📄 <b>Google Sheets Synchronization</b>\n\n"
        f"Status: <b>{cfg}</b>\n"
        f"Worksheet: <code>{status.get('worksheet', 'Registrations')}</code>\n\n"
        f"• Synced Registrations: <b>{synced}</b>\n"
        f"• Pending Queue: <b>{pending}</b>\n"
        f"• Failed Jobs: <b>{failed}</b>\n"
        f"• Last Error: <i>{html.escape(str(last_err))}</i>\n"
    )

    buttons = [
        [InlineKeyboardButton("🔄 Process Queue / Retry Failed", callback_data="adm_sheets_sync_now")],
        [InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="adm_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def sheets_sync_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    res = sheets.process_pending(force=True, limit=50) if hasattr(sheets, "process_pending") else {}
    await query.answer(f"Processed: {res.get('processed', 0)} | Succeeded: {res.get('succeeded', 0)} | Failed: {res.get('failed', 0)}", show_alert=True)
    await sheets_callback(update, context)


# ---------------------------------------------------------------------------
# L. Settings
# ---------------------------------------------------------------------------

@require_admin
async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    academy_name = db.get_setting("academy_name", "Online Quran Academy")
    tagline = db.get_setting("academy_tagline", "Learn the Quran online")
    currency = db.get_setting("default_currency", "ETB")

    text = (
        "⚙️ <b>Academy Settings</b>\n\n"
        f"• <b>Academy Name:</b> {academy_name}\n"
        f"• <b>Tagline:</b> {tagline}\n"
        f"• <b>Default Currency:</b> {currency}\n"
    )
    buttons = [[InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="adm_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Admin Text Messages Dispatcher
# ---------------------------------------------------------------------------

async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    uid = update.effective_user.id
    if not is_authorized_admin(uid):
        return

    text = update.message.text.strip()
    session = db.get_bot_session(uid)
    step = session.get("current_step", "")
    data = session.get("data", {})

    if step == "adm_input_price":
        pid = data.get("program_id")
        try:
            val = float(text)
            new_price = round(val, 2) if val > 0 else None
            db.execute("UPDATE programs SET monthly_price=?, updated_at=? WHERE id=?", (new_price, db.utcnow(), pid))
            db.clear_bot_session(uid)
            p = db.query_one("SELECT name, currency FROM programs WHERE id=?", (pid,))
            p_str = f"{new_price:g} {p['currency']}" if new_price is not None else "Cleared (Contact us)"
            await update.message.reply_text(
                f"✅ Monthly price for <b>{p['name']}</b> updated to <b>{p_str}</b>!",
                reply_markup=admin_main_keyboard(),
                parse_mode="HTML",
            )
        except ValueError:
            await update.message.reply_text("Please enter a valid numeric price (e.g. 500 or 0 to clear):")

    elif step == "adm_input_t_name":
        now = db.utcnow()
        tid = db.execute("INSERT INTO teachers(name, status, created_at, updated_at) VALUES(?, 'active', ?, ?)", (text, now, now))
        db.clear_bot_session(uid)
        await update.message.reply_text(
            f"✅ Teacher <b>{text}</b> added successfully!",
            reply_markup=admin_main_keyboard(),
            parse_mode="HTML",
        )

    elif step.startswith("adm_prog_in_"):
        sid = data.get("student_id")
        cat = data.get("category", "general")
        now = db.utcnow()
        today = now[:10]

        if cat == "hifz":
            db.execute(
                "INSERT INTO learning_progress(student_id, category, entry_date, hifz_surah, recitation_quality, created_at) "
                "VALUES(?, 'hifz', ?, ?, 'Good', ?)",
                (sid, today, text, now),
            )
        elif cat == "qaida":
            db.execute(
                "INSERT INTO learning_progress(student_id, category, entry_date, lesson_completed, created_at) "
                "VALUES(?, 'qaida', ?, ?, ?)",
                (sid, today, text, now),
            )
        else:
            db.execute(
                "INSERT INTO learning_progress(student_id, category, entry_date, lesson_completed, created_at) "
                "VALUES(?, ?, ?, ?, ?)",
                (sid, cat, today, text, now),
            )

        db.clear_bot_session(uid)
        s = db.query_one("SELECT full_name FROM students WHERE id=?", (sid,))
        await update.message.reply_text(
            f"✅ Progress recorded for <b>{s['full_name']}</b>!",
            reply_markup=admin_main_keyboard(),
            parse_mode="HTML",
        )

    elif step == "adm_p_new_name":
        slug_base = re.sub(r'[^a-zA-Z0-9]+', '-', text.lower()).strip('-')
        slug = f"{slug_base}-{str(int(time.time()))[-4:]}"
        now = db.utcnow()
        pid = db.execute(
            "INSERT INTO programs(slug, name, category, description, level_info, age_group, class_format, "
            "currency, active, public_visible, sort_order, created_at, updated_at) "
            "VALUES(?, ?, 'general', ?, 'All levels', 'All ages', 'Online class', 'ETB', 1, 1, 20, ?, ?)",
            (slug, text, f"Structured course: {text}", now, now),
        )
        db.clear_bot_session(uid)
        buttons = [
            [InlineKeyboardButton(f"📚 View {text}", callback_data=f"adm_prog_edit:{pid}")],
            [InlineKeyboardButton("🔙 Back to Courses", callback_data="adm_courses")],
        ]
        await update.message.reply_text(
            f"✅ Course <b>{text}</b> added to catalog!",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML",
        )

    elif step == "adm_k_new_name":
        data["name"] = text
        db.save_bot_session(uid, "adm_k_new_auth", data)
        await update.message.reply_text(
            f"👤 <b>Step 2 of 3: Author / Subject</b>\n\n"
            f"Enter author or subject for <b>{text}</b>:\n"
            f"<i>(e.g., 'Imam an-Nawawi' or 'Classical Scholar')</i>",
            parse_mode="HTML",
        )

    elif step == "adm_k_new_auth":
        data["author"] = text
        db.save_bot_session(uid, "adm_k_new_fee", data)
        await update.message.reply_text(
            f"💰 <b>Step 3 of 3: Monthly Fee</b>\n\n"
            f"Enter monthly fee in ETB for <b>{data.get('name')}</b> (e.g. 1000 or 0 for Contact Academy):",
            parse_mode="HTML",
        )

    elif step == "adm_k_new_fee":
        try:
            val = float(text)
            fee = round(val, 2) if val > 0 else None
        except ValueError:
            fee = None

        name = data.get("name", "New Kitab")
        author = data.get("author", "")
        slug_base = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower()).strip('-')
        slug = f"kitab-{slug_base}-{str(int(time.time()))[-4:]}"
        now = db.utcnow()

        kid = db.execute(
            "INSERT INTO programs(slug, name, category, description, level_info, age_group, class_format, "
            "monthly_price, currency, book_title, author_or_subject, required_materials, active, public_visible, "
            "sort_order, created_at, updated_at) "
            "VALUES(?, ?, 'kitab', ?, 'All levels', 'Youth and adults', 'Online class', ?, 'ETB', ?, ?, 'PDF provided', 1, 1, 15, ?, ?)",
            (slug, name, f"Study of classical text: {name}", fee, name, author, now, now),
        )
        db.clear_bot_session(uid)
        fee_str = f"{fee:g} ETB/mo" if fee is not None else "Contact Academy"
        buttons = [
            [InlineKeyboardButton(f"📖 View {name}", callback_data=f"adm_k_view:{kid}")],
            [InlineKeyboardButton("📚 All Kitabs", callback_data="adm_kitabs")],
            [InlineKeyboardButton("🏠 Admin Menu", callback_data="adm_menu")],
        ]
        await update.message.reply_text(
            f"✅ <b>Kitab Added Successfully!</b>\n\n"
            f"• <b>Title:</b> {name}\n"
            f"• <b>Author:</b> {author or '—'}\n"
            f"• <b>Fee:</b> {fee_str}\n\n"
            f"Students can now browse and register for this Kitab.",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML",
        )

    elif step == "adm_k_in_name":
        kid = data.get("kitab_id")
        db.execute("UPDATE programs SET name=?, book_title=?, updated_at=? WHERE id=?", (text, text, db.utcnow(), kid))
        db.clear_bot_session(uid)
        buttons = [[InlineKeyboardButton("🔙 View Kitab", callback_data=f"adm_k_view:{kid}")]]
        await update.message.reply_text(f"✅ Kitab title updated to <b>{text}</b>!", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

    elif step == "adm_k_in_auth":
        kid = data.get("kitab_id")
        db.execute("UPDATE programs SET author_or_subject=?, updated_at=? WHERE id=?", (text, db.utcnow(), kid))
        db.clear_bot_session(uid)
        buttons = [[InlineKeyboardButton("🔙 View Kitab", callback_data=f"adm_k_view:{kid}")]]
        await update.message.reply_text(f"✅ Kitab author updated to <b>{text}</b>!", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

    elif step == "adm_k_in_fee":
        kid = data.get("kitab_id")
        try:
            val = float(text)
            new_price = round(val, 2) if val > 0 else None
            db.execute("UPDATE programs SET monthly_price=?, updated_at=? WHERE id=?", (new_price, db.utcnow(), kid))
            db.clear_bot_session(uid)
            buttons = [[InlineKeyboardButton("🔙 View Kitab", callback_data=f"adm_k_view:{kid}")]]
            price_str = f"{new_price:g} ETB" if new_price is not None else "Contact Academy"
            await update.message.reply_text(f"✅ Monthly fee updated to <b>{price_str}</b>!", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("Please enter a valid numeric fee (e.g. 1000 or 0 to clear):")

    elif step == "adm_k_in_desc":
        kid = data.get("kitab_id")
        db.execute("UPDATE programs SET description=?, updated_at=? WHERE id=?", (text, db.utcnow(), kid))
        db.clear_bot_session(uid)
        buttons = [[InlineKeyboardButton("🔙 View Kitab", callback_data=f"adm_k_view:{kid}")]]
        await update.message.reply_text("✅ Kitab description updated!", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

    elif step == "adm_k_in_mat":
        kid = data.get("kitab_id")
        db.execute("UPDATE programs SET required_materials=?, updated_at=? WHERE id=?", (text, db.utcnow(), kid))
        db.clear_bot_session(uid)
        buttons = [[InlineKeyboardButton("🔙 View Kitab", callback_data=f"adm_k_view:{kid}")]]
        await update.message.reply_text("✅ Kitab required materials updated!", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


    elif step == "adm_ann_text":
        data["message"] = text
        db.save_bot_session(uid, "adm_ann_confirm", data)
        preview_text = (
            f"📢 <b>Announcement Preview ({data.get('audience', 'all').upper()})</b>\n\n"
            f"{text}\n\n"
            "Send this broadcast to students?"
        )
        buttons = [
            [InlineKeyboardButton("🚀 Confirm & Send Broadcast", callback_data="adm_ann_send_now")],
            [InlineKeyboardButton("❌ Cancel", callback_data="adm_menu")],
        ]
        await update.message.reply_text(preview_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


@require_admin
async def announcement_send_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    session = db.get_bot_session(uid)
    data = session.get("data", {})
    msg_text = data.get("message")
    aud = data.get("audience", "all")
    db.clear_bot_session(uid)

    if not msg_text:
        await query.edit_message_text("No announcement text found.", reply_markup=admin_main_keyboard())
        return

    # Target students
    if aud == "active":
        students = db.query("SELECT telegram_user_id FROM students WHERE status='active' AND telegram_user_id IS NOT NULL")
    else:
        students = db.query("SELECT telegram_user_id FROM students WHERE telegram_user_id IS NOT NULL")

    sent = 0
    token = config.STUDENT_BOT_TOKEN
    for s in students:
        tg_id = s["telegram_user_id"]
        if bridge.send_telegram_message(token, tg_id, f"📢 <b>Academy Announcement</b>\n\n{msg_text}"):
            sent += 1

    db.execute(
        "INSERT INTO announcements(title, message, target_audience, sent_count, created_at) "
        "VALUES('Announcement', ?, ?, ?, ?)",
        (msg_text, aud, sent, db.utcnow()),
    )

    await query.edit_message_text(
        f"✅ <b>Broadcast Completed!</b>\n\nSuccessfully sent to <b>{sent}</b> students.",
        reply_markup=admin_main_keyboard(),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Setup Admin Handlers
# ---------------------------------------------------------------------------

def register_admin_handlers(app) -> None:
    """Register all admin handlers on the Telegram application."""
    app.add_handler(CommandHandler("admin", admin_start_handler))
    app.add_handler(CommandHandler("login", admin_login_handler))
    app.add_handler(CommandHandler("auth", admin_login_handler))

    # In standalone admin bot mode, /start goes to admin menu
    if not config.IS_UNIFIED_MODE:
        app.add_handler(CommandHandler("start", admin_start_handler))

    app.add_handler(CallbackQueryHandler(admin_start_handler, pattern="^adm_menu$"))
    app.add_handler(CallbackQueryHandler(dashboard_callback, pattern="^adm_dash$"))
    app.add_handler(CallbackQueryHandler(registrations_callback, pattern="^adm_regs$"))
    app.add_handler(CallbackQueryHandler(registration_view_callback, pattern="^adm_view:"))
    app.add_handler(CallbackQueryHandler(registration_view_receipt_callback, pattern="^adm_rcpt:"))
    app.add_handler(CallbackQueryHandler(registration_action_callback, pattern="^adm_(appr|rejc|asgn):"))
    app.add_handler(CallbackQueryHandler(registration_assign_teacher_callback, pattern="^adm_do_asgn:"))
    app.add_handler(CallbackQueryHandler(students_callback, pattern="^adm_students$"))
    app.add_handler(CallbackQueryHandler(student_view_callback, pattern="^adm_stu:"))
    app.add_handler(CallbackQueryHandler(courses_callback, pattern="^adm_courses$"))
    app.add_handler(CallbackQueryHandler(course_edit_callback, pattern="^adm_prog_edit:"))
    app.add_handler(CallbackQueryHandler(course_toggle_active_callback, pattern="^adm_toggle_active:"))
    app.add_handler(CallbackQueryHandler(course_new_prompt_callback, pattern="^adm_prog_new$"))
    app.add_handler(CallbackQueryHandler(course_new_gen_callback, pattern="^adm_prog_new_gen$"))
    app.add_handler(CallbackQueryHandler(admin_toggle_btn_details_callback, pattern="^adm_toggle_btn_details$"))
    app.add_handler(CallbackQueryHandler(admin_kitabs_callback, pattern="^adm_kitabs$"))
    app.add_handler(CallbackQueryHandler(admin_kitab_view_callback, pattern="^adm_k_view:"))
    app.add_handler(CallbackQueryHandler(admin_kitab_toggle_callback, pattern="^adm_k_toggle:"))
    app.add_handler(CallbackQueryHandler(admin_kitab_del_ask_callback, pattern="^adm_k_del_ask:"))
    app.add_handler(CallbackQueryHandler(admin_kitab_del_yes_callback, pattern="^adm_k_del_yes:"))
    app.add_handler(CallbackQueryHandler(admin_kitab_new_callback, pattern="^adm_k_new$"))
    app.add_handler(CallbackQueryHandler(admin_kitab_edit_start_callback, pattern="^adm_k_edt_(name|auth|fee|desc|mat):"))
    app.add_handler(CallbackQueryHandler(pricing_callback, pattern="^adm_pricing$"))

    app.add_handler(CallbackQueryHandler(set_price_start_callback, pattern="^adm_set_price:"))
    app.add_handler(CallbackQueryHandler(teachers_callback, pattern="^adm_teachers$"))
    app.add_handler(CallbackQueryHandler(teacher_new_callback, pattern="^adm_t_new$"))
    app.add_handler(CallbackQueryHandler(schedules_callback, pattern="^adm_schedules$"))
    app.add_handler(CallbackQueryHandler(progress_menu_callback, pattern="^adm_progress$"))
    app.add_handler(CallbackQueryHandler(add_progress_start_callback, pattern="^adm_add_prog:"))
    app.add_handler(CallbackQueryHandler(add_progress_category_callback, pattern="^adm_prog_cat:"))
    app.add_handler(CallbackQueryHandler(payments_callback, pattern="^adm_payments$"))
    app.add_handler(CallbackQueryHandler(announcements_callback, pattern="^adm_announcements$"))
    app.add_handler(CallbackQueryHandler(announcement_audience_callback, pattern="^adm_ann_aud:"))
    app.add_handler(CallbackQueryHandler(announcement_send_now_callback, pattern="^adm_ann_send_now$"))
    app.add_handler(CallbackQueryHandler(sheets_callback, pattern="^adm_sheets$"))
    app.add_handler(CallbackQueryHandler(sheets_sync_now_callback, pattern="^adm_sheets_sync_now$"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^adm_settings$"))

    # Text message fallback for admin input
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler))
