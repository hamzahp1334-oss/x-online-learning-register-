"""Admin dashboard: login/setup pages, SPA shell, and the admin REST API.

Every admin API endpoint requires an authenticated session (enforced on the
server). Mutating endpoints additionally verify same-origin requests.
"""
import csv
import io
import json
import re
import secrets

from flask import (Blueprint, Response, jsonify, redirect, render_template,
                   request, url_for)

import db
import notify
import sheets
from auth import (SESSION_COOKIE, admin_required_api, audit, create_session,
                  current_admin, destroy_session, hash_password, login,
                  login_limiter, origin_ok, verify_password)
from validators import clean_email, clean_text

bp = Blueprint("admin", __name__, url_prefix="/admin")


# =================================================================== pages

@bp.get("/")
def index():
    if current_admin() is None:
        return redirect(url_for("admin.login_page"))
    if db.admin_count() == 0:
        return redirect(url_for("admin.setup_page"))
    return render_template("admin.html", admin=current_admin())


@bp.get("/login")
def login_page():
    if db.admin_count() == 0:
        return redirect(url_for("admin.setup_page"))
    if current_admin() is not None:
        return redirect(url_for("admin.index"))
    return render_template("admin_login.html", error=None)


@bp.post("/login")
def login_submit():
    if db.admin_count() == 0:
        return redirect(url_for("admin.setup_page"))
    ip = request.remote_addr or "unknown"
    if not login_limiter.allow(f"login:{ip}"):
        return render_template("admin_login.html",
                               error="Too many attempts. Please wait a few minutes and try again."), 429
    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    admin = login(email, password)
    if admin is None:
        audit(None, "login_failed", "admin", email)
        return render_template("admin_login.html",
                               error="Incorrect email or password."), 401
    token = create_session(admin["id"])
    audit({"id": admin["id"], "email": admin["email"]}, "login_success")
    resp = redirect(url_for("admin.index"))
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="Lax",
                    max_age=8 * 3600, path="/")
    return resp


@bp.get("/setup")
def setup_page():
    if db.admin_count() > 0:
        return redirect(url_for("admin.login_page"))
    return render_template("admin_setup.html", error=None)


@bp.post("/setup")
def setup_submit():
    if db.admin_count() > 0:
        return redirect(url_for("admin.login_page"))
    name = (request.form.get("name") or "").strip()[:120]
    email = (request.form.get("email") or "").strip().lower()[:120]
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm") or ""
    if not name or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return render_template("admin_setup.html", error="Please enter a valid name and email address.")
    if len(password) < 10:
        return render_template("admin_setup.html",
                               error="Password must be at least 10 characters long.")
    if password != confirm:
        return render_template("admin_setup.html", error="Passwords do not match.")
    now = db.utcnow()
    admin_id = db.execute(
        "INSERT INTO admin_users(name, email, password_hash, role, status, "
        "created_at, updated_at) VALUES(?,?,?,'admin','active',?,?)",
        (name, email, hash_password(password), now, now))
    audit({"id": admin_id, "email": email}, "admin_created", "admin", admin_id)
    token = create_session(admin_id)
    resp = redirect(url_for("admin.index"))
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="Lax",
                    max_age=8 * 3600, path="/")
    return resp


@bp.post("/logout")
def logout():
    admin = current_admin()
    if admin:
        audit(admin, "logout")
    destroy_session()
    resp = redirect(url_for("admin.login_page"))
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


# =================================================================== API

