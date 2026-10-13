"""Admin authentication: server-side sessions, password hashing,
login rate limiting, audit logging and CSRF origin checks."""
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import request

import db
from werkzeug.security import check_password_hash, generate_password_hash

SESSION_COOKIE = "qa_admin_session"
SESSION_HOURS = 8

# ---------------------------------------------------------------- hashing

def hash_password(pw: str) -> str:
    return generate_password_hash(pw, method="scrypt")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return check_password_hash(hashed, pw)
    except ValueError:
        return False


# ---------------------------------------------------------------- sessions

def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def create_session(admin_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    db.execute(
        "INSERT INTO admin_sessions(token, admin_id, created_at, expires_at, ip, user_agent) "
        "VALUES(?,?,?,?,?,?)",
        (token, admin_id, db.utcnow(), expires,
         request.remote_addr or "", (request.user_agent.string or "")[:200]),
    )
    return token


def current_admin() -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    row = db.query_one(
        "SELECT s.token, s.expires_at, a.id, a.name, a.email, a.role, a.status "
        "FROM admin_sessions s JOIN admin_users a ON a.id = s.admin_id "
        "WHERE s.token = ?",
        (token,),
    )
    if row is None or row["status"] != "active":
        return None
    if _parse(row["expires_at"]) < datetime.now(timezone.utc):
        db.execute("DELETE FROM admin_sessions WHERE token=?", (token,))
        return None
    return {"id": row["id"], "name": row["name"], "email": row["email"],
            "role": row["role"]}


def destroy_session() -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute("DELETE FROM admin_sessions WHERE token=?", (token,))


def login(email: str, password: str) -> dict | None:
    """Verify credentials; returns the admin row dict or None."""
    admin = db.query_one(
        "SELECT * FROM admin_users WHERE lower(email)=lower(?) AND status='active'",
        (email.strip(),),
    )
    if admin is None or not verify_password(password, admin["password_hash"]):
        return None
    db.execute("UPDATE admin_users SET last_login_at=?, updated_at=? WHERE id=?",
               (db.utcnow(), db.utcnow(), admin["id"]))
    return admin


def purge_expired_sessions() -> None:
    db.execute("DELETE FROM admin_sessions WHERE expires_at < ?", (db.utcnow(),))


# ---------------------------------------------------------------- decorators

def admin_required_api(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        admin = current_admin()
        if admin is None:
            return {"error": "Authentication required"}, 401
        return fn(admin, *args, **kwargs)
    return wrapper


def admin_required_page(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_admin() is None:
            from flask import redirect, url_for
            return redirect(url_for("admin.login_page"))
        return fn(*args, **kwargs)
    return wrapper


def origin_ok() -> bool:
    """Lightweight CSRF defence for mutating requests: when the browser sends
    an Origin or Referer it must match the Host of this request."""
    origin = request.headers.get("Origin")
    if origin:
        try:
            from urllib.parse import urlparse
            o = urlparse(origin)
            return o.netloc == request.host
        except ValueError:
            return False
    referer = request.headers.get("Referer")
    if referer:
        try:
            from urllib.parse import urlparse
            r = urlparse(referer)
            return r.netloc == request.host
        except ValueError:
            return False
    return True


# ---------------------------------------------------------------- rate limit

class RateLimiter:
    """In-memory sliding window limiter (per key)."""
    def __init__(self, max_hits: int, window_seconds: int):
        self.max = max_hits
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < self.window]
            hits.append(now)
            self._hits[key] = hits
            if len(self._hits) > 5000:  # prune the map occasionally
                cutoff = now - self.window
                self._hits = {k: v for k, v in self._hits.items()
                              if v and v[-1] > cutoff}
            return len(hits) <= self.max


login_limiter = RateLimiter(8, 600)      # 8 attempts / 10 min per IP
register_limiter = RateLimiter(10, 600)  # 10 submissions / 10 min per IP
contact_limiter = RateLimiter(5, 600)    # 5 messages / 10 min per IP


# ---------------------------------------------------------------- audit

def audit(admin: dict | None, action: str, entity_type: str = "",
          entity_id: str = "", details=None) -> None:
    import json as _json
    db.execute(
        "INSERT INTO audit_log(admin_id, admin_email, action, entity_type, entity_id, "
        "details, created_at) VALUES(?,?,?,?,?,?,?)",
        (
            admin["id"] if admin else None,
            admin["email"] if admin else None,
            action,
            entity_type,
            str(entity_id),
            _json.dumps(details, default=str)[:2000] if details else None,
            db.utcnow(),
        ),
    )
