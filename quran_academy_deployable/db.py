"""SQLite database layer for the Online Quran Academy.

A single shared connection guarded by a lock. SQLite in WAL mode is a
persistent, ACID-compliant database — the source of truth for the whole app.
Google Sheets is only a synchronized copy (see sheets.py).
"""
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "academy.db"))

os.makedirs(DATA_DIR, exist_ok=True)

_conn: sqlite3.Connection | None = None
_lock = threading.RLock()

REG_STATUSES = ("new", "pending_verification", "contacted", "confirmed", "active", "rejected", "cancelled")
READING_LEVELS = (
    "Complete beginner",
    "Learning Arabic letters",
    "Can read slowly",
    "Can read but needs Tajweed improvement",
    "Intermediate",
    "Advanced",
    "Quran memorization (Hifz)",
)
SCHEDULES = ("Morning", "Afternoon", "Evening", "Flexible")
CLASS_FORMATS = ("One-to-one", "Small group", "Either is fine")

CATEGORIES = {
    "qaida": "Qaida (Alphabets & Foundational Reading)",
    "nezer": "Nezer (Quran Reading Practice & Fluency)",
    "tajweed": "Tajweed (Recitation Rules & Correction)",
    "hifz": "Hifz (Quran Memorization & Revision)",
    "kitab": "Kitab (Islamic Book & Text Studies)",
    "arabic": "Arabic Language Lessons",
    "islamic_studies": "Islamic Studies",
}

PAYMENT_STATUSES = (
    "not_paid",
    "awaiting_verification",
    "partially_paid",
    "paid",
    "overdue",
    "waived",
)

SCHEDULE_STATUSES = ("scheduled", "completed", "cancelled", "rescheduled")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.execute("PRAGMA busy_timeout=10000")
    return _conn


def query(sql: str, params=()) -> list[dict]:
    with _lock:
        cur = get_conn().execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def query_one(sql: str, params=()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params=()) -> int:
    """Run a write statement and commit. Returns lastrowid."""
    with _lock:
        conn = get_conn()
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid


def executemany(sql: str, seq) -> None:
    with _lock:
        conn = get_conn()
        conn.executemany(sql, seq)
        conn.commit()


def tx():
    """Context manager for a locked transaction."""
    return _Transaction(_lock, get_conn())


class _Transaction:
    def __init__(self, lock, conn):
        self._lock = lock
        self._conn = conn

    def __enter__(self):
        self._lock.acquire()
        self._conn.execute("BEGIN")
        return self._conn

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._lock.release()
        return False


# ---------------------------------------------------------------------------
# Settings (editable from the admin dashboard)
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    "academy_name": "Online Quran Academy",
    "academy_tagline": "Learn the Quran online, from anywhere",
    "logo_url": "",
    "announcement_enabled": False,
    "announcement_text": "",
    "hero_headline": "Learn the Quran Online, From Anywhere.",
    "hero_text": ("Start or strengthen your Quran learning journey with a structured "
                  "online program designed around your level and learning goals."),
    "default_currency": "ETB",
    "pricing_footer_note": ("Submitting the registration form does not complete any payment. "
                            "The academy will contact you to confirm class availability, schedule and payment."),
    "about_sections": json.dumps([
        {
            "title": "About the Academy",
            "body": ("[Placeholder] This section is editable from the admin dashboard. "
                     "Replace it with an accurate introduction to the academy, its history "
                     "and how it serves students."),
        },
        {
            "title": "Our Teaching Approach",
            "body": ("[Placeholder] Describe how classes are taught: lesson structure, teacher "
                     "interaction, materials used, and how student progress is followed. "
                     "Only publish details the academy has confirmed."),
        },
        {
            "title": "Teachers",
            "body": ("[Placeholder] Teacher profiles and qualifications will be published here "
                     "once provided by the academy."),
        },
        {
            "title": "Mission and Values",
            "body": ("[Placeholder] Describe the academy's mission and the values that guide "
                     "its teaching."),
        },
    ]),
    "contact_email": "",
    "contact_phone": "",
    "whatsapp_number": "",
    "telegram_link": "",
    "facebook_link": "",
    "instagram_link": "",
    "youtube_link": "",
    "working_hours": "",
    "discount_note": "",
    "bank_name": "Commercial Bank of Ethiopia (CBE)",
    "bank_account_number": "1000234567890",
    "telebirr_number": "0911223344",
    "account_holder": "Online Quran Academy",
    "default_fee_amount": 800.0,
    "payment_instructions": (
        "🏦 <b>Payment Accounts:</b>\n"
        "• <b>CBE Account:</b> <code>1000234567890</code>\n"
        "• <b>Telebirr:</b> <code>0911223344</code>\n"
        "• <b>Account Name:</b> Online Quran Academy\n\n"
        "Please complete the bank transfer or Telebirr payment, then upload a screenshot or photo of your payment receipt below."
    ),
}