def _bad(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


def _check_origin():
    if not origin_ok():
        return _bad("Cross-origin request rejected.", 403)
    return None


@bp.get("/api/me")
@admin_required_api
def api_me(admin):
    return jsonify({"admin": admin})


# ------------------------------------------------------------------ stats

@bp.get("/api/stats")
@admin_required_api
def api_stats(admin):
    def count(sql, params=()):
        return db.query_one(sql, params)["c"]

    stats = {
        "total": count("SELECT COUNT(*) c FROM registrations WHERE archived_at IS NULL"),
        "new": count("SELECT COUNT(*) c FROM registrations WHERE status='new' AND archived_at IS NULL"),
        "awaiting_contact": count("SELECT COUNT(*) c FROM registrations WHERE status='contacted' AND archived_at IS NULL"),
        "confirmed": count("SELECT COUNT(*) c FROM registrations WHERE status='confirmed' AND archived_at IS NULL"),
        "active": count("SELECT COUNT(*) c FROM registrations WHERE status='active' AND archived_at IS NULL"),
        "rejected_cancelled": count("SELECT COUNT(*) c FROM registrations WHERE status IN ('rejected','cancelled') AND archived_at IS NULL"),
        "archived": count("SELECT COUNT(*) c FROM registrations WHERE archived_at IS NOT NULL"),
        "programs": count("SELECT COUNT(*) c FROM programs WHERE active=1 AND public_visible=1"),
        "unread_messages": count("SELECT COUNT(*) c FROM contact_messages WHERE is_read=0"),
    }
    stats["sheets"] = sheets.status()
    stats["notifications"] = notify.status()

    rows = db.query(
        "SELECT substr(created_at,1,10) d, COUNT(*) c FROM registrations "
        "WHERE created_at >= datetime('now', '-13 days') "
        "GROUP BY substr(created_at,1,10)")
    by_day = {r["d"]: r["c"] for r in rows}
    trend = []
    from datetime import date, timedelta
    for i in range(13, -1, -1):
        day = (date.today() - timedelta(days=i)).isoformat()
        trend.append({"day": day, "count": by_day.get(day, 0)})
    stats["trend"] = trend

    recent = db.query(
        "SELECT r.reg_id, r.created_at, r.status, r.program_name_snapshot, "
        "s.full_name, s.country FROM registrations r "
        "JOIN students s ON s.id=r.student_id "
        "WHERE r.archived_at IS NULL ORDER BY r.created_at DESC LIMIT 8")
    stats["recent"] = recent
    stats["admin"] = admin
    return jsonify(stats)


# ------------------------------------------------------------------ registrations

REG_LIST_SQL = (
    "FROM registrations r JOIN students s ON s.id = r.student_id "
    "JOIN programs p ON p.id = r.program_id ")


def _reg_filters(args) -> tuple[str, list]:
    where = ["r.archived_at IS NULL"]
    params: list = []
    q = (args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        where.append("(s.full_name LIKE ? OR s.phone LIKE ? OR r.reg_id LIKE ? "
                     "OR s.email LIKE ?)")
        params += [like, like, like, like]
    status = args.get("status") or ""
    if status:
        where.append("r.status = ?")
        params.append(status)
    program_id = args.get("program_id") or ""
    if program_id:
        where.append("r.program_id = ?")
        params.append(program_id)
    country = (args.get("country") or "").strip()
    if country:
        where.append("s.country LIKE ?")
        params.append(f"%{country}%")
    date_from = (args.get("date_from") or "").strip()
    if date_from:
        where.append("r.created_at >= ?")
        params.append(f"{date_from}T00:00:00Z")
    date_to = (args.get("date_to") or "").strip()
    if date_to:
        where.append("r.created_at <= ?")
        params.append(f"{date_to}T23:59:59Z")
    if args.get("archived") == "1":
        where[0] = "r.archived_at IS NOT NULL"
    return " WHERE " + " AND ".join(where), params


REG_SORTS = {
    "newest": "r.created_at DESC",
    "oldest": "r.created_at ASC",
    "name": "s.full_name ASC",
}


@bp.get("/api/registrations")
@admin_required_api
def api_registrations(admin):
    where, params = _reg_filters(request.args)
    sort = REG_SORTS.get(request.args.get("sort") or "newest", REG_SORTS["newest"])
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        limit, offset = 50, 0
    total = db.query_one(f"SELECT COUNT(*) c {REG_LIST_SQL}{where}", params)["c"]
    rows = db.query(
        f"SELECT r.reg_id, r.created_at, r.updated_at, r.status, "
        f"r.program_name_snapshot AS program_name, r.monthly_price_snapshot AS price, "
        f"r.currency_snapshot AS currency, r.preferred_schedule, r.sheets_sync_status, "
        f"s.full_name, s.age, s.country, s.phone {REG_LIST_SQL}{where} "
        f"ORDER BY {sort} LIMIT ? OFFSET ?", params + [limit, offset])
    return jsonify({"total": total, "registrations": rows})


@bp.get("/api/registrations/<reg_id>")
@admin_required_api
def api_registration_detail(admin, reg_id):
    reg = db.query_one(
        "SELECT r.*, s.full_name, s.age, s.country, s.city, s.phone, s.whatsapp, "
        "s.email, s.gender, s.parent_name, s.parent_phone "
        "FROM registrations r JOIN students s ON s.id=r.student_id WHERE r.reg_id=?",
        (reg_id,))
    if reg is None:
        return _bad("Registration not found.", 404)
    history = db.query(
        "SELECT action, details, created_at, admin_email FROM audit_log "
        "WHERE entity_type='registration' AND entity_id=? ORDER BY id DESC LIMIT 20",
        (reg_id,))
    return jsonify({"registration": reg, "history": history})


@bp.patch("/api/registrations/<reg_id>")
@admin_required_api
def api_registration_update(admin, reg_id):
    if (r := _check_origin()):
        return r
    reg = db.query_one(
        "SELECT r.*, s.full_name FROM registrations r "
        "JOIN students s ON s.id=r.student_id WHERE r.reg_id=?", (reg_id,))
    if reg is None:
        return _bad("Registration not found.", 404)
    payload = request.get_json(silent=True) or {}

    from validators import (clean_age, clean_email, clean_phone, clean_text,
                            _in_enum)
    errors = {}

    def take_text(key, max_len, **kw):
        err, val = clean_text(payload.get(key), max_len, **kw)
        if err:
            errors[key] = err
        return val

    student_fields = {
        "full_name": take_text("full_name", 120, required=True),
        "age": None,
        "country": take_text("country", 60),
        "city": take_text("city", 60),
        "whatsapp": None,
        "email": None,
        "parent_name": take_text("parent_name", 120),
        "parent_phone": None,
    }
    err, val = clean_age(payload.get("age") if "age" in payload else reg["age"])
    if err:
        errors["age"] = err
    student_fields["age"] = val if not err else reg["age"]

    err, val = clean_phone(payload.get("whatsapp") if "whatsapp" in payload else reg["whatsapp"],
                           "whatsapp", "WhatsApp number", False)
    if err:
        errors["whatsapp"] = err
    else:
        student_fields["whatsapp"] = val

    err, val = clean_email(payload.get("email") if "email" in payload else reg["email"], False)
    if err:
        errors["email"] = err
    else:
        student_fields["email"] = val

    phone_val = reg["phone"]
    if "phone" in payload:
        err, val = clean_phone(payload.get("phone"), "phone", "Phone number", True)
        if err:
            errors["phone"] = err
        else:
            phone_val = val
    student_fields["phone"] = phone_val

    guardian_phone = student_fields["parent_phone"]
    err, val = clean_phone(payload.get("parent_phone") if "parent_phone" in payload else reg["parent_phone"],
                           "parent_phone", "Parent or guardian contact number", False)
    if err:
        errors["parent_phone"] = err
    else:
        guardian_phone = val
        student_fields["parent_phone"] = val

    age = student_fields["age"]
    if age is not None and age < 18 and not (student_fields["parent_name"] and guardian_phone):
        errors["parent_name"] = "Students under 18 require a parent/guardian name and contact number."

    schedule = reg["preferred_schedule"]
    if "preferred_schedule" in payload:
        err, val = _in_enum(payload.get("preferred_schedule"), db.SCHEDULES,
                            "Preferred schedule")
        if err or not val:
            errors["preferred_schedule"] = "Invalid preferred schedule."
        else:
            schedule = val

    level = reg["reading_level"]
    if "reading_level" in payload:
        err, val = _in_enum(payload.get("reading_level"), db.READING_LEVELS,
                            "Reading level")
        if err or not val:
            errors["reading_level"] = "Invalid reading level."
        else:
            level = val

    notes = reg["admin_notes"]
    if "admin_notes" in payload:
        err, val = clean_text(payload.get("admin_notes"), 2000)
        if err:
            errors["admin_notes"] = err
        else:
            notes = val

    if errors:
        return jsonify({"error": "Please correct the highlighted fields.",
                        "field_errors": errors}), 400

    now = db.utcnow()
    db.execute(
        "UPDATE students SET full_name=?, age=?, country=?, city=?, phone=?, "
        "whatsapp=?, email=?, parent_name=?, parent_phone=?, updated_at=? WHERE id=?",
        (student_fields["full_name"], age, student_fields["country"],
         student_fields["city"], student_fields["phone"], student_fields["whatsapp"],
         student_fields["email"], student_fields["parent_name"], guardian_phone,
         now, reg["student_id"]))
    db.execute(
        "UPDATE registrations SET preferred_schedule=?, reading_level=?, "
        "admin_notes=?, updated_at=? WHERE reg_id=?",
        (schedule, level, notes, now, reg_id))
    sheets.enqueue_registration(reg_id)
    audit(admin, "registration_updated", "registration", reg_id,
          {"fields": sorted(payload.keys())})
    return jsonify({"ok": True})


@bp.post("/api/registrations/<reg_id>/status")
@admin_required_api
def api_registration_status(admin, reg_id):
    if (r := _check_origin()):
        return r
    payload = request.get_json(silent=True) or {}
    status = payload.get("status") or ""
    if status not in db.REG_STATUSES:
        return _bad("Invalid status.")
    reg = db.query_one("SELECT status FROM registrations WHERE reg_id=?", (reg_id,))
    if reg is None:
        return _bad("Registration not found.", 404)
    db.execute("UPDATE registrations SET status=?, updated_at=? WHERE reg_id=?",
               (status, db.utcnow(), reg_id))
    sheets.enqueue_registration(reg_id)
    audit(admin, "registration_status", "registration", reg_id,
          {"from": reg["status"], "to": status})
    return jsonify({"ok": True})


@bp.post("/api/registrations/<reg_id>/archive")
@admin_required_api
def api_registration_archive(admin, reg_id):
    if (r := _check_origin()):
        return r
    db.execute("UPDATE registrations SET archived_at=?, updated_at=? WHERE reg_id=?",
               (db.utcnow(), db.utcnow(), reg_id))
    audit(admin, "registration_archived", "registration", reg_id)
    return jsonify({"ok": True})


@bp.post("/api/registrations/<reg_id>/unarchive")
@admin_required_api
def api_registration_unarchive(admin, reg_id):
    if (r := _check_origin()):
        return r
    db.execute("UPDATE registrations SET archived_at=NULL, updated_at=? WHERE reg_id=?",
               (db.utcnow(), reg_id))
    audit(admin, "registration_unarchived", "registration", reg_id)
    return jsonify({"ok": True})


@bp.delete("/api/registrations/<reg_id>")
@admin_required_api
def api_registration_delete(admin, reg_id):
    if (r := _check_origin()):
        return r
    payload = request.get_json(silent=True) or {}
    if payload.get("confirm") != reg_id:
        return _bad('Type the registration ID to confirm permanent deletion. '
                    'Archiving is recommended instead.')
    reg = db.query_one("SELECT student_id FROM registrations WHERE reg_id=?", (reg_id,))
    if reg is None:
        return _bad("Registration not found.", 404)
    db.execute("DELETE FROM sync_queue WHERE reg_id=?", (reg_id,))
    db.execute("DELETE FROM registrations WHERE reg_id=?", (reg_id,))
    db.execute("DELETE FROM students WHERE id=?", (reg["student_id"],))
    audit(admin, "registration_deleted", "registration", reg_id)
    return jsonify({"ok": True})


@bp.get("/api/export.csv")
@admin_required_api
def api_export_csv(admin):
    args = request.args
    if args.get("ids"):
        ids = [i.strip() for i in args.get("ids", "").split(",") if i.strip()]
        placeholders = ",".join("?" * len(ids))
        where = f" WHERE r.reg_id IN ({placeholders})"
        params = ids
    else:
        where, params = _reg_filters(args)
    rows = db.query(
        f"SELECT r.reg_id, r.created_at, r.updated_at, r.status, "
        f"r.program_name_snapshot, r.monthly_price_snapshot, r.currency_snapshot, "
        f"r.reading_level, r.preferred_schedule, r.class_format, "
        f"r.previous_experience, r.learning_goals, r.referral_source, "
        f"r.admin_notes, r.sheets_sync_status, s.full_name, s.age, s.country, "
        f"s.city, s.phone, s.whatsapp, s.email, s.parent_name, s.parent_phone "
        f"{REG_LIST_SQL}{where} ORDER BY r.created_at DESC", params)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Registration ID", "Submission Date", "Student Full Name", "Age",
                     "Country", "City", "Phone Number", "WhatsApp Number", "Email",
                     "Program Name", "Monthly Price", "Currency",
                     "Quran Reading Level", "Preferred Schedule", "Class Format",
                     "Parent or Guardian Name", "Parent or Guardian Phone",
                     "Previous Experience", "Learning Goals", "Referral Source",
                     "Registration Status", "Admin Notes", "Sheets Sync",
                     "Last Updated"])
    for r in rows:
        writer.writerow([
            r["reg_id"], r["created_at"], r["full_name"], r["age"], r["country"],
            r["city"], r["phone"], r["whatsapp"], r["email"],
            r["program_name_snapshot"], r["monthly_price_snapshot"],
            r["currency_snapshot"], r["reading_level"], r["preferred_schedule"],
            r["class_format"], r["parent_name"], r["parent_phone"],
            r["previous_experience"], r["learning_goals"], r["referral_source"],
            r["status"], r["admin_notes"], r["sheets_sync_status"], r["updated_at"]])
    audit(admin, "export_csv", "registration", "",
          {"count": len(rows), "filtered": not args.get("ids")})
    out = "\ufeff" + buf.getvalue()
    return Response(out, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             f'attachment; filename="registrations-{db.utcnow()[:10]}.csv"'})


