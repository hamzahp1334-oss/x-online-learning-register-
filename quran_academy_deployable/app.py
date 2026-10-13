"""Online Quran Academy — application entry point.

Run:  python app.py   (serves on http://0.0.0.0:3000 by default)
"""
import os
import secrets
import threading

# --- tiny .env loader (no external dependency) -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_dotenv() -> None:
    path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


load_dotenv()

import db  # noqa: E402
from flask import Flask, jsonify, render_template, request  # noqa: E402

# ---------------------------------------------------------------------------
# First administrator from environment (optional; /admin/setup also works).
_env_admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
_env_admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()


def create_app() -> Flask:
    app = Flask(__name__)

    # Persistent random secret (used for any signed-cookie needs).
    secret_path = os.path.join(db.DATA_DIR, "secret_key")
    if not os.path.exists(secret_path):
        with open(secret_path, "w", encoding="ascii") as fh:
            fh.write(secrets.token_hex(32))
    with open(secret_path, encoding="ascii") as fh:
        app.secret_key = fh.read().strip()
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
    app.config["JSON_SORT_KEYS"] = False

    # --- Jinja helpers -----------------------------------------------------
    @app.template_filter("price")
    def price_filter(value, currency=""):
        if value is None:
            return "Contact us for pricing"
        text = f"{value:,.2f}".rstrip("0").rstrip(".")
        return f"{text} {currency}".strip() + " / month"

    @app.template_filter("dt")
    def dt_filter(iso: str) -> str:
        if not iso:
            return "—"
        return iso.replace("T", " ").replace("Z", " UTC")

    @app.context_processor
    def inject_globals():
        from datetime import date
        return {
            "site": db.public_settings(),
            "current_path": request.path,
            "now_year": date.today().year,
        }

    # --- security headers ---------------------------------------------------
    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
            "script-src 'self'; font-src 'self' fonts.gstatic.com; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        if request.path.startswith("/admin"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    # --- blueprints ----------------------------------------------------------
    from routes_admin import bp as admin_bp
    from routes_public import bp as public_bp
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    # --- misc routes ---------------------------------------------------------
    @app.get("/robots.txt")
    def robots():
        return ("User-agent: *\nAllow: /\nDisallow: /admin\n"
                "Disallow: /api/\nDisallow: /register/success/\n"), 200, \
               {"Content-Type": "text/plain; charset=utf-8"}

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    # --- error handlers ------------------------------------------------------
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api") or request.path.startswith("/admin/api"):
            return jsonify({"error": "Not found"}), 404
        return render_template("error.html", code=404,
                               message="The page you are looking for does not exist or has moved."), 404

    @app.errorhandler(500)
    def server_error(e):
        if request.path.startswith("/api") or request.path.startswith("/admin/api"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("error.html", code=500,
                               message="Something went wrong on our side. Please try again."), 500

    return app


def seed_admin_from_env() -> None:
    if not (_env_admin_email and _env_admin_password):
        return
    if db.admin_count() > 0:
        return
    import re
    from auth import hash_password
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", _env_admin_email):
        print(f"[startup] ADMIN_EMAIL '{_env_admin_email}' looks invalid — skipped admin seeding.")
        return
    now = db.utcnow()
    db.execute(
        "INSERT INTO admin_users(name, email, password_hash, role, status, "
        "created_at, updated_at) VALUES(?,?,?,'admin','active',?,?)",
        (os.environ.get("ADMIN_NAME", "Administrator").strip()[:120] or "Administrator",
         _env_admin_email.lower(), hash_password(_env_admin_password), now, now))
    print(f"[startup] Created administrator account: {_env_admin_email}")


def main() -> None:
    db.init_db()
    seed_admin_from_env()

    import sheets
    stop_event = threading.Event()
    worker = threading.Thread(target=sheets.worker_loop, args=(stop_event,),
                              daemon=True, name="sheets-worker")
    worker.start()

    app = create_app()
    port = int(os.environ.get("PORT", "3000"))
    host = os.environ.get("HOST", "0.0.0.0")

    if db.admin_count() == 0:
        print("[startup] No administrator exists yet.")
        print("[startup] Open the site and complete the first-run setup at /admin/setup")

    try:
        from waitress import serve
        print(f" * Online Quran Academy running on http://{host}:{port}"
              f"  (admin: http://localhost:{port}/admin)")
        serve(app, host=host, port=port, threads=8)
    except ImportError:
        app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