def get_setting(key: str, default=None):
    row = query_one("SELECT value FROM settings WHERE key=?", (key,))
    if row is None:
        return DEFAULT_SETTINGS.get(key, default) if default is None else default
    try:
        return json.loads(row["value"])
    except (ValueError, TypeError):
        return row["value"]


def set_setting(key: str, value) -> None:
    execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value)),
    )


def public_settings() -> dict:
    """Settings needed by every public page template."""
    return {
        "academy_name": get_setting("academy_name"),
        "academy_tagline": get_setting("academy_tagline"),
        "logo_url": get_setting("logo_url"),
        "announcement_enabled": get_setting("announcement_enabled"),
        "announcement_text": get_setting("announcement_text"),
        "contact_email": get_setting("contact_email"),
        "contact_phone": get_setting("contact_phone"),
        "whatsapp_number": get_setting("whatsapp_number"),
        "telegram_link": get_setting("telegram_link"),
        "facebook_link": get_setting("facebook_link"),
        "instagram_link": get_setting("instagram_link"),
        "youtube_link": get_setting("youtube_link"),
        "working_hours": get_setting("working_hours"),
    }


# ---------------------------------------------------------------------------
# Registration IDs
# ---------------------------------------------------------------------------

_REG_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def gen_reg_id() -> str:
    """QA-YYMMDD-XXXXXX — date plus 6 unambiguous random characters."""
    while True:
        stamp = datetime.now(timezone.utc).strftime("%y%m%d")
        rand = "".join(secrets.choice(_REG_ALPHABET) for _ in range(6))
        reg_id = f"QA-{stamp}-{rand}"
        if query_one("SELECT 1 FROM registrations WHERE reg_id=?", (reg_id,)) is None:
            return reg_id


# ---------------------------------------------------------------------------
# Schema + seed
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_users (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  name             TEXT NOT NULL,
  email            TEXT NOT NULL UNIQUE,
  password_hash    TEXT NOT NULL,
  role             TEXT NOT NULL DEFAULT 'admin',
  status           TEXT NOT NULL DEFAULT 'active',
  telegram_user_id INTEGER,
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  last_login_at    TEXT
);

CREATE TABLE IF NOT EXISTS admin_sessions (
  token      TEXT PRIMARY KEY,
  admin_id   INTEGER NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  ip         TEXT,
  user_agent TEXT
);