# ------------------------------------------------------------------ programs

def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or secrets.token_hex(4)


def _program_payload_errors(payload: dict, program_id=None) -> tuple[dict, dict]:
    errors: dict = {}
    out: dict = {}

    err, val = clean_text(payload.get("name"), 120, required=True)
    if err:
        errors["name"] = err
    else:
        out["name"] = val

    for key, maxlen in (("description", 1000), ("level_info", 200),
                        ("age_group", 120), ("class_format", 120),
                        ("included_services", 1000)):
        err, val = clean_text(payload.get(key), maxlen)
        if err:
            errors[key] = err
        else:
            out[key] = val

    price_raw = (payload.get("monthly_price") or "").strip() \
        if isinstance(payload.get("monthly_price"), str) else payload.get("monthly_price")
    price = None
    if price_raw not in (None, ""):
        try:
            price = round(float(price_raw), 2)
            if price < 0 or price > 10_000_000:
                raise ValueError
        except (TypeError, ValueError):
            errors["monthly_price"] = "Monthly price must be a positive number (or empty for 'contact us')."
    out["monthly_price"] = price

    currency = (payload.get("currency") or "ETB").strip().upper()
    if not re.match(r"^[A-Z]{3}$", currency):
        errors["currency"] = "Currency must be a 3-letter code (e.g. ETB, USD)."
    else:
        out["currency"] = currency

    def opt_int(key, lo, hi, label):
        raw = payload.get(key)
        if raw in (None, ""):
            out[key] = None
            return
        try:
            v = int(raw)
            if not lo <= v <= hi:
                raise ValueError
            out[key] = v
        except (TypeError, ValueError):
            errors[key] = f"{label} must be between {lo} and {hi}."

    opt_int("lessons_per_week", 1, 7, "Lessons per week")
    opt_int("lesson_duration_min", 15, 240, "Lesson duration (minutes)")

    out["active"] = 1 if payload.get("active") in (True, 1, "1", "on") else 0
    out["public_visible"] = 1 if payload.get("public_visible") in (True, 1, "1", "on") else 0

    if "name" in out:
        slug = payload.get("slug") and payload.get("slug").strip()
        if not slug:
            slug = _slugify(out["name"])
        clash = db.query_one(
            "SELECT id FROM programs WHERE slug=? AND id IS NOT ?",
            (slug, program_id if program_id is not None else -1))
        if clash:
            slug = f"{slug}-{secrets.token_hex(2)}"
        out["slug"] = slug

    return errors, out


