"""Student Bot handlers and experience for Online Quran Academy."""
import json
import logging
import os
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
from bot import bridge, config, i18n

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keyboards & Navigation
# ---------------------------------------------------------------------------

def language_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="stu_lang:en"),
            InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="stu_lang:am"),
        ],
        [
            InlineKeyboardButton("🌳 Afaan Oromoo", callback_data="stu_lang:om"),
            InlineKeyboardButton("🇸🇦 العربية", callback_data="stu_lang:ar"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def get_welcome_text(telegram_user_id: int | None = None) -> str:
    academy_name = db.get_setting("academy_name", "Online Quran Academy")
    tagline = db.get_setting("academy_tagline", "Learn the Quran online, from anywhere")
    lang = db.get_user_language(telegram_user_id)
    return i18n.t("welcome_body", lang, academy_name=academy_name, tagline=tagline)


def main_menu_keyboard(telegram_user_id: int | None = None) -> InlineKeyboardMarkup:
    lang = db.get_user_language(telegram_user_id)
    buttons = [
        [
            InlineKeyboardButton(i18n.t("btn_courses", lang), callback_data="stu_courses"),
            InlineKeyboardButton(i18n.t("btn_register", lang), callback_data="stu_reg_start"),
        ],
        [
            InlineKeyboardButton(i18n.t("btn_profile", lang), callback_data="stu_profile"),
        ],
        [
            InlineKeyboardButton(i18n.t("btn_schedule", lang), callback_data="stu_schedule"),
            InlineKeyboardButton(i18n.t("btn_progress", lang), callback_data="stu_progress"),
        ],
        [
            InlineKeyboardButton(i18n.t("btn_help", lang), callback_data="stu_help"),
            InlineKeyboardButton(i18n.t("btn_language", lang), callback_data="stu_pick_lang"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


# ---------------------------------------------------------------------------
# Handlers: Start & Main Menu
# ---------------------------------------------------------------------------

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    uid = user.id if user else None

    # When a user starts the bot, offer Amharic, Oromic, Arabic, and English language options
    text = (
        "🌐 <b>Welcome to Online Quran Academy!</b>\n\n"
        "Please select your preferred language:\n\n"
        "🇪🇹 እባክዎ ቋንቋዎን ይምረጡ፡\n"
        "🌳 Maaloo afaan keessan filadhaa:\n"
        "🇸🇦 الرجاء اختيار لغتكم المفضلة:"
    )
    reply_markup = language_selection_keyboard()

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")


async def language_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id if update.effective_user else None
    lang = query.data.split(":", 1)[1]
    if uid:
        db.set_user_language(uid, lang)

    session = db.get_bot_session(uid) if uid else {}
    step = session.get("current_step", "")
    resume_note = ""
    if step and step.startswith("reg_"):
        resume_note = i18n.t("resume_note", lang)

    text = get_welcome_text(uid) + resume_note
    reply_markup = main_menu_keyboard(uid)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        await query.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")


async def language_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update.effective_user else None
    lang = db.get_user_language(uid)
    text = i18n.t("choose_lang_title", lang)
    reply_markup = language_selection_keyboard()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id if update.effective_user else None
    await query.edit_message_text(get_welcome_text(uid), reply_markup=main_menu_keyboard(uid), parse_mode="HTML")



# ---------------------------------------------------------------------------
# Explore Courses
# ---------------------------------------------------------------------------

async def courses_categories_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id if update.effective_user else None
    lang = db.get_user_language(uid)

    academy_name = db.get_setting("academy_name", "Online Quran Academy")
    show_extra = db.get_setting("show_button_extra_details", False)

    text = i18n.t("courses_title", lang, academy_name=academy_name)
    buttons = [
        [
            InlineKeyboardButton(i18n.t("cat_qaida", lang), callback_data="stu_cat:qaida"),
            InlineKeyboardButton(i18n.t("cat_nezer", lang), callback_data="stu_cat:nezer"),
        ],
        [
            InlineKeyboardButton(i18n.t("cat_tajweed", lang), callback_data="stu_cat:tajweed"),
            InlineKeyboardButton(i18n.t("cat_hifz", lang), callback_data="stu_cat:hifz"),
        ],
        [
            InlineKeyboardButton(i18n.t("cat_kitab", lang), callback_data="stu_cat:kitab"),
        ],
        [
            InlineKeyboardButton(i18n.t("cat_arabic", lang), callback_data="stu_cat:arabic"),
            InlineKeyboardButton(i18n.t("cat_islamic_studies", lang), callback_data="stu_cat:islamic_studies"),
        ],
        [
            InlineKeyboardButton(i18n.t("btn_main_menu", lang), callback_data="stu_menu"),
        ],
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def render_course_details_view(query, p: dict, back_cb: str = "stu_courses", telegram_user_id: int | None = None) -> None:
    """Render comprehensive course details card with clean navigation."""
    uid = telegram_user_id or (query.from_user.id if query and hasattr(query, 'from_user') else None)
    lang = db.get_user_language(uid)
    price = p.get("monthly_price")
    curr = p.get("currency") or "ETB"
    contact_txt = i18n.t("fees_contact", lang)
    price_str = f"<b>{price:g} {curr} / month</b>" if price is not None else f"<i>{contact_txt}</i>"

    lessons = f"{p['lessons_per_week']} lessons / week" if p.get("lessons_per_week") else "Flexible / As scheduled"
    duration = f"{p['lesson_duration_min']} minutes" if p.get("lesson_duration_min") else "Standard lesson"
    fmt = p.get("class_format") or "Online one-to-one or small group"
    age = p.get("age_group") or "All ages"
    level = p.get("level_info") or "Suitable for all levels"

    text = i18n.t(
        "course_detail_card",
        lang,
        name=p['name'],
        desc=p.get('description') or 'Structured Islamic & Quran learning.',
        level=level,
        age=age,
        fmt=fmt,
        duration=duration,
        frequency=lessons,
        fee=price_str,
    )

    if p.get("category") == "kitab":
        b_title = p.get("book_title") or p["name"]
        b_author = p.get("author_or_subject") or "Classical Islamic Scholar"
        b_mat = p.get("required_materials") or "Textbook PDF provided"
        text += (
            f"\n📚 <b>Kitab Information:</b>\n"
            f"• <b>Book Title:</b> {b_title}\n"
            f"• <b>Author / Subject:</b> {b_author}\n"
            f"• <b>Required Materials:</b> {b_mat}\n"
        )
        back_btn_label = i18n.t("btn_back_kitabs", lang)
        back_cb = "stu_cat:kitab"
    else:
        back_btn_label = i18n.t("btn_back_courses", lang)

    buttons = [
        [InlineKeyboardButton(i18n.t("btn_reg_course", lang), callback_data=f"stu_reg_prog:{p['id']}")],
        [InlineKeyboardButton(back_btn_label, callback_data=back_cb)],
        [InlineKeyboardButton(i18n.t("btn_main_menu", lang), callback_data="stu_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def category_courses_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id if update.effective_user else None
    lang = db.get_user_language(uid)

    cat = query.data.split(":", 1)[1]
    cat_title = db.CATEGORIES.get(cat, cat.capitalize())

    progs = db.query(
        "SELECT * FROM programs WHERE category=? AND active=1 AND public_visible=1 ORDER BY sort_order, id",
        (cat,),
    )
    if not progs:
        progs = db.query("SELECT * FROM programs WHERE active=1 AND public_visible=1 ORDER BY sort_order, id")

    show_extra = db.get_setting("show_button_extra_details", False)

    # If Kitab: immediately present the comprehensive list of available Kitabs!
    if cat == "kitab":
        kitabs = db.query(
            "SELECT * FROM programs WHERE category='kitab' AND active=1 AND public_visible=1 ORDER BY sort_order, id"
        )
        text = i18n.t("kitabs_catalog_title", lang)
        buttons = []
        for p in kitabs:
            btn_label = f"📖 {p['name']}" if show_extra else p['name']
            if show_extra and p.get("monthly_price") is not None:
                btn_label += f" ({p['monthly_price']:g} {p.get('currency', 'ETB')})"
            buttons.append([InlineKeyboardButton(btn_label, callback_data=f"stu_prog:{p['id']}")])

        buttons.append([InlineKeyboardButton(i18n.t("btn_back_courses", lang), callback_data="stu_courses")])
        buttons.append([InlineKeyboardButton(i18n.t("btn_main_menu", lang), callback_data="stu_menu")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        return

    # If there is 1 primary course in this category (e.g. Qaida, Nezer, Tajweed, Hifz):
    # Directly display that course's detailed card to showcase it without clutter or truncation!
    if len(progs) == 1:
        await render_course_details_view(query, progs[0], back_cb="stu_courses", telegram_user_id=uid)
        return

    # Multiple courses in category:
    text = f"📂 <b>{cat_title}</b>\n\nSelect a course below:"
    buttons = []
    for p in progs:
        btn_label = p['name']
        if show_extra and p.get("monthly_price") is not None:
            btn_label += f" ({p['monthly_price']:g} {p.get('currency', 'ETB')})"
        buttons.append([InlineKeyboardButton(btn_label, callback_data=f"stu_prog:{p['id']}")])

    buttons.append([InlineKeyboardButton(i18n.t("btn_back_courses", lang), callback_data="stu_courses")])
    buttons.append([InlineKeyboardButton(i18n.t("btn_main_menu", lang), callback_data="stu_menu")])


    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def course_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    prog_id = int(query.data.split(":", 1)[1])
    p = db.query_one("SELECT * FROM programs WHERE id=?", (prog_id,))
    if not p:
        await query.edit_message_text("Course not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="stu_courses")]]))
        return

    await render_course_details_view(query, p)


# ---------------------------------------------------------------------------
# Monthly Fees
# ---------------------------------------------------------------------------

async def fees_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id if update.effective_user else None
    lang = db.get_user_language(uid)

    progs = db.query("SELECT * FROM programs WHERE active=1 AND public_visible=1 ORDER BY sort_order, id")
    text = i18n.t("fees_title", lang)
    contact_txt = i18n.t("fees_contact", lang)
    if not progs:
        text += f"{contact_txt}\n"
    else:
        for p in progs:
            price = p.get("monthly_price")
            curr = p.get("currency") or "ETB"
            p_str = f"<b>{price:g} {curr} / month</b>" if price is not None else f"<i>{contact_txt}</i>"
            text += f"• <b>{p['name']}</b>: {p_str}\n"

    footer_note = db.get_setting("pricing_footer_note", "Submitting registration does not complete payment. The academy will confirm next steps.")
    text += f"\n<i>ℹ️ {footer_note}</i>"

    buttons = [
        [InlineKeyboardButton(i18n.t("btn_register", lang), callback_data="stu_reg_start")],
        [InlineKeyboardButton(i18n.t("btn_main_menu", lang), callback_data="stu_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Registration Wizard: Category -> Identity -> Payment -> Receipt Upload
# ---------------------------------------------------------------------------

def category_keyboard(telegram_user_id: int | None = None) -> InlineKeyboardMarkup:
    lang = db.get_user_language(telegram_user_id)
    buttons = [
        [
            InlineKeyboardButton(i18n.t("cat_qaida", lang), callback_data="stu_reg_cat:qaida"),
            InlineKeyboardButton(i18n.t("cat_nezer", lang), callback_data="stu_reg_cat:nezer"),
        ],
        [
            InlineKeyboardButton(i18n.t("cat_tajweed", lang), callback_data="stu_reg_cat:tajweed"),
            InlineKeyboardButton(i18n.t("cat_hifz", lang), callback_data="stu_reg_cat:hifz"),
        ],
        [
            InlineKeyboardButton(i18n.t("cat_kitab", lang), callback_data="stu_reg_cat:kitab"),
        ],
        [
            InlineKeyboardButton(i18n.t("cat_arabic", lang), callback_data="stu_reg_cat:arabic"),
            InlineKeyboardButton(i18n.t("cat_islamic_studies", lang), callback_data="stu_reg_cat:islamic_studies"),
        ],
        [
            InlineKeyboardButton(i18n.t("btn_cancel", lang), callback_data="stu_reg_cancel"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)



async def reg_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    lang = db.get_user_language(uid)

    # Pre-selection if triggered from course detail: stu_reg_prog:<id>
    if query.data.startswith("stu_reg_prog:"):
        prog_id = int(query.data.split(":", 1)[1])
        prog = db.query_one("SELECT * FROM programs WHERE id=?", (prog_id,))
        if prog:
            cat_key = prog.get("category", "qaida")
            raw_p = prog.get("monthly_price")
            price_val = 1000.0 if raw_p is None else float(raw_p)
            curr = prog.get("currency") or "ETB"
            fee_str = f"{price_val:g} {curr} / month"
            data = {
                "category": cat_key,
                "category_title": prog.get("name", "Quran Program"),
                "program_id": prog["id"],
                "program_name": prog["name"],
                "price": price_val,
                "currency": curr,
            }
            db.save_bot_session(uid, "reg_name", data)
            text = i18n.t("reg_step2_name", lang, course_name=prog['name'], fee=fee_str)
            await query.edit_message_text(text, parse_mode="HTML")
            return

    # Direct registration: Step 1 is Course Category selection
    db.clear_bot_session(uid)
    db.save_bot_session(uid, "reg_cat", {})
    text = i18n.t("reg_step1_cat", lang)
    await query.edit_message_text(text, reply_markup=category_keyboard(uid), parse_mode="HTML")


async def reg_resume_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    session = db.get_bot_session(uid)
    step = session.get("current_step", "reg_cat")
    data = session.get("data", {})
    await prompt_step(query, uid, step, data)


async def reg_fresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    lang = db.get_user_language(uid)
    db.clear_bot_session(uid)
    db.save_bot_session(uid, "reg_cat", {})
    text = i18n.t("reg_step1_cat", lang)
    await query.edit_message_text(text, reply_markup=category_keyboard(uid), parse_mode="HTML")


async def prompt_step(query_or_msg, uid: int, step: str, data: dict) -> None:
    """Helper to render the appropriate prompt for the current step."""
    is_cb = hasattr(query_or_msg, "edit_message_text")
    lang = db.get_user_language(uid)

    if step == "reg_cat":
        msg = i18n.t("reg_step1_cat", lang)
        if is_cb:
            await query_or_msg.edit_message_text(msg, reply_markup=category_keyboard(uid), parse_mode="HTML")
        else:
            await query_or_msg.reply_text(msg, reply_markup=category_keyboard(uid), parse_mode="HTML")

    elif step == "reg_name":
        cat_title = data.get("category_title") or "Selected Course"
        raw_p = data.get("price")
        price_val = 1000.0 if raw_p is None else float(raw_p)
        curr = data.get("currency") or "ETB"
        fee_str = f"{price_val:g} {curr} / month"
        msg = i18n.t("reg_step2_name", lang, course_name=cat_title, fee=fee_str)
        if is_cb:
            await query_or_msg.edit_message_text(msg, parse_mode="HTML")
        else:
            await query_or_msg.reply_text(msg, parse_mode="HTML")

    elif step == "reg_age":
        msg = i18n.t("reg_step3_age", lang, name=data.get('full_name', 'Student'))
        if is_cb:
            await query_or_msg.edit_message_text(msg, parse_mode="HTML")
        else:
            await query_or_msg.reply_text(msg, parse_mode="HTML")

    elif step == "reg_guardian_name":
        msg = i18n.t("reg_step_guardian_name", lang, age=data.get('age', 15))
        if is_cb:
            await query_or_msg.edit_message_text(msg, parse_mode="HTML")
        else:
            await query_or_msg.reply_text(msg, parse_mode="HTML")

    elif step == "reg_guardian_phone":
        msg = i18n.t("reg_step_guardian_phone", lang)
        if is_cb:
            await query_or_msg.edit_message_text(msg, parse_mode="HTML")
        else:
            await query_or_msg.reply_text(msg, parse_mode="HTML")

    elif step == "reg_guardian_rel":
        buttons = [
            [
                InlineKeyboardButton(i18n.t("reg_rel_father", lang), callback_data="stu_reg_rel:Father"),
                InlineKeyboardButton(i18n.t("reg_rel_mother", lang), callback_data="stu_reg_rel:Mother")
            ],
            [
                InlineKeyboardButton(i18n.t("reg_rel_guardian", lang), callback_data="stu_reg_rel:Guardian")
            ],
        ]
        msg = i18n.t("reg_step_guardian_rel", lang)
        if is_cb:
            await query_or_msg.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        else:
            await query_or_msg.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

    elif step == "reg_location":
        msg = i18n.t("reg_step_location", lang)
        if is_cb:
            await query_or_msg.edit_message_text(msg, parse_mode="HTML")
        else:
            await query_or_msg.reply_text(msg, parse_mode="HTML")

    elif step == "reg_phone":
        msg = i18n.t("reg_step_phone", lang)
        if is_cb:
            await query_or_msg.edit_message_text(msg, parse_mode="HTML")
        else:
            await query_or_msg.reply_text(msg, parse_mode="HTML")

    elif step == "reg_schedule":
        buttons = [
            [
                InlineKeyboardButton(i18n.t("sched_morning", lang), callback_data="stu_reg_sched:Morning"),
                InlineKeyboardButton(i18n.t("sched_afternoon", lang), callback_data="stu_reg_sched:Afternoon")
            ],
            [
                InlineKeyboardButton(i18n.t("sched_evening", lang), callback_data="stu_reg_sched:Evening"),
                InlineKeyboardButton(i18n.t("sched_flexible", lang), callback_data="stu_reg_sched:Flexible")
            ],
        ]
        msg = i18n.t("reg_step_schedule", lang)
        if is_cb:
            await query_or_msg.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        else:
            await query_or_msg.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

    elif step == "reg_receipt":
        await render_payment_prompt(query_or_msg, data, is_cb, uid)


async def render_payment_prompt(target, data: dict, is_cb: bool, uid: int | None = None) -> None:
    lang = db.get_user_language(uid)
    cat_title = data.get("category_title") or "Quran Program"
    raw_p = data.get("price")
    price = 1000.0 if raw_p is None else float(raw_p)
    curr = data.get("currency") or "ETB"
    fee_str = f"{price:g} {curr} / month"
    student_name = data.get("full_name", "")
    schedule = data.get("preferred_schedule", "Flexible")

    text = i18n.t(
        "reg_step_payment",
        lang,
        full_name=student_name,
        program_name=cat_title,
        location=data.get('location', ''),
        phone=data.get('phone', ''),
        schedule=schedule,
        fee=fee_str,
    )
    buttons = [
        [InlineKeyboardButton(i18n.t("btn_cancel", lang), callback_data="stu_reg_cancel")],
    ]
    if is_cb:
        await target.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
    else:
        await target.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")



async def wizard_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    uid = update.effective_user.id
    text = update.message.text.strip()

    session = db.get_bot_session(uid)
    step = session.get("current_step", "")
    data = session.get("data", {})

    if not step.startswith("reg_"):
        if step == "contact_msg":
            await handle_contact_submission(update, uid, text)
            return
        if step == "sched_req":
            await handle_schedule_request_submission(update, uid, text)
            return
        if step == "link_reg_id":
            await handle_link_reg_submission(update, uid, text)
            return
        return

    if step == "reg_name":
        if len(text) < 2:
            await update.message.reply_text("Please enter a valid full name:")
            return
        data["full_name"] = text
        db.save_bot_session(uid, "reg_age", data)
        await prompt_step(update.message, uid, "reg_age", data)

    elif step == "reg_age":
        if not text.isdigit() or not (1 <= int(text) <= 120):
            await update.message.reply_text("Please enter a valid age (number between 1 and 120):")
            return
        data["age"] = int(text)
        if data["age"] < 18:
            db.save_bot_session(uid, "reg_guardian_name", data)
            await prompt_step(update.message, uid, "reg_guardian_name", data)
        else:
            db.save_bot_session(uid, "reg_location", data)
            await prompt_step(update.message, uid, "reg_location", data)

    elif step == "reg_guardian_name":
        if len(text) < 2:
            await update.message.reply_text("Please enter the parent or guardian's full name:")
            return
        data["parent_name"] = text[:120]
        db.save_bot_session(uid, "reg_guardian_phone", data)
        await prompt_step(update.message, uid, "reg_guardian_phone", data)

    elif step == "reg_guardian_phone":
        clean_p = text.replace(" ", "").replace("-", "")
        if len(clean_p) < 7:
            await update.message.reply_text("Please enter a valid guardian phone number:")
            return
        data["parent_phone"] = text[:40]
        db.save_bot_session(uid, "reg_guardian_rel", data)
        await prompt_step(update.message, uid, "reg_guardian_rel", data)

    elif step == "reg_location":
        if len(text) < 2:
            await update.message.reply_text("Please enter your Country and City:")
            return
        data["location"] = text[:100]
        db.save_bot_session(uid, "reg_phone", data)
        await prompt_step(update.message, uid, "reg_phone", data)

    elif step == "reg_phone":
        clean_p = text.replace(" ", "").replace("-", "")
        if len(clean_p) < 7:
            await update.message.reply_text("Please enter a valid phone number with country code (e.g. +251911223344):")
            return
        data["phone"] = text[:40]
        db.save_bot_session(uid, "reg_schedule", data)
        await prompt_step(update.message, uid, "reg_schedule", data)

    elif step == "reg_receipt":
        lang = db.get_user_language(uid)
        await update.message.reply_text(
            i18n.t("reg_receipt_prompt", lang),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(i18n.t("btn_cancel", lang), callback_data="stu_reg_cancel")]]),
            parse_mode="HTML",
        )


async def wizard_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    lang = db.get_user_language(uid)
    session = db.get_bot_session(uid)
    data = session.get("data", {})
    cb = query.data

    if cb == "stu_reg_cat:kitab":
        kitabs = db.query("SELECT * FROM programs WHERE category='kitab' AND active=1 AND public_visible=1 ORDER BY sort_order, id")
        buttons = []
        for k in kitabs:
            buttons.append([InlineKeyboardButton(f"📖 {k['name']}", callback_data=f"stu_reg_kitab:{k['id']}")])
        buttons.append([InlineKeyboardButton(i18n.t("btn_back_courses", lang), callback_data="stu_reg_fresh")])
        buttons.append([InlineKeyboardButton(i18n.t("btn_cancel", lang), callback_data="stu_reg_cancel")])
        await query.edit_message_text(
            i18n.t("reg_step1_kitab", lang),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML",
        )
        return

    elif cb.startswith("stu_reg_kitab:"):
        kid = int(cb.split(":", 1)[1])
        k = db.query_one("SELECT * FROM programs WHERE id=?", (kid,))
        if k:
            raw_p = k.get("monthly_price")
            price_val = 1000.0 if raw_p is None else float(raw_p)
            curr = k.get("currency") or "ETB"
            data["category"] = "kitab"
            data["category_title"] = f"Kitab: {k['name']}"
            data["program_id"] = k["id"]
            data["program_name"] = k["name"]
            data["price"] = price_val
            data["currency"] = curr
        db.save_bot_session(uid, "reg_name", data)
        raw_p = data.get("price")
        price_val = 1000.0 if raw_p is None else float(raw_p)
        curr = data.get("currency") or "ETB"
        fee_str = f"{price_val:g} {curr} / month"
        await query.edit_message_text(
            i18n.t("reg_step2_name", lang, course_name=data.get('program_name'), fee=fee_str),
            parse_mode="HTML",
        )
        return

    elif cb.startswith("stu_reg_cat:"):
        cat_key = cb.split(":", 1)[1]
        cat_title = i18n.t(f"cat_{cat_key}", lang) if cat_key in db.CATEGORIES else cat_key.capitalize()
        data["category"] = cat_key
        data["category_title"] = cat_title

        # Look up program and monthly price for this category
        p = db.query_one("SELECT * FROM programs WHERE category=? AND active=1 ORDER BY sort_order, id LIMIT 1", (cat_key,))
        if p:
            raw_p = p.get("monthly_price")
            price_val = 1000.0 if raw_p is None else float(raw_p)
            curr = p.get("currency") or "ETB"
            data["program_id"] = p["id"]
            data["program_name"] = p["name"]
            data["price"] = price_val
            data["currency"] = curr
        else:
            data["program_id"] = None
            data["program_name"] = cat_title
            data["price"] = 1000.0
            data["currency"] = "ETB"

        db.save_bot_session(uid, "reg_name", data)
        raw_p = data.get("price")
        price_val = 1000.0 if raw_p is None else float(raw_p)
        curr = data.get("currency") or "ETB"
        fee_str = f"{price_val:g} {curr} / month"
        await query.edit_message_text(
            i18n.t("reg_step2_name", lang, course_name=cat_title, fee=fee_str),
            parse_mode="HTML",
        )

    elif cb.startswith("stu_reg_rel:"):
        data["parent_relationship"] = cb.split(":", 1)[1]
        db.save_bot_session(uid, "reg_location", data)
        await prompt_step(query, uid, "reg_location", data)

    elif cb.startswith("stu_reg_sched:"):
        data["preferred_schedule"] = cb.split(":", 1)[1]
        db.save_bot_session(uid, "reg_receipt", data)
        await prompt_step(query, uid, "reg_receipt", data)

    elif cb == "stu_reg_cancel":
        db.clear_bot_session(uid)
        await query.edit_message_text(
            i18n.t("reg_cancelled", lang),
            reply_markup=main_menu_keyboard(uid),
        )


async def receipt_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    uid = update.effective_user.id
    session = db.get_bot_session(uid)
    step = session.get("current_step", "")
    data = session.get("data", {})

    if step != "reg_receipt":
        return

    photo_obj = None
    if update.message.photo:
        photo_obj = update.message.photo[-1]
    elif update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith("image/"):
        photo_obj = update.message.document

    if not photo_obj:
        await update.message.reply_text("Please upload an image or photo of your payment receipt.")
        return

    file_id = photo_obj.file_id
    reg_id = db.gen_reg_id()
    now = db.utcnow()
    username = update.effective_user.username or ""

    # Ensure receipts directory exists and download photo
    receipts_dir = os.path.join(os.path.dirname(db.DB_PATH), "receipts")
    os.makedirs(receipts_dir, exist_ok=True)
    local_path = os.path.join(receipts_dir, f"{reg_id}.jpg")

    try:
        tg_file = await photo_obj.get_file()
        await tg_file.download_to_drive(custom_path=local_path)
    except Exception as ex:
        log.warning("Could not download receipt to drive: %s", ex)
        local_path = ""

    # Parse location
    loc = data.get("location", "")
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    country = parts[0] if len(parts) == 1 else parts[-1]
    city = parts[0] if len(parts) > 1 else ""

    cat_title = data.get("category_title") or "Quran Program"
    raw_p = data.get("price")
    price = 1000.0 if raw_p is None else float(raw_p)
    curr = data.get("currency") or "ETB"

    with db.tx() as conn:
        cur = conn.execute(
            "INSERT INTO students(full_name, age, country, city, phone, whatsapp, email, "
            "parent_name, parent_phone, telegram_user_id, telegram_username, status, created_at, updated_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_verification', ?, ?)",
            (
                data["full_name"],
                data.get("age"),
                country,
                city,
                data.get("phone", ""),
                data.get("phone", ""),
                "",
                data.get("parent_name", ""),
                data.get("parent_phone", ""),
                uid,
                username,
                now,
                now,
            ),
        )
        student_id = cur.lastrowid
        conn.execute(
            "INSERT INTO registrations(reg_id, student_id, program_id, program_name_snapshot, "
            "monthly_price_snapshot, currency_snapshot, reading_level, preferred_schedule, class_format, "
            "parent_relationship, telegram_user_id, status, receipt_file_id, receipt_url, category_snapshot, "
            "created_at, updated_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_verification', ?, ?, ?, ?, ?)",
            (
                reg_id,
                student_id,
                data.get("program_id"),
                data.get("program_name") or cat_title,
                price,
                curr,
                cat_title,
                data.get("preferred_schedule", "Flexible"),
                "Online Class",
                data.get("parent_relationship", ""),
                uid,
                file_id,
                local_path,
                data.get("category", "qaida"),
                now,
                now,
            ),
        )
        conn.execute(
            "INSERT INTO payment_records(student_id, reg_id, program_id, amount_due, amount_received, "
            "currency, status, receipt_file_id, receipt_url, created_at, updated_at) "
            "VALUES(?, ?, ?, ?, 0.0, ?, 'pending_verification', ?, ?, ?, ?)",
            (
                student_id,
                reg_id,
                data.get("program_id"),
                price,
                curr,
                file_id,
                local_path,
                now,
                now,
            ),
        )

    db.clear_bot_session(uid)
    sheets.enqueue_registration(reg_id)

    full_reg = db.query_one(
        "SELECT r.*, s.full_name, s.age, s.country, s.city, s.phone, s.whatsapp, s.email, "
        "s.parent_name, s.parent_phone "
        "FROM registrations r JOIN students s ON s.id=r.student_id WHERE r.reg_id=?",
        (reg_id,),
    )
    if full_reg:
        bridge.notify_admins_new_registration(full_reg)

    lang = db.get_user_language(uid)
    confirmation_msg = i18n.t("reg_success", lang, reg_id=reg_id, program_name=cat_title)
    buttons = [
        [InlineKeyboardButton(i18n.t("btn_profile", lang), callback_data="stu_profile")],
        [InlineKeyboardButton(i18n.t("btn_main_menu", lang), callback_data="stu_menu")],
    ]
    await update.message.reply_text(confirmation_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Student Profile
# ---------------------------------------------------------------------------

async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    uid = update.effective_user.id
    lang = db.get_user_language(uid)
    if query:
        await query.answer()

    student = db.get_student_by_telegram_id(uid)
    if not student:
        text = i18n.t("profile_not_registered", lang)
        buttons = [
            [InlineKeyboardButton(i18n.t("btn_register", lang), callback_data="stu_reg_start")],
            [InlineKeyboardButton("🔗 Link Existing Registration", callback_data="stu_link_start")],
            [InlineKeyboardButton(i18n.t("btn_main_menu", lang), callback_data="stu_menu")],
        ]
        if query:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        elif update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        return

    regs = db.get_student_registrations(student["id"])
    active_reg = regs[0] if regs else None

    reg_id_str = active_reg["reg_id"] if active_reg else "—"
    status_str = (active_reg["status"] if active_reg else student.get("status", "new")).upper()
    prog_str = active_reg["program_name_snapshot"] if active_reg else "Quran Program"
    price_val = active_reg.get("monthly_price_snapshot") if active_reg else None
    curr_val = active_reg.get("currency_snapshot") if active_reg else "ETB"
    price_str = f"{price_val:g} {curr_val}/mo" if price_val is not None else "Contact Academy"

    # Teacher assignment check
    assignment = db.query_one(
        "SELECT t.name FROM teacher_assignments ta JOIN teachers t ON t.id = ta.teacher_id "
        "WHERE ta.student_id=? AND ta.status='active' LIMIT 1",
        (student["id"],),
    )
    teacher_name = assignment["name"] if assignment else "Pending assignment"

    # Next schedule check
    next_class = db.query_one(
        "SELECT scheduled_at, timezone FROM class_schedules "
        "WHERE student_id=? AND status='scheduled' AND scheduled_at >= datetime('now') "
        "ORDER BY scheduled_at ASC LIMIT 1",
        (student["id"],),
    )
    sched_str = next_class["scheduled_at"].replace("T", " ")[:16] if next_class else "No upcoming classes"

    text = (
        f"👤 <b>Student Profile</b>\n\n"
        f"🆔 <b>Registration ID:</b> <code>{reg_id_str}</code>\n"
        f"👤 <b>Name:</b> {student['full_name']}\n"
        f"📊 <b>Status:</b> <b>{status_str}</b>\n"
        f"📚 <b>Program:</b> {prog_str}\n"
        f"💰 <b>Monthly Fee:</b> {price_str}\n"
        f"👨‍🏫 <b>Assigned Teacher:</b> {teacher_name}\n"
        f"📅 <b>Next Class:</b> {sched_str}\n"
        f"📞 <b>Contact:</b> {student['phone']}\n"
    )

    buttons = [
        [
            InlineKeyboardButton("📚 My Courses", callback_data="stu_my_courses"),
            InlineKeyboardButton("📅 My Schedule", callback_data="stu_schedule"),
        ],
        [
            InlineKeyboardButton("📊 My Progress", callback_data="stu_progress"),
            InlineKeyboardButton("🔄 Change Schedule", callback_data="stu_req_sched_start"),
        ],
        [
            InlineKeyboardButton("✏️ Update Contact", callback_data="stu_edit_contact"),
            InlineKeyboardButton("❓ Contact Academy", callback_data="stu_contact_admin"),
        ],
        [
            InlineKeyboardButton("🏠 Main Menu", callback_data="stu_menu"),
        ],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def my_courses_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    student = db.get_student_by_telegram_id(uid)
    if not student:
        await profile_callback(update, context)
        return

    regs = db.get_student_registrations(student["id"])
    text = "📚 <b>My Enrolled & Registered Courses</b>\n\n"
    if not regs:
        text += "No active courses found."
    else:
        for r in regs:
            price = r.get("monthly_price_snapshot")
            curr = r.get("currency_snapshot") or "ETB"
            p_txt = f"{price:g} {curr}/mo" if price is not None else "Contact Academy"
            text += (
                f"• <b>{r['program_name_snapshot']}</b>\n"
                f"  ID: <code>{r['reg_id']}</code> | Status: {r['status'].upper()}\n"
                f"  Fee: {p_txt} | Schedule: {r['preferred_schedule']}\n\n"
            )

    buttons = [[InlineKeyboardButton("🔙 Back to Profile", callback_data="stu_profile")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Class Schedule
# ---------------------------------------------------------------------------

async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    student = db.get_student_by_telegram_id(uid)
    if not student:
        text = "📅 <b>Class Schedule</b>\n\nYou must be a registered student to view your class schedule."
        buttons = [
            [InlineKeyboardButton("📝 Register as a Student", callback_data="stu_reg_start")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="stu_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        return

    schedules = db.get_student_schedule(student["id"])
    text = "📅 <b>Your Class Schedule</b>\n\n"
    if not schedules:
        text += (
            "No upcoming classes currently scheduled.\n"
            "Once the academy or your teacher schedules your classes, they will appear here "
            "with meeting links and reminder times."
        )
    else:
        for s in schedules:
            t_str = s["scheduled_at"].replace("T", " ")[:16]
            teacher = s.get("teacher_name") or "Assigned Teacher"
            link = f"\n  🔗 <a href='{s['meeting_link']}'>Join Online Class</a>" if s.get("meeting_link") else "\n  <i>Meeting link will be shared before class</i>"
            text += (
                f"• <b>{s['title']}</b>\n"
                f"  📅 {t_str} ({s.get('timezone', 'UTC')})\n"
                f"  👨‍🏫 Teacher: {teacher} | ⏱ {s.get('duration_min', 45)} min"
                f"{link}\n\n"
            )

    buttons = [
        [InlineKeyboardButton("🔄 Request Schedule Change", callback_data="stu_req_sched_start")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="stu_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML", disable_web_page_preview=True)


# ---------------------------------------------------------------------------
# Learning Progress
# ---------------------------------------------------------------------------

async def progress_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    student = db.get_student_by_telegram_id(uid)
    if not student:
        text = "📊 <b>My Learning Progress</b>\n\nYou must be a registered student to view learning progress."
        buttons = [
            [InlineKeyboardButton("📝 Register as a Student", callback_data="stu_reg_start")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="stu_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        return

    progress = db.get_student_progress(student["id"])
    text = "📊 <b>My Learning & Hifz Progress</b>\n\n"
    if not progress:
        text += (
            "<i>No progress records have been entered by your teacher yet.</i>\n\n"
            "As you complete lessons, your teacher will record your Hifz, Tajweed, Nezer, "
            "Qaida, and Kitab milestones here."
        )
    else:
        for p in progress[:8]:  # Show latest entries
            cat = p.get("category", "general")
            entry_d = p.get("entry_date", "")[:10]
            teacher = p.get("teacher_name") or "Teacher"

            if cat == "hifz":
                text += (
                    f"📖 <b>Hifz — {entry_d}</b> (by {teacher})\n"
                    f"• <b>Surah & Ayahs:</b> {p.get('hifz_surah')} {p.get('hifz_ayah_range')}\n"
                    f"• <b>New Memorization:</b> {p.get('hifz_new_memo') or 'Completed'}\n"
                    f"• <b>Revision (Muraja'ah):</b> {p.get('hifz_revision') or 'Reviewed'}\n"
                    f"• <b>Quality:</b> {p.get('recitation_quality') or 'Good'}\n"
                    f"• <b>Next Target:</b> {p.get('next_target') or '—'}\n"
                )
            elif cat == "qaida":
                text += (
                    f"📖 <b>Qaida — {entry_d}</b> (by {teacher})\n"
                    f"• <b>Lesson/Page:</b> {p.get('lesson_completed')}\n"
                    f"• <b>Level:</b> {p.get('reading_level') or 'In progress'}\n"
                    f"• <b>Next Lesson:</b> {p.get('next_target') or '—'}\n"
                )
            elif cat == "kitab":
                text += (
                    f"📚 <b>Kitab — {entry_d}</b> (by {teacher})\n"
                    f"• <b>Lesson & Chapter:</b> {p.get('lesson_completed')}\n"
                    f"• <b>Topics Covered:</b> {p.get('topics_covered') or 'Reviewed'}\n"
                    f"• <b>Homework/Task:</b> {p.get('next_target') or 'None'}\n"
                )
            else:
                text += (
                    f"🎙️ <b>{cat.capitalize()} — {entry_d}</b> (by {teacher})\n"
                    f"• <b>Lesson:</b> {p.get('lesson_completed')}\n"
                    f"• <b>Areas to Improve:</b> {p.get('areas_improvement') or 'None'}\n"
                    f"• <b>Recommended Practice:</b> {p.get('next_target') or 'Continue practice'}\n"
                )
            if p.get("teacher_notes"):
                text += f"• <i>Teacher Note:</i> {p['teacher_notes']}\n"
            text += "\n"

    buttons = [
        [InlineKeyboardButton("👤 Back to Profile", callback_data="stu_profile")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="stu_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Help, FAQ & Contact
# ---------------------------------------------------------------------------

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    uid = update.effective_user.id if update.effective_user else None
    lang = db.get_user_language(uid)
    if query:
        await query.answer()

    text = i18n.t("help_title", lang)
    buttons = [
        [InlineKeyboardButton("❓ Frequently Asked Questions", callback_data="stu_faqs")],
        [InlineKeyboardButton("✉️ Contact the Academy", callback_data="stu_contact_admin")],
        [InlineKeyboardButton("🔄 Request Schedule Change", callback_data="stu_req_sched_start")],
        [InlineKeyboardButton(i18n.t("btn_main_menu", lang), callback_data="stu_menu")],
    ]
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def faqs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    faqs = db.query("SELECT * FROM faqs WHERE visible=1 ORDER BY sort_order, id LIMIT 6")
    text = "❓ <b>Frequently Asked Questions</b>\n\n"
    for f in faqs:
        text += f"<b>Q: {f['question']}</b>\n{f['answer']}\n\n"

    buttons = [
        [InlineKeyboardButton("✉️ Still Have Questions? Contact Us", callback_data="stu_contact_admin")],
        [InlineKeyboardButton("🔙 Back to Help", callback_data="stu_help")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def contact_admin_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    db.save_bot_session(uid, "contact_msg", {})
    await query.edit_message_text(
        "✉️ <b>Contact the Academy</b>\n\n"
        "Please type and send your question, inquiry, or message.\n"
        "An academy administrator will review it and reply back to you.\n\n"
        "<i>(Type your message below and send)</i>",
        parse_mode="HTML",
    )


async def handle_contact_submission(update: Update, uid: int, msg_text: str) -> None:
    now = db.utcnow()
    user = update.effective_user
    name = user.full_name or "Telegram User"
    username = f" (@{user.username})" if user.username else ""

    db.execute(
        "INSERT INTO contact_messages(name, email, phone, message, is_read, created_at) "
        "VALUES(?, ?, ?, ?, 0, ?)",
        (f"{name}{username} [TG:{uid}]", "", "", msg_text, now),
    )
    db.clear_bot_session(uid)

    # Notify admins
    for aid in db.get_all_admin_telegram_ids(config.ADMIN_TELEGRAM_IDS):
        bridge.send_telegram_message(
            config.ADMIN_BOT_TOKEN,
            aid,
            f"📬 <b>New Contact Message</b>\n\n"
            f"From: <b>{name}</b> (ID: <code>{uid}</code>)\n"
            f"Message: {msg_text}",
        )

    await update.message.reply_text(
        "✅ <b>Message Sent!</b>\n\n"
        "Thank you. Your message has been received and the academy administrator will reply soon.",
        reply_markup=main_menu_keyboard(uid),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Schedule Change Request
# ---------------------------------------------------------------------------

async def req_sched_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    student = db.get_student_by_telegram_id(uid)
    if not student:
        await query.edit_message_text(
            "You must have an active registration to request a schedule change.",
            reply_markup=main_menu_keyboard(uid),
        )
        return

    db.save_bot_session(uid, "sched_req", {"student_id": student["id"]})
    await query.edit_message_text(
        "🔄 <b>Request a Schedule Change</b>\n\n"
        "Please describe your requested schedule change (preferred days, new time, or reason):\n\n"
        "<i>(Type your request below and send)</i>",
        parse_mode="HTML",
    )


async def handle_schedule_request_submission(update: Update, uid: int, details: str) -> None:
    now = db.utcnow()
    student = db.get_student_by_telegram_id(uid)
    sid = student["id"] if student else None

    db.execute(
        "INSERT INTO schedule_requests(student_id, request_type, details, status, created_at, updated_at) "
        "VALUES(?, 'reschedule', ?, 'pending', ?, ?)",
        (sid, details, now, now),
    )
    db.clear_bot_session(uid)

    # Notify admins
    for aid in db.get_all_admin_telegram_ids(config.ADMIN_TELEGRAM_IDS):
        bridge.send_telegram_message(
            config.ADMIN_BOT_TOKEN,
            aid,
            f"📅 <b>Schedule Change Request</b>\n\n"
            f"Student: <b>{student['full_name'] if student else 'Student'}</b>\n"
            f"Details: {details}",
        )

    await update.message.reply_text(
        "✅ <b>Schedule Change Request Submitted!</b>\n\n"
        "Your request has been sent to the academy administration. You will receive an update once reviewed.",
        reply_markup=main_menu_keyboard(uid),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Account Linking
# ---------------------------------------------------------------------------

async def link_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    db.save_bot_session(uid, "link_reg_id", {})
    await query.edit_message_text(
        "🔗 <b>Link Website Registration</b>\n\n"
        "Please enter your <b>Registration ID</b> (e.g. <code>QA-261012-ABCDEF</code>):\n\n"
        "<i>(Type your Registration ID below and send)</i>",
        parse_mode="HTML",
    )


async def handle_link_reg_submission(update: Update, uid: int, text: str) -> None:
    session = db.get_bot_session(uid)
    data = session.get("data", {})

    if "reg_id" not in data:
        reg_id = text.strip().upper()
        reg = db.get_registration_by_id(reg_id) if hasattr(db, "get_registration_by_id") else db.query_one("SELECT * FROM registrations WHERE reg_id=?", (reg_id,))
        if not reg:
            await update.message.reply_text("Registration ID not found. Please check and re-enter:")
            return
        data["reg_id"] = reg_id
        db.save_bot_session(uid, "link_phone", data)
        await update.message.reply_text("Please enter the <b>Phone Number</b> used during registration to verify your identity:")
        return

    # Second step: phone verification
    reg_id = data["reg_id"]
    phone = text.strip()
    username = update.effective_user.username or ""
    linked = db.link_telegram_to_registration(reg_id, phone, uid, username)
    db.clear_bot_session(uid)

    if not linked:
        await update.message.reply_text(
            "❌ <b>Verification Failed</b>\n\n"
            "The phone number entered did not match the registration record.\n"
            "Please contact the academy if you need assistance.",
            reply_markup=main_menu_keyboard(uid),
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        f"✅ <b>Account Successfully Linked!</b>\n\n"
        f"Your Telegram account is now connected to registration <code>{reg_id}</code> ({linked['full_name']}).",
        reply_markup=main_menu_keyboard(uid),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Setup Student Handlers
# ---------------------------------------------------------------------------

def register_student_handlers(app) -> None:
    """Register all student handlers on the Telegram application."""
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler(["language", "lang"], language_menu_callback))
    app.add_handler(CommandHandler("courses", lambda u, c: courses_categories_callback(u, c)))
    app.add_handler(CommandHandler("profile", lambda u, c: profile_callback(u, c)))
    app.add_handler(CommandHandler("schedule", lambda u, c: schedule_callback(u, c)))
    app.add_handler(CommandHandler("help", lambda u, c: help_callback(u, c)))

    # Language selection callbacks
    app.add_handler(CallbackQueryHandler(language_menu_callback, pattern="^stu_pick_lang$"))
    app.add_handler(CallbackQueryHandler(language_select_callback, pattern="^stu_lang:(en|am|om|ar)$"))

    # Callback queries
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^stu_menu$"))
    app.add_handler(CallbackQueryHandler(courses_categories_callback, pattern="^stu_courses$"))
    app.add_handler(CallbackQueryHandler(category_courses_callback, pattern="^stu_cat:"))
    app.add_handler(CallbackQueryHandler(course_details_callback, pattern="^stu_prog:"))
    app.add_handler(CallbackQueryHandler(fees_callback, pattern="^stu_fees$"))
    app.add_handler(CallbackQueryHandler(profile_callback, pattern="^stu_profile$"))
    app.add_handler(CallbackQueryHandler(my_courses_callback, pattern="^stu_my_courses$"))
    app.add_handler(CallbackQueryHandler(schedule_callback, pattern="^stu_schedule$"))
    app.add_handler(CallbackQueryHandler(progress_callback, pattern="^stu_progress$"))
    app.add_handler(CallbackQueryHandler(help_callback, pattern="^stu_help$"))
    app.add_handler(CallbackQueryHandler(faqs_callback, pattern="^stu_faqs$"))
    app.add_handler(CallbackQueryHandler(contact_admin_start_callback, pattern="^stu_contact_admin$"))
    app.add_handler(CallbackQueryHandler(req_sched_start_callback, pattern="^stu_req_sched_start$"))
    app.add_handler(CallbackQueryHandler(link_start_callback, pattern="^stu_link_start$"))

    # Wizard callbacks
    app.add_handler(CallbackQueryHandler(reg_start_callback, pattern="^stu_reg_start$"))
    app.add_handler(CallbackQueryHandler(reg_start_callback, pattern="^stu_reg_prog:"))
    app.add_handler(CallbackQueryHandler(reg_resume_callback, pattern="^stu_reg_resume$"))
    app.add_handler(CallbackQueryHandler(reg_fresh_callback, pattern="^stu_reg_fresh$"))
    app.add_handler(CallbackQueryHandler(wizard_callback_handler, pattern="^stu_reg_"))

    # Text message fallback for wizard input
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, wizard_text_handler))

    # Photo / screenshot receipt upload
    app.add_handler(MessageHandler(filters.PHOTO | (filters.Document.IMAGE & ~filters.COMMAND), receipt_photo_handler))
