"""Google Sheets synchronization engine.

Real integration with the Google Sheets REST API using a service account
(RS256-signed JWT exchanged for an OAuth access token). The application
database is the source of truth; every successful save/update enqueues a
durable sync job. Jobs are idempotent: a registration row is matched by its
unique Registration ID, so retries never duplicate rows.

If credentials are not configured, registrations are still saved normally and
the queue simply waits — nothing is lost, and the admin dashboard shows the
exact setup steps that remain.
"""
import base64
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import db

TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPE = "https://www.googleapis.com/auth/spreadsheets"
REQUEST_TIMEOUT = 20

WORKSHEET = os.environ.get("GOOGLE_SHEET_WORKSHEET", "Registrations")

SHEET_COLUMNS = [
    "Registration ID", "Submission Date", "Student Full Name", "Age", "Country",
    "City", "Phone Number", "WhatsApp Number", "Email", "Program Name",
    "Quran Reading Level", "Preferred Schedule", "Class Format",
    "Parent or Guardian Name", "Parent or Guardian Phone", "Previous Experience",
    "Learning Goals", "Monthly Price", "Currency", "Registration Status",
    "Admin Notes", "Last Updated",
]

# Retry backoff: attempt N waits BACKOFFS[N-1] seconds (capped at the last value).
BACKOFFS = [30, 120, 600, 3600, 21600, 86400]
MAX_AUTO_ATTEMPTS = len(BACKOFFS)

_token_cache = {"token": None, "expires_at": 0.0}
_token_lock = threading.Lock()


# ------------------------------------------------------------------ config

class ConfigError(Exception):
    pass


def config() -> dict:
    return {
        "sheet_id": os.environ.get("GOOGLE_SHEET_ID", "").strip(),
        "email": os.environ.get("GOOGLE_SERVICE_ACCOUNT_EMAIL", "").strip(),
        "private_key": os.environ.get("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n").strip(),
        "worksheet": WORKSHEET,
    }


def missing_vars() -> list[str]:
    cfg = config()
    missing = []
    if not cfg["sheet_id"]:
        missing.append("GOOGLE_SHEET_ID")
    if not cfg["email"]:
        missing.append("GOOGLE_SERVICE_ACCOUNT_EMAIL")
    if not cfg["private_key"]:
        missing.append("GOOGLE_PRIVATE_KEY")
    return missing


def is_configured() -> bool:
    return not missing_vars()


# ------------------------------------------------------------------ google auth

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def get_access_token() -> str:
    """Exchange a self-signed service-account JWT for an access token."""
    cfg = config()
    missing = missing_vars()
    if missing:
        raise ConfigError(f"Google Sheets not configured: missing {', '.join(missing)}")

    now = int(time.time())
    with _token_lock:
        if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
            return _token_cache["token"]

        header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        claims = _b64(json.dumps({
            "iss": cfg["email"],
            "scope": SCOPE,
            "aud": TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        }).encode())
        signing_input = f"{header}.{claims}".encode("ascii")

        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        key = serialization.load_pem_private_key(cfg["private_key"].encode(), password=None)
        signature = _b64(key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256()))
        jwt = f"{header}.{claims}.{signature}"

        body = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt,
        }).encode()
        req = urllib.request.Request(TOKEN_URL, data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode())

        token = payload.get("access_token")
        if not token:
            raise RuntimeError("Google token endpoint returned no access_token")
        _token_cache["token"] = token
        _token_cache["expires_at"] = now + int(payload.get("expires_in", 3600))
        return token


def _api(method: str, url: str, body: dict | None = None) -> dict:
    """Call a Google Sheets REST endpoint. Raises on HTTP/API errors."""
    token = get_access_token()
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            text = resp.read().decode()
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode()[:400]
        except Exception:
            pass
        raise RuntimeError(f"Google API HTTP {e.code}: {detail}") from e


def _range(rg: str) -> str:
    return urllib.parse.quote(f"'{WORKSHEET}'!{rg}")


# ------------------------------------------------------------------ worksheet setup