@bp.get("/api/programs")
@admin_required_api
def api_programs(admin):
    rows = db.query("SELECT * FROM programs ORDER BY sort_order, id")
    counts = {r["program_id"]: r["c"] for r in db.query(
        "SELECT program_id, COUNT(*) c FROM registrations GROUP BY program_id")}
    for p in rows:
        p["registration_count"] = counts.get(p["id"], 0)
    return jsonify({"programs": rows})


@bp.post("/api/programs")
@admin_required_api
def api_program_create(admin):
    if (r := _check_origin()):
        return r
    payload = request.get_json(silent=True) or {}
    errors, p = _program_payload_errors(payload)
    if errors:
        return jsonify({"error": "Please correct the highlighted fields.",
                        "field_errors": errors}), 400
    now = db.utcnow()
    try:
        sort_order = int(payload.get("sort_order") or 99)
    except (TypeError, ValueError):
        sort_order = 99
    pid = db.execute(
        "INSERT INTO programs(slug, name, description, level_info, age_group, "
        "class_format, monthly_price, currency, lessons_per_week, "
        "lesson_duration_min, included_services, active, public_visible, is_sample, "
        "sort_order, created_at, updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?)",
        (p["slug"], p["name"], p["description"], p["level_info"], p["age_group"],
         p["class_format"], p["monthly_price"], p["currency"],
         p["lessons_per_week"], p["lesson_duration_min"], p["included_services"],
         p["active"], p["public_visible"], sort_order, now, now))
    audit(admin, "program_created", "program", pid, {"name": p["name"]})
    return jsonify({"ok": True, "id": pid}), 201


