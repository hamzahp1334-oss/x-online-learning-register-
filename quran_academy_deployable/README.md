# Online Quran Learning Academy — Telegram Bot & Web Platform

A production-grade Telegram Bot system and registration platform for an Online Quran Learning Academy, built with Python, SQLite (WAL mode), Flask, and Google Sheets synchronization.

---

## 🌟 Academy Teaching Disciplines

The system supports all 7 core Islamic learning areas:

1. **Qaida** — Arabic alphabet recognition, pronunciation (Makharij), and foundational reading.
2. **Nezer** — Quran reading practice and fluency (Nazirah).
3. **Tajweed** — Essential and advanced Quran recitation rules.
4. **Hifz** — Quran memorization, daily revision (Muraja'ah), and evaluation.
5. **Kitab** — Classical Islamic book and text studies (configurable titles, e.g., Safinat al-Naja, 40 Hadith of Imam Nawawi).
6. **Arabic Language** — Conversational, foundational, and grammar lessons.
7. **Islamic Studies** — Creed (Aqeedah), Fiqh, Seerah, and manners (Adab).

---

## 🤖 Telegram Bot Architecture

### Student Bot Experience
- **Welcome Greeting:** Configurable greeting with academy name and tagline.
- **📚 Explore Courses:** Categorized course cards showing real descriptions, levels, frequency, class formats, and actual configured monthly fees (shows "Contact the Academy" if unpriced; never invents prices).
- **📝 Step-by-Step Registration Wizard:**
  - Student details (Name, Age, Country, City, Phone, WhatsApp, Email, Telegram ID).
  - Parent/Guardian verification (strictly mandatory for students under 18).
  - Course selection & learning levels (including Hifz-specific memorization history).
  - Preferred schedule & class format.
  - Review summary with locked fee snapshots.
  - Unique Registration ID generation (`QA-YYMMDD-XXXXXX`).
  - Supports resuming interrupted registrations.
- **👤 My Profile:** Authenticated by Telegram user ID. Displays registration status, fee snapshot, assigned teacher, confirmed class schedule, and learning progress. Also supports linking website registrations safely.
- **📅 Class Schedules & Reminders:** View scheduled classes with online meeting links. Automated 24-hour and 30-minute reminders dispatched before each class.
- **📊 Learning Progress Tracking:** Real-time visibility into teacher-recorded milestones for Hifz, Nezer, Qaida, Tajweed, and Kitab.
- **❓ Help & Contact:** Dynamic FAQs and direct messaging to academy administrators.

### Administrator Bot Experience
- **Strict Authorization:** Only authorized Telegram user IDs (`admin_users` table or `ADMIN_TELEGRAM_IDS` in `.env`) can access administrative features.
- **Instant Alerts:** New registrations (from Telegram or the Website) send interactive notifications to administrators with inline action buttons (`Approve`, `Reject`, `Assign Teacher`, `View Details`).
- **📊 Dashboard:** Real-time metrics for registrations, active students, popular courses, upcoming classes, payment tracking, and Google Sheets sync health.
- **📝 Registrations:** Filter, review, approve, reject with reason, or assign teachers.
- **👨‍🎓 Students:** Search student profiles, assign courses, update status, view progress, and add internal notes.
- **📚 Manage Courses & Kitab:** Add/edit courses, manage Kitab titles and materials dynamically without touching code.
- **💰 Manage Pricing:** Update monthly fees and currencies dynamically; preserves older registration fee snapshots.
- **👨‍🏫 Teachers:** Manage teacher profiles and student assignments.
- **📅 Class Schedules:** Schedule classes, add online meeting links, and manage conflicts.
- **📖 Learning Progress:** Record detailed Hifz portions, recitation quality, Qaida lessons, and homework.
- **💳 Payment Status:** Track manual payment records (`Not Paid`, `Awaiting Verification`, `Paid`, `Overdue`, `Waived`).
- **📢 Announcements:** Broadcast messages to students with preview and confirmation.
- **📄 Google Sheets Sync:** View sync queue health and trigger manual retries.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11+
- Dependencies installed from `requirements.txt`:
  ```bash
  pip install -r requirements.txt
  ```

### 2. Configuration (`.env`)
Copy `.env.example` to `.env` or edit the existing `.env`:
```ini
# Server configuration
PORT=3000
HOST=0.0.0.0

# First Administrator account for Web Dashboard
ADMIN_NAME=Administrator
ADMIN_EMAIL=admin@academy.test
ADMIN_PASSWORD=your_secure_password

# Telegram Bot Token
TELEGRAM_BOT_TOKEN="8594518638:AAFxCnlFmhNZhwc-tLKA1rjWBhIaAhoeHe8"

# Optional separate admin bot token (if omitted, runs unified mode)
# ADMIN_BOT_TOKEN=

# Authorized Telegram user IDs for Admin Bot (comma-separated)
ADMIN_TELEGRAM_IDS=123456789,987654321

# Google Sheets Integration (Optional for local testing, required for cloud sync)
GOOGLE_SHEET_ID=
GOOGLE_SERVICE_ACCOUNT_EMAIL=
GOOGLE_PRIVATE_KEY=
GOOGLE_SHEET_WORKSHEET=Registrations
```

### 3. Running the Telegram Bot
To start the Telegram bot service:
```bash
python run_bot.py
```

### 4. Running the Web Platform
To start the Flask registration website and admin web dashboard:
```bash
python app.py
```
- Public website: `http://localhost:3000`
- Admin web dashboard: `http://localhost:3000/admin`

---

## 🧪 Automated Testing

Run the full end-to-end test suite covering all 17 specification requirements:
```bash
python -m unittest tests/test_bot_core.py -v
```
All 17 tests will run and pass:
- Browsing all 7 course categories
- Actual pricing and "Contact Academy" fallback
- Full student registration workflow
- Minor parent/guardian validation
- Admin instant notification dispatch
- Admin dashboard synchronization
- Google Sheets queue deduplication and idempotence
- Shared database access across Website and Telegram
- Admin authorization security gate
- Student profile data isolation
- Dynamic course pricing updates
- Historical registration snapshot immutability
- Hifz & learning progress tracking
- Class schedule reminders (24h & 30m)
- Google Sheets network resilience and backoff retry
- Service recovery and interrupted wizard resumption
- Payment status verification security