CREATE TABLE IF NOT EXISTS programs (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  slug                TEXT NOT NULL UNIQUE,
  name                TEXT NOT NULL,
  category            TEXT NOT NULL DEFAULT 'qaida',
  description         TEXT NOT NULL DEFAULT '',
  level_info          TEXT NOT NULL DEFAULT '',
  age_group           TEXT NOT NULL DEFAULT '',
  class_format        TEXT NOT NULL DEFAULT '',
  monthly_price       REAL,
  currency            TEXT NOT NULL DEFAULT 'ETB',
  registration_fee    REAL DEFAULT 0.0,
  lessons_per_week    INTEGER,
  lesson_duration_min INTEGER,
  included_services   TEXT NOT NULL DEFAULT '',
  book_title          TEXT NOT NULL DEFAULT '',
  author_or_subject   TEXT NOT NULL DEFAULT '',
  required_materials  TEXT NOT NULL DEFAULT '',
  active              INTEGER NOT NULL DEFAULT 1,
  public_visible      INTEGER NOT NULL DEFAULT 1,
  is_sample           INTEGER NOT NULL DEFAULT 0,
  sort_order          INTEGER NOT NULL DEFAULT 0,
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  full_name         TEXT NOT NULL,
  age               INTEGER,
  country           TEXT NOT NULL DEFAULT '',
  city              TEXT NOT NULL DEFAULT '',
  phone             TEXT NOT NULL DEFAULT '',
  whatsapp          TEXT NOT NULL DEFAULT '',
  email             TEXT NOT NULL DEFAULT '',
  gender            TEXT NOT NULL DEFAULT '',
  parent_name       TEXT NOT NULL DEFAULT '',
  parent_phone      TEXT NOT NULL DEFAULT '',
  telegram_user_id  INTEGER,
  telegram_username TEXT NOT NULL DEFAULT '',
  status            TEXT NOT NULL DEFAULT 'new',
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registrations (
  reg_id                 TEXT PRIMARY KEY,
  student_id             INTEGER NOT NULL REFERENCES students(id),
  program_id             INTEGER REFERENCES programs(id),
  program_name_snapshot  TEXT NOT NULL,
  monthly_price_snapshot REAL,
  currency_snapshot      TEXT,
  reading_level          TEXT NOT NULL DEFAULT '',
  preferred_schedule     TEXT NOT NULL DEFAULT '',
  class_format           TEXT NOT NULL DEFAULT '',
  previous_experience    TEXT NOT NULL DEFAULT '',
  learning_goals         TEXT NOT NULL DEFAULT '',
  referral_source        TEXT NOT NULL DEFAULT '',
  parent_relationship    TEXT NOT NULL DEFAULT '',
  telegram_user_id       INTEGER,
  status                 TEXT NOT NULL DEFAULT 'new',
  admin_notes            TEXT NOT NULL DEFAULT '',
  sheets_sync_status     TEXT NOT NULL DEFAULT 'pending',
  sheets_synced_at       TEXT,
  sheets_sync_error      TEXT,
  archived_at            TEXT,
  created_at             TEXT NOT NULL,
  updated_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teachers (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  name              TEXT NOT NULL,
  phone             TEXT NOT NULL DEFAULT '',
  email             TEXT NOT NULL DEFAULT '',
  telegram_user_id  INTEGER,
  telegram_username TEXT NOT NULL DEFAULT '',
  specialization    TEXT NOT NULL DEFAULT '',
  bio               TEXT NOT NULL DEFAULT '',
  status            TEXT NOT NULL DEFAULT 'active',
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teacher_assignments (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  teacher_id  INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  program_id  INTEGER REFERENCES programs(id) ON DELETE SET NULL,
  status      TEXT NOT NULL DEFAULT 'active',
  assigned_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS class_schedules (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id         INTEGER REFERENCES students(id) ON DELETE CASCADE,
  teacher_id         INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
  program_id         INTEGER REFERENCES programs(id) ON DELETE SET NULL,
  title              TEXT NOT NULL,
  scheduled_at       TEXT NOT NULL,
  duration_min       INTEGER NOT NULL DEFAULT 45,
  timezone           TEXT NOT NULL DEFAULT 'UTC',
  meeting_link       TEXT NOT NULL DEFAULT '',
  status             TEXT NOT NULL DEFAULT 'scheduled',
  reminder_24h_sent  INTEGER NOT NULL DEFAULT 0,
  reminder_30m_sent  INTEGER NOT NULL DEFAULT 0,
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learning_progress (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id         INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  teacher_id         INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
  program_id         INTEGER REFERENCES programs(id) ON DELETE SET NULL,
  category           TEXT NOT NULL DEFAULT 'general',
  entry_date         TEXT NOT NULL,
  hifz_surah         TEXT NOT NULL DEFAULT '',
  hifz_ayah_range    TEXT NOT NULL DEFAULT '',
  hifz_new_memo      TEXT NOT NULL DEFAULT '',
  hifz_revision      TEXT NOT NULL DEFAULT '',
  recitation_quality TEXT NOT NULL DEFAULT '',
  lesson_completed   TEXT NOT NULL DEFAULT '',
  topics_covered     TEXT NOT NULL DEFAULT '',
  reading_level      TEXT NOT NULL DEFAULT '',
  areas_improvement  TEXT NOT NULL DEFAULT '',
  next_target        TEXT NOT NULL DEFAULT '',
  teacher_notes      TEXT NOT NULL DEFAULT '',
  created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_records (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  reg_id          TEXT REFERENCES registrations(reg_id) ON DELETE SET NULL,
  program_id      INTEGER REFERENCES programs(id) ON DELETE SET NULL,
  amount_due      REAL NOT NULL DEFAULT 0.0,
  amount_received REAL NOT NULL DEFAULT 0.0,
  currency        TEXT NOT NULL DEFAULT 'ETB',
  payment_period  TEXT NOT NULL DEFAULT '',
  due_date        TEXT NOT NULL DEFAULT '',
  received_at     TEXT,
  status          TEXT NOT NULL DEFAULT 'not_paid',
  admin_notes     TEXT NOT NULL DEFAULT '',
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS announcements (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  title           TEXT NOT NULL,
  message         TEXT NOT NULL,
  target_audience TEXT NOT NULL DEFAULT 'all',
  target_id       INTEGER,
  sent_count      INTEGER NOT NULL DEFAULT 0,
  failed_count    INTEGER NOT NULL DEFAULT 0,
  created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule_requests (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id   INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  reg_id       TEXT,
  request_type TEXT NOT NULL DEFAULT 'reschedule',
  details      TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'pending',
  admin_notes  TEXT NOT NULL DEFAULT '',
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bot_sessions (
  telegram_user_id INTEGER PRIMARY KEY,
  current_step     TEXT NOT NULL DEFAULT '',
  data_json        TEXT NOT NULL DEFAULT '{}',
  updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_preferences (
  telegram_user_id INTEGER PRIMARY KEY,
  language_code    TEXT NOT NULL DEFAULT 'en',
  updated_at       TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS sync_queue (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  reg_id          TEXT NOT NULL REFERENCES registrations(reg_id) ON DELETE CASCADE,
  operation       TEXT NOT NULL DEFAULT 'upsert',
  attempts        INTEGER NOT NULL DEFAULT 0,
  last_error      TEXT,
  next_attempt_at TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'pending',
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  admin_id    INTEGER,
  admin_email TEXT,
  action      TEXT NOT NULL,
  entity_type TEXT,
  entity_id   TEXT,
  details     TEXT,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS faqs (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  question   TEXT NOT NULL,
  answer     TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  visible    INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contact_messages (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT NOT NULL,
  email      TEXT NOT NULL DEFAULT '',
  phone      TEXT NOT NULL DEFAULT '',
  message    TEXT NOT NULL,
  is_read    INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_subscribers (
  telegram_user_id INTEGER PRIMARY KEY,
  first_name       TEXT NOT NULL DEFAULT '',
  username         TEXT NOT NULL DEFAULT '',
  subscribed_at    TEXT NOT NULL
);

"""

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_reg_status     ON registrations(status);
CREATE INDEX IF NOT EXISTS idx_reg_created    ON registrations(created_at);
CREATE INDEX IF NOT EXISTS idx_reg_program    ON registrations(program_id);
CREATE INDEX IF NOT EXISTS idx_reg_student    ON registrations(student_id);
CREATE INDEX IF NOT EXISTS idx_reg_tg_user    ON registrations(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_student_phone  ON students(phone);
CREATE INDEX IF NOT EXISTS idx_student_tg     ON students(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_sync_status    ON sync_queue(status, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_audit_created  ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_msg_created    ON contact_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_sched_time     ON class_schedules(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_sched_student  ON class_schedules(student_id);
CREATE INDEX IF NOT EXISTS idx_sched_teacher  ON class_schedules(teacher_id);
CREATE INDEX IF NOT EXISTS idx_prog_category  ON programs(category);
CREATE INDEX IF NOT EXISTS idx_learn_student  ON learning_progress(student_id);
CREATE INDEX IF NOT EXISTS idx_pay_student    ON payment_records(student_id);
CREATE INDEX IF NOT EXISTS idx_admin_sub_id   ON admin_subscribers(telegram_user_id);
"""

SAMPLE_PROGRAMS = [
    ("qaida-beginners", "Qaida — Arabic Alphabet & Foundations",
     "qaida",
     "Learn Arabic letters, recognition, pronunciation, joining letters, and reading words from the foundation.",
     "Complete beginners — children and adults", "All ages", "Online one-to-one or small group",
     "", "", ""),
    ("nezer-fluency", "Nezer — Quran Reading Practice & Fluency",
     "nezer",
     "Continuous Quran recitation practice, reading fluency, and teacher-guided correction.",
     "Students who know Arabic letters and can read words", "All ages", "Online one-to-one or small group",
     "", "", ""),
    ("tajweed-mastery", "Tajweed — Quran Recitation Rules",
     "tajweed",
     "Master Makharij, Sifaat, Noon Sakinah, Meem Sakinah, and practical application while reciting.",
     "Students who can read Quran and want recitation accuracy", "All ages", "Online one-to-one",
     "", "", ""),
    ("hifz-memorization", "Hifz — Quran Memorization & Revision",
     "hifz",
     "Structured daily memorization of new portions, rigorous revision (Muraja'ah), and teacher evaluation.",
     "Students committed to memorizing portions or the entire Quran", "All ages", "Online one-to-one",
     "", "", ""),
    ("kitab-safinat-naja", "Kitab — Safinat al-Naja (Basic Fiqh)",
     "kitab",
     "Foundational Shafi'i fiqh text covering Taharah, Salah, and worship essentials.",
     "Beginner to intermediate Islamic studies students", "Youth and adults", "Online group class",
     "Safinat al-Naja", "Salim ibn Sumayr al-Hadrami", "Textbook PDF provided"),
    ("kitab-arbaeen-nawawi", "Kitab — 40 Hadith of Imam Nawawi",
     "kitab",
     "Detailed study of forty fundamental prophetic traditions with moral and legal insights.",
     "Intermediate students", "Youth and adults", "Online group class",
     "Al-Arba'in an-Nawawiyyah", "Imam an-Nawawi", "Hadith commentary guide"),
    ("arabic-foundations", "Arabic Language — Reading & Conversation",
     "arabic",
     "Practical Arabic grammar, vocabulary, and conversational practice supporting Quranic comprehension.",
     "All levels seeking Arabic language fluency", "All ages", "Online class",
     "", "", ""),
    ("islamic-studies-essentials", "Islamic Studies — Aqeedah & Adab",
     "islamic_studies",
     "Foundational Islamic creed, ethics, prophetic biography (Seerah), and practical manners.",
     "Children, youth, and new learners", "All ages", "Online class",
     "", "", ""),
]

SAMPLE_FAQS = [
    ("How do I register?",
     "Open the Register page, fill in the registration form and submit it. You will receive a unique registration ID immediately. The academy will then contact you to confirm class availability and schedule.",
     1),
    ("How much does each program cost per month?",
     "Monthly prices for each program are shown on the Monthly Pricing page. If a price is not yet listed for a program, contact the academy for pricing. Payment is separate from registration.",
     2),
    ("Can beginners join?",
     "Yes. The Quran Reading for Beginners program is designed for complete beginners, including learning the Arabic letters.",
     3),
    ("Are children accepted?",
     "Yes. The Children's Quran Classes program is designed for young learners. Registration for a student under 18 requires a parent or guardian's name and contact number.",
     4),
    ("How are classes conducted?",
     "Classes are conducted online. The exact class format (one-to-one or small group) and platform are confirmed by the academy when they contact you after registration.",
     5),
    ("How many lessons are offered each week?",
     "The number of lessons per week for each program is shown on the Monthly Pricing page when configured by the academy. Contact the academy for any program where it is not yet listed.",
     6),
    ("What happens after registration?",
     "The academy reviews your registration and contacts you to confirm class availability, schedule, and payment. Your registration does not complete payment or guarantee a specific schedule by itself.",
     7),
    ("How can I contact the academy?",
     "Use the contact details on the Contact page, or send a message through the contact form on that page.",
     8),
    ("What payment methods are accepted?",
     "Accepted payment methods are confirmed by the academy when they contact you after registration. No payment is made through this website.",
     9),
]


def migrate_db() -> None:
    """Safely migrate existing database tables without data loss."""
    with _lock:
        conn = get_conn()
        cur = conn.cursor()

        # Check programs table columns
        prog_cols = [r["name"] for r in query("PRAGMA table_info(programs)")]
        if "category" not in prog_cols:
            cur.execute("ALTER TABLE programs ADD COLUMN category TEXT NOT NULL DEFAULT 'qaida'")
        if "book_title" not in prog_cols:
            cur.execute("ALTER TABLE programs ADD COLUMN book_title TEXT NOT NULL DEFAULT ''")
        if "author_or_subject" not in prog_cols:
            cur.execute("ALTER TABLE programs ADD COLUMN author_or_subject TEXT NOT NULL DEFAULT ''")
        if "required_materials" not in prog_cols:
            cur.execute("ALTER TABLE programs ADD COLUMN required_materials TEXT NOT NULL DEFAULT ''")
        if "registration_fee" not in prog_cols:
            cur.execute("ALTER TABLE programs ADD COLUMN registration_fee REAL DEFAULT 0.0")

        # Map existing programs to categories if they are default
        cur.execute("UPDATE programs SET category='qaida' WHERE slug LIKE '%beginner%' OR slug LIKE '%child%'")
        cur.execute("UPDATE programs SET category='nezer' WHERE slug LIKE '%improvement%' OR slug LIKE '%nezer%'")
        cur.execute("UPDATE programs SET category='tajweed' WHERE slug LIKE '%tajweed%'")
        cur.execute("UPDATE programs SET category='hifz' WHERE slug LIKE '%hifz%' OR slug LIKE '%memorization%'")
        cur.execute("UPDATE programs SET category='arabic' WHERE slug LIKE '%arabic%'")

        # Check students table columns
        student_cols = [r["name"] for r in query("PRAGMA table_info(students)")]
        if "telegram_user_id" not in student_cols:
            cur.execute("ALTER TABLE students ADD COLUMN telegram_user_id INTEGER")
        if "telegram_username" not in student_cols:
            cur.execute("ALTER TABLE students ADD COLUMN telegram_username TEXT NOT NULL DEFAULT ''")
        if "status" not in student_cols:
            cur.execute("ALTER TABLE students ADD COLUMN status TEXT NOT NULL DEFAULT 'new'")

        # Check admin_users table columns
        admin_cols = [r["name"] for r in query("PRAGMA table_info(admin_users)")]
        if "telegram_user_id" not in admin_cols:
            cur.execute("ALTER TABLE admin_users ADD COLUMN telegram_user_id INTEGER")

        # Check registrations table columns
        reg_cols = [r["name"] for r in query("PRAGMA table_info(registrations)")]
        if "telegram_user_id" not in reg_cols:
            cur.execute("ALTER TABLE registrations ADD COLUMN telegram_user_id INTEGER")
        if "parent_relationship" not in reg_cols:
            cur.execute("ALTER TABLE registrations ADD COLUMN parent_relationship TEXT NOT NULL DEFAULT ''")
        if "receipt_file_id" not in reg_cols:
            cur.execute("ALTER TABLE registrations ADD COLUMN receipt_file_id TEXT NOT NULL DEFAULT ''")
        if "receipt_url" not in reg_cols:
            cur.execute("ALTER TABLE registrations ADD COLUMN receipt_url TEXT NOT NULL DEFAULT ''")
        if "category_snapshot" not in reg_cols:
            cur.execute("ALTER TABLE registrations ADD COLUMN category_snapshot TEXT NOT NULL DEFAULT 'qaida'")

        # Check payment_records table columns
        pay_cols = [r["name"] for r in query("PRAGMA table_info(payment_records)")]
        if "receipt_file_id" not in pay_cols:
            cur.execute("ALTER TABLE payment_records ADD COLUMN receipt_file_id TEXT NOT NULL DEFAULT ''")
        if "receipt_url" not in pay_cols:
            cur.execute("ALTER TABLE payment_records ADD COLUMN receipt_url TEXT NOT NULL DEFAULT ''")

        # 1. Clean, uncluttered course titles
        cur.execute("UPDATE programs SET name='Qaida' WHERE slug='qaida-beginners'")
        cur.execute("UPDATE programs SET name='Nezer' WHERE slug='nezer-fluency'")
        cur.execute("UPDATE programs SET name='Tajweed' WHERE slug='tajweed-mastery'")
        cur.execute("UPDATE programs SET name='Hifz' WHERE slug='hifz-memorization'")
        cur.execute("UPDATE programs SET name='Arabic Language' WHERE slug='arabic-foundations'")
        cur.execute("UPDATE programs SET name='Islamic Studies' WHERE slug='islamic-studies-essentials'")

        # Deactivate old duplicate / redundant courses so each core category has 1 pristine entry
        cur.execute(
            "UPDATE programs SET active=0, public_visible=0 WHERE slug IN "
            "('quran-reading-beginners', 'childrens-quran-classes', 'quran-reading-improvement', 'tajweed', 'quran-memorization-hifz', 'arabic-quran-foundations')"
        )
        cur.execute(
            "UPDATE programs SET active=1, public_visible=1 WHERE slug IN "
            "('qaida-beginners', 'nezer-fluency', 'tajweed-mastery', 'hifz-memorization', 'arabic-foundations', 'islamic-studies-essentials')"
        )

        # 2. Seed comprehensive classical Kitab catalog
        cur.execute("UPDATE programs SET name='Safinat al-Naja', book_title='Safinat al-Naja' WHERE slug='kitab-safinat-naja'")
        cur.execute("UPDATE programs SET name='40 Hadith of Imam Nawawi', book_title='40 Hadith of Imam Nawawi' WHERE slug='kitab-arbaeen-nawawi'")

        kitabs = [
            ("kitab-safinat-naja", "Safinat al-Naja", "kitab",
             "Foundational Shafi'i fiqh text covering Taharah, Salah, and worship essentials.",
             "Beginner to intermediate", "Youth and adults", "Online group class",
             "Safinat al-Naja", "Salim ibn Sumayr al-Hadrami", "Textbook PDF provided"),
            ("kitab-arbaeen-nawawi", "40 Hadith of Imam Nawawi", "kitab",
             "Detailed study of forty fundamental prophetic traditions with moral and legal insights.",
             "Intermediate students", "Youth and adults", "Online group class",
             "Al-Arba'in an-Nawawiyyah", "Imam an-Nawawi", "Hadith commentary guide"),
            ("kitab-al-ajrumiyyah", "Al-Ajrumiyyah", "kitab",
             "Classical foundational primer in Arabic grammar (Nahw) essential for understanding Quranic & Islamic texts.",
             "Intermediate students", "Youth and adults", "Online class",
             "Al-Ajrumiyyah", "Ibn Adjurrum", "Grammar textbook PDF"),
            ("kitab-riyadh-salihin", "Riyadh as-Salihin", "kitab",
             "Selections from Imam an-Nawawi's renowned compilation of authentic Hadith on morals, etiquette, and worship.",
             "Intermediate to advanced", "Youth and adults", "Online class",
             "Riyadh as-Salihin", "Imam an-Nawawi", "Book of Hadith"),
            ("kitab-aqeedat-awwam", "Aqeedat al-Awwam", "kitab",
             "Concise poetic poem explaining foundational Islamic creed and beliefs for every Muslim.",
             "Beginner to intermediate", "All ages", "Online class",
             "Aqeedat al-Awwam", "Ahmad al-Marzuqi", "Poem text and explanation"),
            ("kitab-matn-abi-shuja", "Matn Abi Shuja", "kitab",
             "Comprehensive classical summary of Islamic jurisprudence (Fiqh) according to the Shafi'i school.",
             "Intermediate students", "Youth and adults", "Online class",
             "Ghayat al-Ikhtisar", "Abu Shuja al-Isfahani", "Fiqh textbook"),
        ]
        now = utcnow()
        for slug, name, cat, desc, level, age, fmt, b_title, b_auth, b_mat in kitabs:
            cur.execute(
                "INSERT INTO programs(slug, name, category, description, level_info, age_group, class_format, "
                "book_title, author_or_subject, required_materials, active, public_visible, sort_order, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 10, ?, ?) "
                "ON CONFLICT(slug) DO UPDATE SET name=excluded.name, book_title=excluded.book_title, "
                "author_or_subject=excluded.author_or_subject, category='kitab', active=1, public_visible=1, updated_at=excluded.updated_at",
                (slug, name, cat, desc, level, age, fmt, b_title, b_auth, b_mat, now, now),
            )

        cur.execute(
            "CREATE TABLE IF NOT EXISTS user_preferences ("
            "  telegram_user_id INTEGER PRIMARY KEY,"
            "  language_code    TEXT NOT NULL DEFAULT 'en',"
            "  updated_at       TEXT NOT NULL"
            ")"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS admin_subscribers ("
            "  telegram_user_id INTEGER PRIMARY KEY,"
            "  first_name       TEXT NOT NULL DEFAULT '',"
            "  username         TEXT NOT NULL DEFAULT '',"
            "  subscribed_at    TEXT NOT NULL"
            ")"
        )
        conn.commit()



def init_db() -> None:
    with _lock:
        conn = get_conn()
        conn.executescript(SCHEMA)
        conn.commit()

    migrate_db()

    with _lock:
        conn = get_conn()
        conn.executescript(INDEXES_SQL)
        conn.commit()

    now = utcnow()
    # Settings defaults (never overwrite values the admin has changed)
    executemany(
        "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
        [(k, json.dumps(v)) for k, v in DEFAULT_SETTINGS.items()],
    )

    # Seed programs
    for i, (slug, name, cat, desc, lvl, age, fmt, b_title, b_author, b_mat) in enumerate(SAMPLE_PROGRAMS):
        existing = query_one("SELECT id FROM programs WHERE slug=?", (slug,))
        if not existing:
            execute(
                "INSERT INTO programs(slug, name, category, description, level_info, age_group, "
                "class_format, monthly_price, currency, included_services, book_title, "
                "author_or_subject, required_materials, active, public_visible, is_sample, "
                "sort_order, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,NULL,?, '', ?, ?, ?, 1, 1, 1, ?, ?, ?)",
                (slug, name, cat, desc, lvl, age, fmt,
                 get_setting("default_currency") or "ETB",
                 b_title, b_author, b_mat, i + 1, now, now),
            )

    if query_one("SELECT 1 FROM faqs LIMIT 1") is None:
        executemany(
            "INSERT INTO faqs(question, answer, sort_order, visible, updated_at) "
            "VALUES(?,?,?,1,?)",
            [(q, a, o, now) for q, a, o in SAMPLE_FAQS],
        )


def admin_count() -> int:
    row = query_one("SELECT COUNT(*) AS c FROM admin_users")
    return row["c"] if row else 0


# ---------------------------------------------------------------------------
# Telegram Bot Helpers
# ---------------------------------------------------------------------------

def get_student_by_telegram_id(telegram_user_id: int) -> dict | None:
    return query_one(
        "SELECT * FROM students WHERE telegram_user_id=? ORDER BY id DESC LIMIT 1",
        (telegram_user_id,),
    )


def get_student_registrations(student_id: int) -> list[dict]:
    return query(
        "SELECT r.*, p.name AS program_name, p.category, p.description AS program_desc "
        "FROM registrations r "
        "LEFT JOIN programs p ON p.id = r.program_id "
        "WHERE r.student_id=? AND r.archived_at IS NULL "
        "ORDER BY r.created_at DESC",
        (student_id,),
    )


def link_telegram_to_registration(reg_id: str, phone: str, telegram_user_id: int, telegram_username: str = "") -> dict | None:
    """Safely verify phone match against registration and link Telegram user ID."""
    clean_p = phone.strip().replace(" ", "").replace("-", "")
    reg = query_one(
        "SELECT r.reg_id, r.student_id, s.phone "
        "FROM registrations r "
        "JOIN students s ON s.id = r.student_id "
        "WHERE r.reg_id=? AND r.archived_at IS NULL",
        (reg_id.strip(),),
    )
    if not reg:
        return None
    db_phone = (reg["phone"] or "").strip().replace(" ", "").replace("-", "")
    if clean_p not in db_phone and db_phone not in clean_p:
        return None

    now = utcnow()
    execute(
        "UPDATE students SET telegram_user_id=?, telegram_username=?, updated_at=? WHERE id=?",
        (telegram_user_id, telegram_username or "", now, reg["student_id"]),
    )
    execute(
        "UPDATE registrations SET telegram_user_id=?, updated_at=? WHERE reg_id=?",
        (telegram_user_id, now, reg["reg_id"]),
    )
    return query_one(
        "SELECT r.*, s.full_name, s.phone FROM registrations r JOIN students s ON s.id=r.student_id WHERE r.reg_id=?",
        (reg_id,),
    )


def get_student_schedule(student_id: int) -> list[dict]:
    return query(
        "SELECT cs.*, t.name AS teacher_name, p.name AS program_name "
        "FROM class_schedules cs "
        "LEFT JOIN teachers t ON t.id = cs.teacher_id "
        "LEFT JOIN programs p ON p.id = cs.program_id "
        "WHERE cs.student_id=? "
        "ORDER BY cs.scheduled_at ASC",
        (student_id,),
    )


def get_student_progress(student_id: int) -> list[dict]:
    return query(
        "SELECT lp.*, t.name AS teacher_name, p.name AS program_name "
        "FROM learning_progress lp "
        "LEFT JOIN teachers t ON t.id = lp.teacher_id "
        "LEFT JOIN programs p ON p.id = lp.program_id "
        "WHERE lp.student_id=? "
        "ORDER BY lp.entry_date DESC, lp.id DESC",
        (student_id,),
    )


def get_student_payments(student_id: int) -> list[dict]:
    return query(
        "SELECT pr.*, p.name AS program_name "
        "FROM payment_records pr "
        "LEFT JOIN programs p ON p.id = pr.program_id "
        "WHERE pr.student_id=? "
        "ORDER BY pr.created_at DESC",
        (student_id,),
    )


def register_admin_subscriber(telegram_user_id: int, first_name: str = "", username: str = "") -> None:
    if not telegram_user_id:
        return
    now = utcnow()
    execute(
        "INSERT INTO admin_subscribers(telegram_user_id, first_name, username, subscribed_at) "
        "VALUES(?, ?, ?, ?) "
        "ON CONFLICT(telegram_user_id) DO UPDATE SET "
        "first_name=excluded.first_name, username=excluded.username",
        (telegram_user_id, first_name or "", username or "", now),
    )


def get_all_admin_subscribers() -> list[dict]:
    return query("SELECT * FROM admin_subscribers ORDER BY subscribed_at DESC")


def is_telegram_admin(telegram_user_id: int, env_admin_ids: list[int] | None = None) -> bool:
    if env_admin_ids and telegram_user_id in env_admin_ids:
        return True
    row = query_one(
        "SELECT 1 FROM admin_users WHERE telegram_user_id=? AND status='active'",
        (telegram_user_id,),
    )
    if row is not None:
        return True
    sub = query_one(
        "SELECT 1 FROM admin_subscribers WHERE telegram_user_id=?",
        (telegram_user_id,),
    )
    return sub is not None


def get_all_admin_telegram_ids(env_admin_ids: list[int] | None = None) -> list[int]:
    ids = set(env_admin_ids or [])
    rows = query("SELECT telegram_user_id FROM admin_users WHERE telegram_user_id IS NOT NULL AND status='active'")
    for r in rows:
        if r["telegram_user_id"]:
            ids.add(int(r["telegram_user_id"]))
    sub_rows = query("SELECT telegram_user_id FROM admin_subscribers WHERE telegram_user_id IS NOT NULL")
    for r in sub_rows:
        if r["telegram_user_id"]:
            ids.add(int(r["telegram_user_id"]))
    return list(ids)


def get_bot_session(telegram_user_id: int) -> dict:
    row = query_one("SELECT * FROM bot_sessions WHERE telegram_user_id=?", (telegram_user_id,))
    if not row:
        return {"current_step": "", "data": {}}
    try:
        data = json.loads(row["data_json"])
    except (ValueError, TypeError):
        data = {}
    return {"current_step": row["current_step"], "data": data}


def save_bot_session(telegram_user_id: int, current_step: str, data: dict) -> None:
    now = utcnow()
    execute(
        "INSERT INTO bot_sessions(telegram_user_id, current_step, data_json, updated_at) "
        "VALUES(?, ?, ?, ?) "
        "ON CONFLICT(telegram_user_id) DO UPDATE SET "
        "current_step=excluded.current_step, data_json=excluded.data_json, updated_at=excluded.updated_at",
        (telegram_user_id, current_step, json.dumps(data), now),
    )


def clear_bot_session(telegram_user_id: int) -> None:
    execute("DELETE FROM bot_sessions WHERE telegram_user_id=?", (telegram_user_id,))


def get_user_language(telegram_user_id: int | None) -> str:
    if not telegram_user_id:
        return "en"
    row = query_one("SELECT language_code FROM user_preferences WHERE telegram_user_id=?", (telegram_user_id,))
    if row and row.get("language_code"):
        return row["language_code"]
    return "en"


def has_user_language(telegram_user_id: int | None) -> bool:
    if not telegram_user_id:
        return False
    row = query_one("SELECT 1 FROM user_preferences WHERE telegram_user_id=?", (telegram_user_id,))
    return row is not None


def set_user_language(telegram_user_id: int, language_code: str) -> None:
    now = utcnow()
    execute(
        "INSERT INTO user_preferences(telegram_user_id, language_code, updated_at) "
        "VALUES(?, ?, ?) "
        "ON CONFLICT(telegram_user_id) DO UPDATE SET language_code=excluded.language_code, updated_at=excluded.updated_at",
        (telegram_user_id, language_code, now),
    )