@bp.patch("/api/programs/<int:pid>")
@admin_required_api
def api_program_update(admin, pid):
    if (r := _check_origin()):
        return r
    prog = db.query_one("SELECT * FROM programs WHERE id=?", (pid,))
    if prog is None:
        return _bad("Program not found.", 404)
    payload = request.get_json(silent=True) or {}

    if set(payload.keys()) <= {"monthly_price", "currency", "lessons_per_week",
                               "lesson_duration_min", "public_visible",
                               "included_services"}:
        merged = {**prog, **{k: v for k, v in payload.items()}}
    else:
        merged = {**prog, **payload}

    errors, p = _program_payload_errors(merged, program_id=pid)
    if errors:
        return jsonify({"error": "Please correct the highlighted fields.",
                        "field_errors": errors}), 400
    db.execute(
        "UPDATE programs SET slug=?, name=?, description=?, level_info=?, "
        "age_group=?, class_format=?, monthly_price=?, currency=?, "
        "lessons_per_week=?, lesson_duration_min=?, included_services=?, "
        "active=?, public_visible=?, updated_at=? WHERE id=?",
        (p["slug"], p["name"], p["description"], p["level_info"], p["age_group"],
         p["class_format"], p["monthly_price"], p["currency"],
         p["lessons_per_week"], p["lesson_duration_min"], p["included_services"],
         p["active"], p["public_visible"], db.utcnow(), pid))
    audit(admin, "program_updated", "program", pid,
          {"fields": sorted(payload.keys())})
    return jsonify({"ok": True})