def ensure_worksheet() -> None:
    """Create the worksheet and header row if they do not exist yet."""
    cfg = config()
    meta = _api("GET", f"{SHEETS_API}/{cfg['sheet_id']}?fields=sheets.properties")
    titles = [s.get("properties", {}).get("title") for s in meta.get("sheets", [])]
    if WORKSHEET not in titles:
        _api("POST", f"{SHEETS_API}/{cfg['sheet_id']}:batchUpdate", {
            "requests": [{"addSheet": {"properties": {"title": WORKSHEET}}}],
        })
    result = _api("GET",
                  f"{SHEETS_API}/{cfg['sheet_id']}/values/{_range('A1')}?"
                  "majorDimension=ROWS")
    if not result.get("values"):
        _api("PUT",
             f"{SHEETS_API}/{cfg['sheet_id']}/values/{_range('A1')}?"
             "valueInputOption=RAW",
             {"values": [SHEET_COLUMNS]})


# ------------------------------------------------------------------ row upsert

def _registration_row(reg_id: str) -> list | None:
    reg = db.query_one(
        "SELECT r.*, s.full_name, s.age, s.country, s.city, s.phone, s.whatsapp, "
        "s.email, s.parent_name, s.parent_phone "
        "FROM registrations r JOIN students s ON s.id = r.student_id "
        "WHERE r.reg_id = ?", (reg_id,))
    if reg is None:
        return None

    def fmt_price(p):
        return "" if p is None else f"{p:g}"

    return [
        reg["reg_id"],
        reg["created_at"],
        reg["full_name"] or "",
        reg["age"] if reg["age"] is not None else "",
        reg["country"] or "",
        reg["city"] or "",
        reg["phone"] or "",
        reg["whatsapp"] or "",
        reg["email"] or "",
        reg["program_name_snapshot"] or "",
        reg["reading_level"] or "",
        reg["preferred_schedule"] or "",
        reg["class_format"] or "",
        reg["parent_name"] or "",
        reg["parent_phone"] or "",
        reg["previous_experience"] or "",
        reg["learning_goals"] or "",
        fmt_price(reg["monthly_price_snapshot"]),
        reg["currency_snapshot"] or "",
        reg["status"] or "",
        reg["admin_notes"] or "",
        reg["updated_at"] or "",
    ]


def upsert_registration(reg_id: str) -> None:
    """Insert or update the spreadsheet row for a registration (idempotent)."""
    cfg = config()
    ensure_worksheet()

    row = _registration_row(reg_id)
    if row is None:
        return  # registration deleted; nothing to sync

    # Locate an existing row by its unique Registration ID (column A).
    listing = _api("GET",
                   f"{SHEETS_API}/{cfg['sheet_id']}/values/"
                   f"{_range('A2:A')}?majorDimension=COLUMNS")
    existing: dict[str, int] = {}
    for col in listing.get("values", []):
        for idx, val in enumerate(col):
            if isinstance(val, str) and val.strip():
                existing[val.strip()] = idx + 2  # row number in the sheet

    if row[0] in existing:
        row_no = existing[row[0]]
        _api("PUT",
             f"{SHEETS_API}/{cfg['sheet_id']}/values/"
             f"{_range(f'A{row_no}:V{row_no}')}?valueInputOption=RAW",
             {"values": [row]})
    else:
        _api("POST",
             f"{SHEETS_API}/{cfg['sheet_id']}/values/"
             f"{_range('A:V')}?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
             {"values": [row]})


# ------------------------------------------------------------------ queue

def enqueue_registration(reg_id: str) -> None:
    """Queue an upsert for a registration (deduplicated by pending job)."""
    now = db.utcnow()
    db.execute(
        "INSERT INTO sync_queue(reg_id, operation, attempts, next_attempt_at, "
        "status, created_at, updated_at) "
        "SELECT ?, 'upsert', 0, ?, 'pending', ?, ? "
        "WHERE NOT EXISTS (SELECT 1 FROM sync_queue "
        "                  WHERE reg_id=? AND status IN ('pending','failed'))",
        (reg_id, now, now, now, reg_id),
    )


def _next_delay(attempts: int) -> timedelta:
    idx = min(attempts, len(BACKOFFS)) - 1
    return timedelta(seconds=BACKOFFS[max(idx, 0)])


