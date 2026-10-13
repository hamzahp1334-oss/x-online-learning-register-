"""Public website pages and public APIs."""
import threading

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

import db
import notify
import sheets
from auth import contact_limiter, register_limiter
from validators import validate_contact, validate_registration

bp = Blueprint("public", __name__)


def _program_view(p: dict) -> dict:
    price = p["monthly_price"]
    return {
        "id": p["id"],
        "slug": p["slug"],
        "name": p["name"],
        "description": p["description"],
        "level_info": p["level_info"],
        "age_group": p["age_group"],
        "class_format": p["class_format"],
        "monthly_price": price,
        "has_price": price is not None,
        "currency": p["currency"],
        "lessons_per_week": p["lessons_per_week"],
        "lesson_duration_min": p["lesson_duration_min"],
        "included_services": [s.strip() for s in (p["included_services"] or "").splitlines()
                              if s.strip()],
    }


def public_programs() -> list[dict]:
    rows = db.query(
        "SELECT * FROM programs WHERE active=1 AND public_visible=1 "
        "ORDER BY sort_order, id")
    return [_program_view(p) for p in rows]


# ------------------------------------------------------------------ pages

@bp.get("/")
def home():
    return render_template("home.html", programs=public_programs()[:3],
                           program_count=len(public_programs()))


@bp.get("/programs")
def programs_page():
    return render_template("programs.html", programs=public_programs())


@bp.get("/pricing")
def pricing_page():
    settings_note = db.get_setting("pricing_footer_note")
    discount_note = db.get_setting("discount_note")
    return render_template("pricing.html", programs=public_programs(),
                           pricing_note=settings_note, discount_note=discount_note)


@bp.get("/register")
def register_page():
    preselect = request.args.get("program", "")
    return render_template("register.html", programs=public_programs(),
                           preselect=preselect)


@bp.get("/register/success/<reg_id>")
def register_success(reg_id: str):
    reg = db.query_one(
        "SELECT r.reg_id, r.created_at, r.program_name_snapshot, "
        "r.monthly_price_snapshot, r.currency_snapshot, s.full_name "
        "FROM registrations r JOIN students s ON s.id = r.student_id "
        "WHERE r.reg_id = ? AND r.archived_at IS NULL", (reg_id,))
    if reg is None:
        abort(404)
    return render_template("register_success.html", reg=reg)


@bp.get("/about")
def about_page():
    import json
    sections = []
    try:
        sections = json.loads(db.get_setting("about_sections") or "[]")
    except (ValueError, TypeError):
        sections = []
    return render_template("about.html", sections=sections)


@bp.get("/faq")
def faq_page():
    faqs = db.query("SELECT * FROM faqs WHERE visible=1 ORDER BY sort_order, id")
    return render_template("faq.html", faqs=faqs)


@bp.get("/contact")
def contact_page():
    return render_template("contact.html")


# ------------------------------------------------------------------ public APIs

@bp.get("/api/programs")
def api_programs():
    return jsonify({"programs": public_programs()})