@bp.delete("/api/programs/<int:pid>")
@admin_required_api
def api_program_delete(admin, pid):
    if (r := _check_origin()):
        return r
    payload = request.get_json(silent=True) or {}
    if payload.get("confirm") != "yes":
        return _bad('Send {"confirm":"yes"} to delete. Deleting is permanent; '
                    'deactivating is recommended instead.')
    used = db.query_one("SELECT COUNT(*) c FROM registrations WHERE program_id=?", (pid,))
    if used and used["c"] > 0:
        return _bad("This program has registrations. Deactivate it instead of deleting.")
    prog = db.query_one("SELECT name FROM programs WHERE id=?", (pid,))
    if prog is None:
        return _bad("Program not found.", 404)
    db.execute("DELETE FROM programs WHERE id=?", (pid,))
    audit(admin, "program_deleted", "program", pid, {"name": prog["name"]})
    return jsonify({"ok": True})


# ------------------------------------------------------------------ pricing page

@bp.get("/api/pricing")
@admin_required_api
def api_pricing(admin):
    rows = db.query("SELECT id, name, monthly_price, currency, lessons_per_week, "
                    "lesson_duration_min, included_services, public_visible "
                    "FROM programs ORDER BY sort_order, id")
    return jsonify({"programs": rows,
                    "discount_note": db.get_setting("discount_note")})


@bp.put("/api/pricing/settings")
@admin_required_api
def api_pricing_settings(admin):
    if (r := _check_origin()):
        return r
    payload = request.get_json(silent=True) or {}
    err, val = clean_text(payload.get("discount_note"), 500)
    if err:
        return _bad(err)
    db.set_setting("discount_note", val)
    audit(admin, "pricing_note_updated", "settings", "discount_note")
    return jsonify({"ok": True})


# ------------------------------------------------------------------ FAQs

@bp.get("/api/faqs")
@admin_required_api
def api_faqs(admin):
    rows = db.query("SELECT * FROM faqs ORDER BY sort_order, id")
    return jsonify({"faqs": rows})


