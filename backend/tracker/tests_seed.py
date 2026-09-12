"""Tests for `manage.py seed_demo` -- the command that makes "works out of
the box" true. Run as part of the normal suite:

    DB_ENGINE=sqlite py manage.py test
"""

import datetime

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import Dose, Note, UserMedication
from .services import classify_dose


class SeedDemoTests(TestCase):

    def setUp(self):
        call_command("seed_demo")

    def test_creates_both_demo_accounts(self):
        self.assertTrue(User.objects.filter(username="admin", is_superuser=True).exists())
        self.assertTrue(User.objects.filter(username="dev1").exists())

    def test_the_documented_passwords_work(self):
        self.assertTrue(self.client.login(username="admin", password="password"))
        self.assertTrue(self.client.login(username="dev1", password="firstpassword"))

    def test_accounts_are_on_the_documented_medications(self):
        admin = UserMedication.objects.get(user__username="admin")
        self.assertEqual(admin.medication_id, "vyvanse")
        self.assertEqual(admin.scheduled_time, datetime.time(8, 0))

        dev1 = UserMedication.objects.get(user__username="dev1")
        self.assertEqual(dev1.medication_id, "dexamf")
        self.assertEqual(dev1.scheduled_time, datetime.time(7, 30))

    def test_running_twice_does_not_duplicate_anything(self):
        before = (
            User.objects.count(), Dose.objects.count(), Note.objects.count(),
            UserMedication.objects.count(),
        )
        call_command("seed_demo")
        after = (
            User.objects.count(), Dose.objects.count(), Note.objects.count(),
            UserMedication.objects.count(),
        )
        self.assertEqual(before, after)

    def test_each_account_has_nine_doses_in_a_ten_day_window_including_today(self):
        today = timezone.localdate()
        oldest = today - datetime.timedelta(days=9)
        # The one missed day in each account's window has no row at all.
        for username, gap_days_ago in (("admin", 4), ("dev1", 3)):
            with self.subTest(user=username):
                doses = Dose.objects.filter(user__username=username)
                self.assertEqual(doses.count(), 9)

                dates = set(doses.values_list("date", flat=True))
                self.assertEqual(len(dates), 9)  # one row per date, no duplicates
                self.assertIn(today, dates)
                self.assertTrue(all(oldest <= d <= today for d in dates))
                self.assertNotIn(today - datetime.timedelta(days=gap_days_ago), dates)

    def test_todays_dose_is_never_in_the_future(self):
        for username in ("admin", "dev1"):
            with self.subTest(user=username):
                dose = Dose.objects.get(user__username=username, date=timezone.localdate())
                self.assertLessEqual(dose.taken_at, timezone.now())

    def test_every_doses_status_matches_classify_dose(self):
        for username in ("admin", "dev1"):
            selection = UserMedication.objects.get(user__username=username)
            for dose in Dose.objects.filter(user__username=username):
                expected = classify_dose(selection.scheduled_time, dose.taken_at)
                with self.subTest(user=username, date=dose.date):
                    self.assertEqual(dose.status, expected)

    def test_the_history_is_a_mix_of_on_time_and_late(self):
        # A run of identical statuses would leave the History page and the
        # adherence percentage with nothing to show.
        for username in ("admin", "dev1"):
            with self.subTest(user=username):
                statuses = set(
                    Dose.objects.filter(user__username=username)
                    .values_list("status", flat=True)
                )
                self.assertIn(Dose.Status.ON_TIME, statuses)
                self.assertIn(Dose.Status.LATE, statuses)

    def test_notes_include_flagged_ones(self):
        for username, total in (("admin", 7), ("dev1", 4)):
            with self.subTest(user=username):
                notes = Note.objects.filter(user__username=username)
                self.assertEqual(notes.count(), total)
                self.assertEqual(notes.filter(flagged=True).count(), 2)

    def test_reset_regenerates_after_a_manual_change(self):
        admin = User.objects.get(username="admin")
        Note.objects.create(user=admin, text="an extra note a marker typed in")
        self.assertEqual(Note.objects.filter(user=admin).count(), 8)

        call_command("seed_demo", reset=True)

        admin = User.objects.get(username="admin")  # --reset recreates the row
        self.assertEqual(Note.objects.filter(user=admin).count(), 7)

    def test_reset_does_not_touch_a_non_demo_user(self):
        marker = User.objects.create_user(username="marker", password="not-a-demo-account")
        call_command("seed_demo", reset=True)
        self.assertTrue(User.objects.filter(pk=marker.pk).exists())