@bp.post("/api/register")
def api_register():
    ip = request.remote_addr or "unknown"
    if not register_limiter.allow(f"reg:{ip}"):
        return jsonify({"error": "Too many submissions from this device. Please try again later."}), 429

    payload = request.get_json(silent=True) or {}
    errors, data = validate_registration(payload)

    program = None
    if not errors or (payload.get("program_slug") or payload.get("program_id")):
        prog = None
        if payload.get("program_slug"):
            prog = db.query_one(
                "SELECT * FROM programs WHERE slug=? AND active=1 AND public_visible=1",
                (str(payload["program_slug"]).strip(),))
        elif payload.get("program_id"):
            try:
                prog = db.query_one(
                    "SELECT * FROM programs WHERE id=? AND active=1 AND public_visible=1",
                    (int(payload["program_id"]),))
            except (TypeError, ValueError):
                prog = None
        if prog is None:
            errors["program"] = "Please select an available program."
        else:
            program = prog

    if errors:
        return jsonify({"error": "Please correct the highlighted fields.",
                        "field_errors": errors}), 400

    # Guard against duplicate rapid submissions (e.g. double-clicked submit).
    recent = db.query_one(
        "SELECT r.reg_id FROM registrations r JOIN students s ON s.id=r.student_id "
        "WHERE s.phone=? AND r.program_id=? AND r.archived_at IS NULL "
        "AND r.created_at >= datetime('now', '-2 minutes') "
        "ORDER BY r.created_at DESC LIMIT 1",
        (data["phone"], program["id"]))
    if recent:
        return jsonify({"reg_id": recent["reg_id"], "duplicate": True,
                        "redirect": url_for("public.register_success",
                                            reg_id=recent["reg_id"])})

    now = db.utcnow()
    reg_id = db.gen_reg_id()
    with db.tx() as conn:
        cur = conn.execute(
            "INSERT INTO students(full_name, age, country, city, phone, whatsapp, "
            "email, gender, parent_name, parent_phone, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (data["full_name"], data["age"], data["country"], data["city"],
             data["phone"], data.get("whatsapp", ""), data.get("email", ""),
             data.get("gender", ""), data.get("parent_name", ""),
             data.get("parent_phone", ""), now, now))
        student_id = cur.lastrowid
        conn.execute(
            "INSERT INTO registrations(reg_id, student_id, program_id, "
            "program_name_snapshot, monthly_price_snapshot, currency_snapshot, "
            "reading_level, preferred_schedule, class_format, previous_experience, "
            "learning_goals, referral_source, status, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'new', ?, ?)",
            (reg_id, student_id, program["id"], program["name"],
             program["monthly_price"], program["currency"],
             data["reading_level"], data["preferred_schedule"],
             data.get("class_format", ""), data.get("previous_experience", ""),
             data.get("learning_goals", ""), data.get("referral_source", ""),
             now, now))

    # Durable sync queue: registration is saved first; Sheets is only a copy.
    sheets.enqueue_registration(reg_id)
    if sheets.is_configured():
        threading.Thread(
            target=lambda: _safe_process(),
            daemon=True, name=f"sync-{reg_id}").start()

    reg = db.query_one(
        "SELECT r.*, s.full_name, s.age, s.country, s.city, s.phone, s.whatsapp, s.email "
        "FROM registrations r JOIN students s ON s.id=r.student_id WHERE r.reg_id=?",
        (reg_id,))
    notify.notify_admin_new_registration({**reg})
    notify.send_student_confirmation(
        {**reg, "full_name": reg["full_name"]}, data.get("email", ""))

    try:
        from bot import bridge
        bridge.notify_admins_new_registration({**reg})
    except Exception:
        pass

    return jsonify({"reg_id": reg_id,
                    "redirect": url_for("public.register_success", reg_id=reg_id)}), 201


def _safe_process():
    try:
        sheets.process_pending(force=False, limit=10)
    except Exception:
        pass


@bp.post("/api/contact")
def api_contact():
    ip = request.remote_addr or "unknown"
    if not contact_limiter.allow(f"contact:{ip}"):
        return jsonify({"error": "Too many messages from this device. Please try again later."}), 429
    payload = request.get_json(silent=True) or {}
    errors, data = validate_contact(payload)
    if errors:
        return jsonify({"error": "Please correct the highlighted fields.",
                        "field_errors": errors}), 400
    db.execute(
        "INSERT INTO contact_messages(name, email, phone, message, created_at) "
        "VALUES(?,?,?,?,?)",
        (data["name"], data.get("email", ""), data.get("phone", ""),
         data["message"], db.utcnow()))

    admin_email = notify.smtp_config()["notify_admin"]
    if admin_email:
        notify.send(admin_email, "New contact message",
                    f"From: {data['name']}\nEmail: {data.get('email', '')}\n"
                    f"Phone: {data.get('phone', '')}\n\n{data['message']}")

    return jsonify({"ok": True,
                    "message": "Thank you. Your message has been received and the academy will reply soon."}), 201