@bp.post("/api/faqs")
@admin_required_api
def api_faq_create(admin):
    if (r := _check_origin()):
        return r
    payload = request.get_json(silent=True) or {}
    err_q, q = clean_text(payload.get("question"), 300, required=True)
    err_a, a = clean_text(payload.get("answer"), 3000, required=True)
    if err_q or err_a:
        return _bad(err_q or err_a)
    try:
        order = int(payload.get("sort_order") or 99)
    except (TypeError, ValueError):
        order = 99
    fid = db.execute("INSERT INTO faqs(question, answer, sort_order, visible, updated_at) "
                     "VALUES(?,?,?,?,?)", (q, a, order, 1, db.utcnow()))
    audit(admin, "faq_created", "faq", fid)
    return jsonify({"ok": True, "id": fid}), 201


@bp.patch("/api/faqs/<int:fid>")
@admin_required_api
def api_faq_update(admin, fid):
    if (r := _check_origin()):
        return r
    faq = db.query_one("SELECT * FROM faqs WHERE id=?", (fid,))
    if faq is None:
        return _bad("FAQ not found.", 404)
    payload = request.get_json(silent=True) or {}
    merged = {**faq, **payload}
    err_q, q = clean_text(merged.get("question"), 300, required=True)
    err_a, a = clean_text(merged.get("answer"), 3000, required=True)
    if err_q or err_a:
        return _bad(err_q or err_a)
    visible = 1 if merged.get("visible") in (True, 1, "1", "on") else 0
    try:
        order = int(merged.get("sort_order") or 99)
    except (TypeError, ValueError):
        order = 99
    db.execute("UPDATE faqs SET question=?, answer=?, visible=?, sort_order=?, "
               "updated_at=? WHERE id=?", (q, a, visible, order, db.utcnow(), fid))
    audit(admin, "faq_updated", "faq", fid)
    return jsonify({"ok": True})


@bp.delete("/api/faqs/<int:fid>")
@admin_required_api
def api_faq_delete(admin, fid):
    if (r := _check_origin()):
        return r
    db.execute("DELETE FROM faqs WHERE id=?", (fid,))
    audit(admin, "faq_deleted", "faq", fid)
    return jsonify({"ok": True})


# ------------------------------------------------------------------ settings / content

SETTING_WHITELIST = {
    "academy_name": ("text", 120),
    "academy_tagline": ("text", 200),
    "logo_url": ("text", 400),
    "announcement_enabled": ("bool", None),
    "announcement_text": ("text", 300),
    "hero_headline": ("text", 200),
    "hero_text": ("text", 600),
    "about_sections": ("json", None),
    "contact_email": ("email", 120),
    "contact_phone": ("text", 60),
    "whatsapp_number": ("text", 60),
    "telegram_link": ("url", 300),
    "facebook_link": ("url", 300),
    "instagram_link": ("url", 300),
    "youtube_link": ("url", 300),
    "working_hours": ("text", 300),
}


@bp.get("/api/settings")
@admin_required_api
def api_settings_get(admin):
    data = {k: db.get_setting(k) for k in SETTING_WHITELIST}
    data["notifications"] = notify.status()
    return jsonify({"settings": data})


@bp.put("/api/settings")
@admin_required_api
def api_settings_put(admin):
    if (r := _check_origin()):
        return r
    payload = request.get_json(silent=True) or {}
    errors = {}
    changes = []
    for key, value in payload.items():
        if key not in SETTING_WHITELIST:
            continue
        kind, maxlen = SETTING_WHITELIST[key]
        if kind == "bool":
            value = bool(value)
        elif kind == "json":
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                errors[key] = "Invalid data."
                continue
        else:
            err, value = clean_text(value, maxlen or 300)
            if err:
                errors[key] = err
                continue
            if kind == "email" and value:
                err, value = clean_email(value, False)
                if err:
                    errors[key] = err
                    continue
            if kind == "url" and value and not re.match(
                    r"^https?://[^\s]+$", value):
                errors[key] = "Link must start with http:// or https://"
                continue
        db.set_setting(key, value)
        changes.append(key)
    if errors:
        return jsonify({"error": "Please correct the highlighted fields.",
                        "field_errors": errors}), 400
    if changes:
        audit(admin, "settings_updated", "settings", "",
              {"keys": changes})
    return jsonify({"ok": True})


LOGO_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


