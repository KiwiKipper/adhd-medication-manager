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

    def test_creates_the_three_demo_accounts(self):
        self.assertTrue(User.objects.filter(username="ada").exists())
        self.assertTrue(User.objects.filter(username="sam").exists())
        self.assertTrue(User.objects.filter(username="admin", is_superuser=True).exists())

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

    def test_ada_has_nine_dose_rows_across_ten_distinct_dates_including_today(self):
        ada = User.objects.get(username="ada")
        doses = Dose.objects.filter(user=ada)
        self.assertEqual(doses.count(), 9)

        dates = set(doses.values_list("date", flat=True))
        self.assertEqual(len(dates), 9)  # one row per date, no duplicates
        today = timezone.localdate()
        self.assertIn(today, dates)
        oldest = today - datetime.timedelta(days=9)
        self.assertTrue(all(oldest <= d <= today for d in dates))
        # The one gap in ada's ten-day window (days_ago=4) has no row at all.
        self.assertNotIn(today - datetime.timedelta(days=4), dates)

    def test_todays_dose_for_ada_is_not_in_the_future(self):
        ada = User.objects.get(username="ada")
        today_dose = Dose.objects.get(user=ada, date=timezone.localdate())
        self.assertLessEqual(today_dose.taken_at, timezone.now())

    def test_sam_has_no_dose_logged_today(self):
        sam = User.objects.get(username="sam")
        self.assertFalse(Dose.objects.filter(user=sam, date=timezone.localdate()).exists())
        self.assertEqual(Dose.objects.filter(user=sam).count(), 8)

    def test_every_doses_status_matches_classify_dose(self):
        for user in ("ada", "sam"):
            selection = UserMedication.objects.get(user__username=user)
            for dose in Dose.objects.filter(user__username=user):
                expected = classify_dose(selection.scheduled_time, dose.taken_at)
                with self.subTest(user=user, date=dose.date):
                    self.assertEqual(dose.status, expected)

    def test_ada_has_two_flagged_notes_among_eight(self):
        ada = User.objects.get(username="ada")
        notes = Note.objects.filter(user=ada)
        self.assertEqual(notes.count(), 8)
        self.assertEqual(notes.filter(flagged=True).count(), 2)

    def test_sam_has_three_notes(self):
        sam = User.objects.get(username="sam")
        self.assertEqual(Note.objects.filter(user=sam).count(), 3)

    def test_reset_regenerates_after_a_manual_change(self):
        ada = User.objects.get(username="ada")
        Note.objects.create(user=ada, text="an extra note a marker typed in")
        self.assertEqual(Note.objects.filter(user=ada).count(), 9)

        call_command("seed_demo", reset=True)

        ada = User.objects.get(username="ada")  # re-fetch: --reset recreates the row
        self.assertEqual(Note.objects.filter(user=ada).count(), 8)

    def test_reset_does_not_touch_a_non_demo_user(self):
        marker = User.objects.create_user(username="marker", password="not-a-demo-account")
        call_command("seed_demo", reset=True)
        self.assertTrue(User.objects.filter(pk=marker.pk).exists())