def process_pending(force: bool = False, limit: int = 200) -> dict:
    """Process due queue jobs. With force=True, retry failed jobs too.
    Returns {processed, succeeded, failed, skipped}."""
    stats = {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0}

    if not is_configured():
        stats["skipped"] = db.query_one(
            "SELECT COUNT(*) AS c FROM sync_queue WHERE status='pending'")["c"]
        return stats

    now = db.utcnow()
    if force:
        rows = db.query(
            "SELECT * FROM sync_queue WHERE status IN ('pending','failed') "
            "ORDER BY id LIMIT ?", (limit,))
    else:
        rows = db.query(
            "SELECT * FROM sync_queue WHERE status='pending' AND next_attempt_at<=? "
            "ORDER BY id LIMIT ?", (now, limit))

    for job in rows:
        stats["processed"] += 1
        reg_id = job["reg_id"]
        exists = db.query_one("SELECT 1 FROM registrations WHERE reg_id=?", (reg_id,))
        if exists is None:
            db.execute("UPDATE sync_queue SET status='done', updated_at=? WHERE id=?",
                       (db.utcnow(), job["id"]))
            stats["succeeded"] += 1
            continue
        try:
            upsert_registration(reg_id)
        except Exception as e:  # network / API failure — retry with backoff
            attempts = job["attempts"] + 1
            err = str(e)[:500]
            if attempts >= MAX_AUTO_ATTEMPTS:
                status, nxt = "failed", None
            else:
                status = "pending"
                nxt = (datetime.now(timezone.utc) + _next_delay(attempts)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
            db.execute(
                "UPDATE sync_queue SET attempts=?, last_error=?, status=?, "
                "next_attempt_at=COALESCE(?, next_attempt_at), updated_at=? WHERE id=?",
                (attempts, err, status, nxt, db.utcnow(), job["id"]))
            db.execute(
                "UPDATE registrations SET sheets_sync_status='failed', "
                "sheets_sync_error=?, updated_at=? WHERE reg_id=?",
                (err, db.utcnow(), reg_id))
            stats["failed"] += 1
        else:
            db.execute("UPDATE sync_queue SET status='done', attempts=attempts+1, "
                       "last_error=NULL, updated_at=? WHERE id=?", (db.utcnow(), job["id"]))
            db.execute(
                "UPDATE registrations SET sheets_sync_status='synced', "
                "sheets_synced_at=?, sheets_sync_error=NULL, updated_at=? WHERE reg_id=?",
                (db.utcnow(), db.utcnow(), reg_id))
            stats["succeeded"] += 1
    return stats


def retry_failed() -> int:
    """Reset failed jobs for a manual retry."""
    return db.execute(
        "UPDATE sync_queue SET status='pending', attempts=0, next_attempt_at=?, "
        "updated_at=? WHERE status='failed'", (db.utcnow(), db.utcnow()))


def worker_loop(stop_event: threading.Event) -> None:
    """Background worker: drains due jobs every 20 seconds."""
    while not stop_event.wait(20):
        try:
            process_pending(force=False, limit=100)
        except Exception:
            # Never let the worker die on unexpected errors.
            continue


def status() -> dict:
    pending = db.query_one("SELECT COUNT(*) AS c FROM sync_queue WHERE status='pending'")["c"]
    failed = db.query_one("SELECT COUNT(*) AS c FROM sync_queue WHERE status='failed'")["c"]
    last = db.query_one("SELECT MAX(sheets_synced_at) AS m FROM registrations")
    last_err = db.query_one(
        "SELECT last_error FROM sync_queue WHERE last_error IS NOT NULL "
        "ORDER BY updated_at DESC LIMIT 1")
    synced_count = db.query_one(
        "SELECT COUNT(*) AS c FROM registrations WHERE sheets_sync_status='synced'")["c"]
    return {
        "configured": is_configured(),
        "missing_vars": missing_vars(),
        "worksheet": WORKSHEET,
        "pending": pending,
        "failed": failed,
        "synced_registrations": synced_count,
        "last_success_at": last["m"] if last else None,
        "last_error": last_err["last_error"] if last_err else None,
    }