@bp.post("/api/settings/logo")
@admin_required_api
def api_settings_logo(admin):
    if (r := _check_origin()):
        return r
    file = request.files.get("logo")
    if file is None:
        return _bad("No file uploaded.")
    if file.content_type not in LOGO_TYPES:
        return _bad("Logo must be a PNG, JPG or WebP image.")
    data = file.read()
    if len(data) > 2 * 1024 * 1024:
        return _bad("Logo file must be 2 MB or smaller.")
    ext = LOGO_TYPES[file.content_type]
    filename = f"logo-{secrets.token_hex(4)}{ext}"
    import os
    uploads = os.path.join(db.BASE_DIR, "static", "uploads")
    os.makedirs(uploads, exist_ok=True)
    for old in os.listdir(uploads):
        if old.startswith("logo-"):
            try:
                os.remove(os.path.join(uploads, old))
            except OSError:
                pass
    with open(os.path.join(uploads, filename), "wb") as fh:
        fh.write(data)
    url = f"/static/uploads/{filename}?v={secrets.token_hex(3)}"
    db.set_setting("logo_url", url)
    audit(admin, "logo_updated", "settings", "logo_url")
    return jsonify({"ok": True, "logo_url": url})


# ------------------------------------------------------------------ messages

@bp.get("/api/messages")
@admin_required_api
def api_messages(admin):
    rows = db.query("SELECT * FROM contact_messages ORDER BY created_at DESC LIMIT 200")
    return jsonify({"messages": rows})


@bp.post("/api/messages/<int:mid>/read")
@admin_required_api
def api_message_read(admin, mid):
    if (r := _check_origin()):
        return r
    db.execute("UPDATE contact_messages SET is_read=1 WHERE id=?", (mid,))
    audit(admin, "message_read", "message", mid)
    return jsonify({"ok": True})


@bp.delete("/api/messages/<int:mid>")
@admin_required_api
def api_message_delete(admin, mid):
    if (r := _check_origin()):
        return r
    db.execute("DELETE FROM contact_messages WHERE id=?", (mid,))
    audit(admin, "message_deleted", "message", mid)
    return jsonify({"ok": True})


# ------------------------------------------------------------------ sheets

@bp.get("/api/sheets/status")
@admin_required_api
def api_sheets_status(admin):
    return jsonify(sheets.status())


@bp.post("/api/sheets/sync")
@admin_required_api
def api_sheets_sync(admin):
    if (r := _check_origin()):
        return r
    if not sheets.is_configured():
        return _bad("Google Sheets is not configured. Set the environment "
                    "variables GOOGLE_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_EMAIL and "
                    "GOOGLE_PRIVATE_KEY (see README).")
    stats = sheets.process_pending(force=True, limit=300)
    audit(admin, "sheets_sync_now", "sheets", "", stats)
    return jsonify({"ok": True, "stats": stats, "status": sheets.status()})


@bp.post("/api/sheets/retry-failed")
@admin_required_api
def api_sheets_retry(admin):
    if (r := _check_origin()):
        return r
    reset = sheets.retry_failed()
    stats = sheets.process_pending(force=True, limit=300)
    audit(admin, "sheets_retry_failed", "sheets", "", {"reset": reset, **stats})
    return jsonify({"ok": True, "reset": reset, "stats": stats,
                    "status": sheets.status()})


# ------------------------------------------------------------------ audit + account

@bp.get("/api/audit")
@admin_required_api
def api_audit(admin):
    rows = db.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT 200")
    return jsonify({"entries": rows})


@bp.post("/api/change-password")
@admin_required_api
def api_change_password(admin):
    if (r := _check_origin()):
        return r
    payload = request.get_json(silent=True) or {}
    current = payload.get("current_password") or ""
    new = payload.get("new_password") or ""
    row = db.query_one("SELECT password_hash FROM admin_users WHERE id=?",
                       (admin["id"],))
    if not verify_password(current, row["password_hash"]):
        return _bad("Current password is incorrect.", 403)
    if len(new) < 10:
        return _bad("New password must be at least 10 characters long.")
    db.execute("UPDATE admin_users SET password_hash=?, updated_at=? WHERE id=?",
               (hash_password(new), db.utcnow(), admin["id"]))
    db.execute("DELETE FROM admin_sessions WHERE admin_id=?", (admin["id"],))
    audit(admin, "password_changed", "admin", admin["id"])
    return jsonify({"ok": True})
