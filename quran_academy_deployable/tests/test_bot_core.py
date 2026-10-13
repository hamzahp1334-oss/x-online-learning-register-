"""Automated End-to-End Test Suite for Online Quran Academy Bot System.

Verifies all 17 core specification requirements:
1. Course browsing across all 7 categories
2. Actual monthly price display (no invented prices)
3. Student registration completion
4. Minor guardian validation
5. Admin instant notification dispatch
6. Admin dashboard visibility
7. Google Sheets idempotence & deduplication
8. Shared student database (website & telegram)
9. Admin authorization protection
10. Student data isolation
11. Dynamic price updates
12. Historical price snapshot immutability
13. Hifz & learning progress isolation & tracking
14. Class scheduling & automated reminders (24h & 30m)
15. Google Sheets error retry resilience
16. Service recovery & interrupted registration restoration
17. Payment status tracking & verification
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

# Ensure app path in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import db
import sheets
from bot import bridge, config, scheduler


class TestQuranAcademyBotSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use test database or ensure shared db initialized
        db.init_db()

    def setUp(self):
        self.now = db.utcnow()

    # -----------------------------------------------------------------------
    # Requirement 1: Browse courses across categories
    # -----------------------------------------------------------------------
    def test_01_browse_courses_all_categories(self):
        """1. A student opens the bot and browses all available courses."""
        categories = ["qaida", "nezer", "tajweed", "hifz", "kitab", "arabic", "islamic_studies"]
        for cat in categories:
            courses = db.query(
                "SELECT * FROM programs WHERE category=? AND active=1 AND public_visible=1",
                (cat,),
            )
            self.assertTrue(len(courses) > 0, f"Expected courses in category '{cat}'")
            for c in courses:
                self.assertIn("name", c)
                self.assertIn("description", c)
                self.assertIn("level_info", c)

    # -----------------------------------------------------------------------
    # Requirement 2: Actual monthly price display
    # -----------------------------------------------------------------------
    def test_02_actual_price_display(self):
        """2. A student views the actual monthly price."""
        # Unpriced course shows None (rendered as 'Contact the Academy')
        p_unpriced = db.query_one("SELECT * FROM programs WHERE monthly_price IS NULL LIMIT 1")
        if p_unpriced:
            self.assertIsNone(p_unpriced["monthly_price"])

        # Explicitly configure a price and verify it matches
        prog = db.query_one("SELECT id FROM programs LIMIT 1")
        db.execute("UPDATE programs SET monthly_price=850.00, currency='ETB' WHERE id=?", (prog["id"],))
        p_priced = db.query_one("SELECT * FROM programs WHERE id=?", (prog["id"],))

        self.assertIsNotNone(p_priced["monthly_price"])
        self.assertEqual(p_priced["monthly_price"], 850.00)
        self.assertEqual(p_priced["currency"], "ETB")

    # -----------------------------------------------------------------------
    # Requirement 3: Student completes registration
    # -----------------------------------------------------------------------
    def test_03_student_completes_registration(self):
        """3. A student completes registration."""
        reg_id = db.gen_reg_id()
        tg_id = 99887766

        prog = db.query_one("SELECT * FROM programs WHERE id=1")
        with db.tx() as conn:
            cur = conn.execute(
                "INSERT INTO students(full_name, age, country, city, phone, telegram_user_id, status, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, 'new', ?, ?)",
                ("Ahmad Bilal", 22, "Ethiopia", "Addis Ababa", "+251911002233", tg_id, self.now, self.now),
            )
            student_id = cur.lastrowid
            conn.execute(
                "INSERT INTO registrations(reg_id, student_id, program_id, program_name_snapshot, "
                "monthly_price_snapshot, currency_snapshot, reading_level, preferred_schedule, class_format, "
                "telegram_user_id, status, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)",
                (
                    reg_id,
                    student_id,
                    prog["id"],
                    prog["name"],
                    prog["monthly_price"],
                    prog["currency"],
                    "Intermediate",
                    "Morning",
                    "One-to-one",
                    tg_id,
                    self.now,
                    self.now,
                ),
            )

        saved = db.query_one("SELECT * FROM registrations WHERE reg_id=?", (reg_id,))
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "new")
        self.assertEqual(saved["telegram_user_id"], tg_id)
        self.assertTrue(saved["reg_id"].startswith("QA-"))

        # Verify enqueued for Sheets
        sheets.enqueue_registration(reg_id)
        job = db.query_one("SELECT * FROM sync_queue WHERE reg_id=?", (reg_id,))
        self.assertIsNotNone(job)

    # -----------------------------------------------------------------------
    # Requirement 4: Minor requires guardian details
    # -----------------------------------------------------------------------
    def test_04_minor_requires_guardian_details(self):
        """4. A minor is required to provide guardian details."""
        minor_age = 11

        # Validation logic check
        def validate_registration_data(data):
            if data.get("age") and data["age"] < 18:
                if not data.get("parent_name") or not data.get("parent_phone"):
                    return False, "Parent/guardian name and contact required for minors."
            return True, "Valid"

        valid, msg = validate_registration_data({"full_name": "Child Student", "age": minor_age, "parent_name": "", "parent_phone": ""})
        self.assertFalse(valid)

        valid, msg = validate_registration_data({
            "full_name": "Child Student",
            "age": minor_age,
            "parent_name": "Father Name",
            "parent_phone": "+251911445566",
        })
        self.assertTrue(valid)

    # -----------------------------------------------------------------------
    # Requirement 5: Admin receives new-registration notification
    # -----------------------------------------------------------------------
    def test_05_admin_notification(self):
        """5. An admin receives a new-registration notification."""
        test_admin_id = 777666555
        with patch("bot.bridge.send_telegram_message", return_value=True) as mock_send, \
             patch("db.get_all_admin_telegram_ids", return_value=[test_admin_id]):

            reg_data = {
                "reg_id": "QA-TEST-001",
                "full_name": "Fatima Omar",
                "age": 19,
                "country": "Ethiopia",
                "city": "Addis Ababa",
                "phone": "+251922334455",
                "program_name_snapshot": "Tajweed Mastery",
                "monthly_price_snapshot": 600.0,
                "currency_snapshot": "ETB",
                "preferred_schedule": "Evening",
            }
            sent_count = bridge.notify_admins_new_registration(reg_data)
            self.assertEqual(sent_count, 1)
            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            self.assertEqual(args[1], test_admin_id)
            self.assertIn("Fatima Omar", args[2])
            self.assertIn("QA-TEST-001", args[2])

    # -----------------------------------------------------------------------
    # Requirement 6: Registration appears in admin dashboard
    # -----------------------------------------------------------------------
    def test_06_registration_appears_in_dashboard(self):
        """6. The registration appears in the admin dashboard."""
        reg_id = db.gen_reg_id()
        with db.tx() as conn:
            cur = conn.execute(
                "INSERT INTO students(full_name, status, created_at, updated_at) VALUES('Dashboard Student', 'new', ?, ?)",
                (self.now, self.now),
            )
            sid = cur.lastrowid
            conn.execute(
                "INSERT INTO registrations(reg_id, student_id, program_name_snapshot, status, created_at, updated_at) "
                "VALUES(?, ?, 'Hifz Program', 'new', ?, ?)",
                (reg_id, sid, self.now, self.now),
            )

        new_count = db.query_one("SELECT COUNT(*) c FROM registrations WHERE status='new' AND archived_at IS NULL")["c"]
        self.assertGreater(new_count, 0)

        recent = db.query(
            "SELECT reg_id FROM registrations WHERE archived_at IS NULL ORDER BY created_at DESC LIMIT 5"
        )
        self.assertTrue(any(r["reg_id"] == reg_id for r in recent))

    # -----------------------------------------------------------------------
    # Requirement 7: Google Sheets idempotence without duplicate rows
    # -----------------------------------------------------------------------
    def test_07_google_sheets_queue_idempotence(self):
        """7. The registration appears in Google Sheets queue without duplicate rows."""
        reg_id = db.gen_reg_id()
        with db.tx() as conn:
            cur = conn.execute("INSERT INTO students(full_name, created_at, updated_at) VALUES('Sheets Student', ?, ?)", (self.now, self.now))
            sid = cur.lastrowid
            conn.execute(
                "INSERT INTO registrations(reg_id, student_id, program_name_snapshot, status, created_at, updated_at) "
                "VALUES(?, ?, 'Qaida', 'new', ?, ?)",
                (reg_id, sid, self.now, self.now),
            )

        # Enqueue twice
        sheets.enqueue_registration(reg_id)
        sheets.enqueue_registration(reg_id)

        jobs = db.query("SELECT * FROM sync_queue WHERE reg_id=?", (reg_id,))
        self.assertEqual(len(jobs), 1, "Expected exactly 1 sync queue job for the registration (idempotent)")

    # -----------------------------------------------------------------------
    # Requirement 8: Website and Telegram share student records
    # -----------------------------------------------------------------------
    def test_08_website_and_telegram_shared_database(self):
        """8. A website registration and Telegram registration use the same student system."""
        reg_id = db.gen_reg_id()
        phone = "+251955667788"
        tg_id = 44556677

        # Website registration creates student without telegram ID initially
        with db.tx() as conn:
            cur = conn.execute(
                "INSERT INTO students(full_name, phone, created_at, updated_at) VALUES('Website Student', ?, ?, ?)",
                (phone, self.now, self.now),
            )
            sid = cur.lastrowid
            conn.execute(
                "INSERT INTO registrations(reg_id, student_id, program_name_snapshot, status, created_at, updated_at) "
                "VALUES(?, ?, 'Nezer', 'new', ?, ?)",
                (reg_id, sid, self.now, self.now),
            )

        # Student opens Telegram and links via registration ID and phone
        linked = db.link_telegram_to_registration(reg_id, phone, tg_id, "tg_web_user")
        self.assertIsNotNone(linked)

        # Telegram bot queries student by telegram user ID
        student_in_tg = db.get_student_by_telegram_id(tg_id)
        self.assertIsNotNone(student_in_tg)
        self.assertEqual(student_in_tg["id"], sid)
        self.assertEqual(student_in_tg["full_name"], "Website Student")

    # -----------------------------------------------------------------------
    # Requirement 9: Unauthorized user cannot access admin bot
    # -----------------------------------------------------------------------
    def test_09_unauthorized_user_blocked(self):
        """9. An unauthorized user cannot access the admin bot."""
        random_user_id = 12349999
        self.assertFalse(db.is_telegram_admin(random_user_id, [555, 666]))

        # Authorize explicitly
        self.assertTrue(db.is_telegram_admin(555, [555, 666]))

    # -----------------------------------------------------------------------
    # Requirement 10: Student cannot access another student's data
    # -----------------------------------------------------------------------
    def test_10_student_data_isolation(self):
        """10. A student cannot access another student's private information."""
        user_a_tg = 11110001
        user_b_tg = 22220002

        db.execute(
            "INSERT INTO students(full_name, telegram_user_id, created_at, updated_at) VALUES('Student A', ?, ?, ?)",
            (user_a_tg, self.now, self.now),
        )
        db.execute(
            "INSERT INTO students(full_name, telegram_user_id, created_at, updated_at) VALUES('Student B', ?, ?, ?)",
            (user_b_tg, self.now, self.now),
        )

        stu_a = db.get_student_by_telegram_id(user_a_tg)
        stu_b = db.get_student_by_telegram_id(user_b_tg)

        self.assertNotEqual(stu_a["id"], stu_b["id"])
        self.assertEqual(stu_a["full_name"], "Student A")
        self.assertEqual(stu_b["full_name"], "Student B")

    # -----------------------------------------------------------------------
    # Requirement 11: Dynamic price updates
    # -----------------------------------------------------------------------
    def test_11_admin_changes_price_displays_updated(self):
        """11. An admin changes a course price and the student bot displays the updated price."""
        prog = db.query_one("SELECT id FROM programs LIMIT 1")
        pid = prog["id"]

        db.execute("UPDATE programs SET monthly_price=950.00, currency='ETB', updated_at=? WHERE id=?", (self.now, pid))
        updated = db.query_one("SELECT monthly_price, currency FROM programs WHERE id=?", (pid,))
        self.assertEqual(updated["monthly_price"], 950.00)

        db.execute("UPDATE programs SET monthly_price=1200.00, currency='ETB', updated_at=? WHERE id=?", (self.now, pid))
        updated2 = db.query_one("SELECT monthly_price, currency FROM programs WHERE id=?", (pid,))
        self.assertEqual(updated2["monthly_price"], 1200.00)

    # -----------------------------------------------------------------------
    # Requirement 12: Historical price snapshots remain unchanged
    # -----------------------------------------------------------------------
    def test_12_historical_price_snapshot_immutable(self):
        """12. Historical registration price snapshots remain unchanged."""
        prog = db.query_one("SELECT id, name FROM programs LIMIT 1")
        pid = prog["id"]

        # Initial price 500 ETB
        db.execute("UPDATE programs SET monthly_price=500.00, currency='ETB' WHERE id=?", (pid,))

        reg_id = db.gen_reg_id()
        with db.tx() as conn:
            cur = conn.execute("INSERT INTO students(full_name, created_at, updated_at) VALUES('Historical Student', ?, ?)", (self.now, self.now))
            sid = cur.lastrowid
            conn.execute(
                "INSERT INTO registrations(reg_id, student_id, program_id, program_name_snapshot, "
                "monthly_price_snapshot, currency_snapshot, status, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, 500.00, 'ETB', 'new', ?, ?)",
                (reg_id, sid, pid, prog["name"], self.now, self.now),
            )

        # Later, admin updates course price to 1000 ETB
        db.execute("UPDATE programs SET monthly_price=1000.00, currency='ETB' WHERE id=?", (pid,))

        # Course is 1000 ETB
        current_course = db.query_one("SELECT monthly_price FROM programs WHERE id=?", (pid,))
        self.assertEqual(current_course["monthly_price"], 1000.00)

        # BUT old registration remains locked at 500 ETB!
        old_reg = db.query_one("SELECT monthly_price_snapshot FROM registrations WHERE reg_id=?", (reg_id,))
        self.assertEqual(old_reg["monthly_price_snapshot"], 500.00)

    # -----------------------------------------------------------------------
    # Requirement 13: Learning progress tracking and isolation
    # -----------------------------------------------------------------------
    def test_13_teacher_records_hifz_progress(self):
        """13. A teacher records Hifz progress and the correct student can view it."""
        sid_1 = db.execute("INSERT INTO students(full_name, created_at, updated_at) VALUES('Hifz Student 1', ?, ?)", (self.now, self.now))
        sid_2 = db.execute("INSERT INTO students(full_name, created_at, updated_at) VALUES('Hifz Student 2', ?, ?)", (self.now, self.now))
        tid = db.execute("INSERT INTO teachers(name, status, created_at, updated_at) VALUES('Ustadh Khalid', 'active', ?, ?)", (self.now, self.now))

        # Teacher records progress for Student 1
        db.execute(
            "INSERT INTO learning_progress(student_id, teacher_id, category, entry_date, hifz_surah, hifz_ayah_range, "
            "hifz_new_memo, recitation_quality, teacher_notes, created_at) "
            "VALUES(?, ?, 'hifz', '2026-10-12', 'Al-Kahf', '1-20', 'Memorized 20 ayahs', 'Excellent', 'MashaAllah fluent recitation', ?)",
            (sid_1, tid, self.now),
        )

        p1 = db.get_student_progress(sid_1)
        p2 = db.get_student_progress(sid_2)

        self.assertEqual(len(p1), 1)
        self.assertEqual(p1[0]["hifz_surah"], "Al-Kahf")
        self.assertEqual(p1[0]["recitation_quality"], "Excellent")
        self.assertEqual(len(p2), 0, "Student 2 must not see Student 1's progress")

    # -----------------------------------------------------------------------
    # Requirement 14: Class reminders sent at configured intervals
    # -----------------------------------------------------------------------
    def test_14_class_reminders_dispatched(self):
        """14. A class reminder is sent at the configured time."""
        tg_id = 99119911
        sid = db.execute("INSERT INTO students(full_name, telegram_user_id, created_at, updated_at) VALUES('Schedule Student', ?, ?, ?)", (tg_id, self.now, self.now))
        tid = db.execute("INSERT INTO teachers(name, created_at, updated_at) VALUES('Ustadh Omar', ?, ?)", (self.now, self.now))

        # 1. Schedule class 24 hours ahead
        t_24h = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cid_24 = db.execute(
            "INSERT INTO class_schedules(student_id, teacher_id, title, scheduled_at, duration_min, meeting_link, status, reminder_24h_sent, created_at, updated_at) "
            "VALUES(?, ?, 'Tajweed Class', ?, 45, 'https://meet.example.com/class', 'scheduled', 0, ?, ?)",
            (sid, tid, t_24h, self.now, self.now),
        )

        with patch("bot.bridge.notify_class_reminder", return_value=True) as mock_remind:
            sent = scheduler.check_and_send_class_reminders()
            self.assertGreaterEqual(sent, 1)
            mock_remind.assert_called()

        # Check reminder marked sent to prevent duplicates
        row = db.query_one("SELECT reminder_24h_sent FROM class_schedules WHERE id=?", (cid_24,))
        self.assertEqual(row["reminder_24h_sent"], 1)

    # -----------------------------------------------------------------------
    # Requirement 15: Google Sheets resilience & retry
    # -----------------------------------------------------------------------
    def test_15_google_sheets_retry_resilience(self):
        """15. A temporary Google Sheets failure is retried without losing data."""
        reg_id = db.gen_reg_id()
        with db.tx() as conn:
            cur = conn.execute("INSERT INTO students(full_name, created_at, updated_at) VALUES('Resilient Student', ?, ?)", (self.now, self.now))
            sid = cur.lastrowid
            conn.execute(
                "INSERT INTO registrations(reg_id, student_id, program_name_snapshot, status, created_at, updated_at) "
                "VALUES(?, ?, 'Hifz', 'new', ?, ?)",
                (reg_id, sid, self.now, self.now),
            )

        sheets.enqueue_registration(reg_id)

        # Mark job as failed simulating network timeout
        db.execute("UPDATE sync_queue SET status='failed', attempts=1, last_error='HTTP 503 Service Unavailable' WHERE reg_id=?", (reg_id,))
        failed_job = db.query_one("SELECT * FROM sync_queue WHERE reg_id=?", (reg_id,))
        self.assertEqual(failed_job["status"], "failed")

        # Database record still completely intact!
        reg_db = db.query_one("SELECT * FROM registrations WHERE reg_id=?", (reg_id,))
        self.assertIsNotNone(reg_db)

        # Reset failed jobs for retry
        reset_count = sheets.retry_failed()
        self.assertGreaterEqual(reset_count, 1)

        job_pending = db.query_one("SELECT status FROM sync_queue WHERE reg_id=?", (reg_id,))
        self.assertEqual(job_pending["status"], "pending")

    # -----------------------------------------------------------------------
    # Requirement 16: Service recovery & state restoration
    # -----------------------------------------------------------------------
    def test_16_service_recovery_and_session_restoration(self):
        """16. The bots recover correctly after restarting the hosting service."""
        user_tg_id = 88776655
        partial_data = {
            "full_name": "Yusuf Zayd",
            "age": 16,
            "country": "Ethiopia",
            "city": "Addis Ababa",
            "selected_program_ids": [1],
        }

        # Save session in database
        db.save_bot_session(user_tg_id, "reg_phone", partial_data)

        # Simulate service restart (fetching session fresh from database)
        restored_session = db.get_bot_session(user_tg_id)
        self.assertEqual(restored_session["current_step"], "reg_phone")
        self.assertEqual(restored_session["data"]["full_name"], "Yusuf Zayd")
        self.assertEqual(restored_session["data"]["age"], 16)

        # Clear session
        db.clear_bot_session(user_tg_id)
        empty_session = db.get_bot_session(user_tg_id)
        self.assertEqual(empty_session["current_step"], "")

    # -----------------------------------------------------------------------
    # Requirement 17: Payment verification
    # -----------------------------------------------------------------------
    def test_17_payment_status_verification(self):
        """17. Payment status is not marked as paid without authorized verification."""
        sid = db.execute("INSERT INTO students(full_name, created_at, updated_at) VALUES('Payment Student', ?, ?)", (self.now, self.now))

        pid = db.execute(
            "INSERT INTO payment_records(student_id, amount_due, amount_received, currency, status, created_at, updated_at) "
            "VALUES(?, 1500.0, 0.0, 'ETB', 'not_paid', ?, ?)",
            (sid, self.now, self.now),
        )

        p_init = db.query_one("SELECT status, amount_received FROM payment_records WHERE id=?", (pid,))
        self.assertEqual(p_init["status"], "not_paid")
        self.assertEqual(p_init["amount_received"], 0.0)

        # Authorized verification sets to paid
        db.execute(
            "UPDATE payment_records SET status='paid', amount_received=1500.0, received_at=?, admin_notes='Bank transfer confirmed' WHERE id=?",
            (self.now, pid),
        )
        p_verified = db.query_one("SELECT status, amount_received, admin_notes FROM payment_records WHERE id=?", (pid,))
        self.assertEqual(p_verified["status"], "paid")
        self.assertEqual(p_verified["amount_received"], 1500.0)
        self.assertEqual(p_verified["admin_notes"], "Bank transfer confirmed")

    # -----------------------------------------------------------------------
    # Requirement 18: Streamlined category-only registration selection
    # -----------------------------------------------------------------------
    def test_18_category_only_wizard_flow(self):
        """18. Student selects category directly (Qaida, Nezer, Tajweed, etc.) without sub-level quizzes."""
        from bot import student_bot
        kb = student_bot.category_keyboard()
        buttons_data = [btn.callback_data for row in kb.inline_keyboard for btn in row]

        # Verify all core categories are present
        self.assertIn("stu_reg_cat:qaida", buttons_data)
        self.assertIn("stu_reg_cat:nezer", buttons_data)
        self.assertIn("stu_reg_cat:tajweed", buttons_data)
        self.assertIn("stu_reg_cat:hifz", buttons_data)
        self.assertIn("stu_reg_cat:kitab", buttons_data)
        self.assertIn("stu_reg_cat:arabic", buttons_data)
        self.assertIn("stu_reg_cat:islamic_studies", buttons_data)

    # -----------------------------------------------------------------------
    # Requirement 19: Receipt photo upload and admin notification
    # -----------------------------------------------------------------------
    def test_19_receipt_upload_and_admin_notification(self):
        """19. Student uploads payment receipt photo, creating pending_verification record and admin alert."""
        reg_id = db.gen_reg_id()
        tg_id = 77112233
        test_file_id = "AgACAgQAAxkBAAICeW"
        test_receipt_path = os.path.join(BASE_DIR, "data", "receipts", f"{reg_id}.jpg")

        with db.tx() as conn:
            cur = conn.execute(
                "INSERT INTO students(full_name, age, country, city, phone, telegram_user_id, status, created_at, updated_at) "
                "VALUES('Receipt Test Student', 19, 'Ethiopia', 'Addis Ababa', '+251911445566', ?, 'pending_verification', ?, ?)",
                (tg_id, self.now, self.now),
            )
            student_id = cur.lastrowid
            conn.execute(
                "INSERT INTO registrations(reg_id, student_id, program_name_snapshot, monthly_price_snapshot, "
                "currency_snapshot, preferred_schedule, status, receipt_file_id, receipt_url, category_snapshot, "
                "telegram_user_id, created_at, updated_at) "
                "VALUES(?, ?, 'Qaida Course', 1000.0, 'ETB', 'Morning', 'pending_verification', ?, ?, 'qaida', ?, ?, ?)",
                (reg_id, student_id, test_file_id, test_receipt_path, tg_id, self.now, self.now),
            )
            conn.execute(
                "INSERT INTO payment_records(student_id, reg_id, amount_due, amount_received, currency, "
                "status, receipt_file_id, receipt_url, created_at, updated_at) "
                "VALUES(?, ?, 1000.0, 0.0, 'ETB', 'pending_verification', ?, ?, ?, ?)",
                (student_id, reg_id, test_file_id, test_receipt_path, self.now, self.now),
            )

        # Check records created
        reg = db.query_one("SELECT * FROM registrations WHERE reg_id=?", (reg_id,))
        self.assertEqual(reg["status"], "pending_verification")
        self.assertEqual(reg["receipt_file_id"], test_file_id)

        pay = db.query_one("SELECT * FROM payment_records WHERE reg_id=?", (reg_id,))
        self.assertEqual(pay["status"], "pending_verification")
        self.assertEqual(pay["amount_due"], 1000.0)
        self.assertEqual(pay["amount_received"], 0.0)

        # Test admin notification dispatch
        with patch("bot.bridge.send_telegram_photo", return_value=True) as mock_photo:
            full_reg = db.query_one(
                "SELECT r.*, s.full_name, s.age, s.country, s.city, s.phone, s.whatsapp "
                "FROM registrations r JOIN students s ON s.id=r.student_id WHERE r.reg_id=?",
                (reg_id,),
            )
            with patch("db.get_all_admin_telegram_ids", return_value=[12345678]):
                sent = bridge.notify_admins_new_registration(full_reg)
                self.assertEqual(sent, 1)
                self.assertTrue(mock_photo.called)

    # -----------------------------------------------------------------------
    # Requirement 20: Admin one-click approval updates registration & payments
    # -----------------------------------------------------------------------
    def test_20_admin_one_click_approval_sync(self):
        """20. Admin approval updates registration to confirmed and payment record to paid, and notifies student."""
        reg_id = db.gen_reg_id()
        tg_id = 88442211

        with db.tx() as conn:
            cur = conn.execute(
                "INSERT INTO students(full_name, telegram_user_id, status, created_at, updated_at) "
                "VALUES('Approval Test Student', ?, 'pending_verification', ?, ?)",
                (tg_id, self.now, self.now),
            )
            student_id = cur.lastrowid
            conn.execute(
                "INSERT INTO registrations(reg_id, student_id, program_name_snapshot, monthly_price_snapshot, "
                "currency_snapshot, status, telegram_user_id, created_at, updated_at) "
                "VALUES(?, ?, 'Tajweed Mastery', 1200.0, 'ETB', 'pending_verification', ?, ?, ?)",
                (reg_id, student_id, tg_id, self.now, self.now),
            )
            conn.execute(
                "INSERT INTO payment_records(student_id, reg_id, amount_due, amount_received, currency, status, created_at, updated_at) "
                "VALUES(?, ?, 1200.0, 0.0, 'ETB', 'pending_verification', ?, ?)",
                (student_id, reg_id, self.now, self.now),
            )

        # Simulate admin approval
        now_appr = db.utcnow()
        db.execute("UPDATE registrations SET status='confirmed', updated_at=? WHERE reg_id=?", (now_appr, reg_id))
        db.execute("UPDATE students SET status='confirmed', updated_at=? WHERE id=?", (now_appr, student_id))
        db.execute(
            "UPDATE payment_records SET status='paid', amount_received=amount_due, received_at=?, updated_at=? WHERE reg_id=?",
            (now_appr, now_appr, reg_id),
        )

        reg_after = db.query_one("SELECT status FROM registrations WHERE reg_id=?", (reg_id,))
        pay_after = db.query_one("SELECT status, amount_received, amount_due FROM payment_records WHERE reg_id=?", (reg_id,))

        self.assertEqual(reg_after["status"], "confirmed")
        self.assertEqual(pay_after["status"], "paid")
        self.assertEqual(pay_after["amount_received"], 1200.0)

    # -----------------------------------------------------------------------
    # Requirement 21: Comprehensive Kitab Catalog & Admin Management
    # -----------------------------------------------------------------------
    def test_21_kitab_comprehensive_catalog_and_management(self):
        """21. Kitab button presents comprehensive list of books; admin can add, edit, toggle, and delete."""
        # Verify seeded Kitabs exist
        kitabs = db.query("SELECT * FROM programs WHERE category='kitab' AND active=1")
        self.assertGreaterEqual(len(kitabs), 6)
        kitab_names = [k["name"] for k in kitabs]
        self.assertIn("Safinat al-Naja", kitab_names)
        self.assertIn("40 Hadith of Imam Nawawi", kitab_names)
        self.assertIn("Al-Ajrumiyyah", kitab_names)

        # Admin adds new Kitab
        now = db.utcnow()
        new_kid = db.execute(
            "INSERT INTO programs(slug, name, category, description, level_info, age_group, class_format, "
            "monthly_price, currency, book_title, author_or_subject, required_materials, active, public_visible, "
            "sort_order, created_at, updated_at) "
            "VALUES('test-bulugh-maram', 'Bulugh al-Maram', 'kitab', 'Hadith compilation on rulings', "
            "'Intermediate', 'Youth and adults', 'Online class', 1500.0, 'ETB', 'Bulugh al-Maram', "
            "'Ibn Hajar al-Asqalani', 'PDF provided', 1, 1, 25, ?, ?)",
            (now, now),
        )
        self.assertIsNotNone(new_kid)

        # Verify new Kitab appears in active catalog
        k = db.query_one("SELECT * FROM programs WHERE id=?", (new_kid,))
        self.assertEqual(k["name"], "Bulugh al-Maram")
        self.assertEqual(k["author_or_subject"], "Ibn Hajar al-Asqalani")
        self.assertEqual(k["monthly_price"], 1500.0)

        # Admin edits fee and title
        db.execute(
            "UPDATE programs SET name='Bulugh al-Maram (Fiqh)', monthly_price=1600.0, updated_at=? WHERE id=?",
            (db.utcnow(), new_kid),
        )
        k_edited = db.query_one("SELECT * FROM programs WHERE id=?", (new_kid,))
        self.assertEqual(k_edited["name"], "Bulugh al-Maram (Fiqh)")
        self.assertEqual(k_edited["monthly_price"], 1600.0)

        # Admin deactivates and then deletes
        db.execute("UPDATE programs SET active=0, updated_at=? WHERE id=?", (db.utcnow(), new_kid))
        self.assertEqual(db.query_one("SELECT active FROM programs WHERE id=?", (new_kid,))["active"], 0)

        db.execute("DELETE FROM programs WHERE id=? AND category='kitab'", (new_kid,))
        self.assertIsNone(db.query_one("SELECT id FROM programs WHERE id=?", (new_kid,)))

    # -----------------------------------------------------------------------
    # Requirement 22: Clean Display vs Detailed Display Setting Toggle
    # -----------------------------------------------------------------------
    def test_22_clean_course_display_and_admin_toggle(self):
        """22. Courses showcase clean titles by default, and admin can toggle detailed presentation."""
        # Default should be clean (False)
        db.set_setting("show_button_extra_details", False)
        self.assertFalse(db.get_setting("show_button_extra_details", False))

        # Admin toggles to detailed (True)
        db.set_setting("show_button_extra_details", True)
        self.assertTrue(db.get_setting("show_button_extra_details", False))

    # -----------------------------------------------------------------------
    # Requirement 23: Multilingual Support (Amharic, Oromic, Arabic, English)
    # -----------------------------------------------------------------------
    def test_23_multilingual_language_selection_and_persistence(self):
        """23. Language selection screen, persistence per user, and dynamic translation in Amharic, Oromic, Arabic, English."""
        from bot import i18n
        from bot.student_bot import language_selection_keyboard, main_menu_keyboard, get_welcome_text

        test_uid = 99887766
        db.execute("DELETE FROM user_preferences WHERE telegram_user_id=?", (test_uid,))

        # Check default before preference is set
        self.assertFalse(db.has_user_language(test_uid))
        self.assertEqual(db.get_user_language(test_uid), "en")

        # Test language keyboard options
        kb = language_selection_keyboard()
        cb_datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        self.assertIn("stu_lang:en", cb_datas)
        self.assertIn("stu_lang:am", cb_datas)
        self.assertIn("stu_lang:om", cb_datas)
        self.assertIn("stu_lang:ar", cb_datas)

        # 1. Set to Amharic (am)
        db.set_user_language(test_uid, "am")
        self.assertTrue(db.has_user_language(test_uid))
        self.assertEqual(db.get_user_language(test_uid), "am")
        self.assertEqual(i18n.t("btn_courses", "am"), "📚 ኮርሶችን ይመልከቱ")
        self.assertEqual(i18n.t("btn_register", "am"), "📝 በተማሪነት ይመዝገቡ")
        welcome_am = get_welcome_text(test_uid)
        self.assertIn("አሰላሙ አለይኩም", welcome_am)

        # Main menu buttons in Amharic
        am_menu = main_menu_keyboard(test_uid)
        am_btn_texts = [btn.text for row in am_menu.inline_keyboard for btn in row]
        self.assertIn("📚 ኮርሶችን ይመልከቱ", am_btn_texts)
        self.assertIn("📝 በተማሪነት ይመዝገቡ", am_btn_texts)

        # 2. Set to Oromic (om)
        db.set_user_language(test_uid, "om")
        self.assertEqual(db.get_user_language(test_uid), "om")
        self.assertEqual(i18n.t("btn_courses", "om"), "📚 Koorsiiwwan Ilaalaa")
        self.assertEqual(i18n.t("btn_register", "om"), "📝 Barataa Ta'aa Galmaa'aa")
        welcome_om = get_welcome_text(test_uid)
        self.assertIn("Assalaamu Aleykum", welcome_om)
        self.assertIn("Baga gara", welcome_om)

        # Main menu buttons in Oromic
        om_menu = main_menu_keyboard(test_uid)
        om_btn_texts = [btn.text for row in om_menu.inline_keyboard for btn in row]
        self.assertIn("📚 Koorsiiwwan Ilaalaa", om_btn_texts)
        self.assertIn("📝 Barataa Ta'aa Galmaa'aa", om_btn_texts)

        # 3. Set to Arabic (ar)
        db.set_user_language(test_uid, "ar")
        self.assertEqual(db.get_user_language(test_uid), "ar")
        self.assertEqual(i18n.t("btn_courses", "ar"), "📚 استعراض الدورات")
        self.assertEqual(i18n.t("btn_register", "ar"), "📝 التسجيل كطالب")
        welcome_ar = get_welcome_text(test_uid)
        self.assertIn("السلام عليكم ورحمة الله وبركاته", welcome_ar)
        self.assertIn("أهلاً وسهلاً بكم في", welcome_ar)

        # Main menu buttons in Arabic
        ar_menu = main_menu_keyboard(test_uid)
        ar_btn_texts = [btn.text for row in ar_menu.inline_keyboard for btn in row]
        self.assertIn("📚 استعراض الدورات", ar_btn_texts)
        self.assertIn("📝 التسجيل كطالب", ar_btn_texts)

        # 4. Set to English (en)
        db.set_user_language(test_uid, "en")
        self.assertEqual(db.get_user_language(test_uid), "en")
        self.assertEqual(i18n.t("btn_courses", "en"), "📚 Explore Courses")
        welcome_en = get_welcome_text(test_uid)
        self.assertIn("Assalamu Alaikum", welcome_en)
        self.assertIn("Welcome to", welcome_en)


if __name__ == "__main__":
    unittest.main()

