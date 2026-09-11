"""Tests for the tracker API under /api/.

Most tests here patch tracker.views.compute_timeline/compute_adherence, so
what they check is the payload this app *builds* from the database --
today's dose, the medication's components, the day-by-day adherence
window -- independent of the curve/adherence maths itself. That maths is
pk (backend/pk/), a plain Python package called in-process rather than a
separate service; its own tests live in backend/pk/tests. TimelineEndToEndTests
below calls the real pk module with no mocking, absorbing the cases that
used to live in pk's own endpoint tests back when pk was an HTTP service.

Run from backend/ with:

    DB_ENGINE=sqlite py manage.py test

No VMs and no postgres required.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import Dose, Medication, Note, UserMedication

COMPONENTS = [{"fraction": 1.0, "delay_h": 0.0, "ka": 1.2, "half_life_h": 3.5}]


class ApiTestCase(TestCase):
    """A signed-in user with an active medication, which most endpoints need."""

    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="correct-horse-9")
        self.other = User.objects.create_user(username="bob", password="correct-horse-9")
        self.medication = Medication.objects.create(
            id="methylphenidate-ir", name="Methylphenidate IR", pk_components=COMPONENTS,
        )
        self.client.force_login(self.user)

    def select(self, medication=None, scheduled_time=datetime.time(8, 0), user=None):
        return UserMedication.objects.create(
            user=user or self.user,
            medication=medication or self.medication,
            is_active=True,
            scheduled_time=scheduled_time,
        )


class AuthenticationTests(ApiTestCase):
    """Every tracker endpoint is per-user data and must refuse anonymous callers."""

    def test_all_endpoints_require_authentication(self):
        self.client.logout()
        for path in ("/api/medications/", "/api/my-medication/", "/api/doses/",
                     "/api/notes/", "/api/timeline/", "/api/adherence/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)


class MedicationTests(ApiTestCase):

    def test_medications_lists_the_catalogue(self):
        # Migration 0002 seeds the real catalogue, so this is the seeded rows
        # plus the one this test case adds -- assert on membership and shape
        # rather than pinning the seed list.
        response = self.client.get("/api/medications/")
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(len(body), Medication.objects.count())
        row = next(r for r in body if r["id"] == "methylphenidate-ir")
        self.assertEqual(row["name"], "Methylphenidate IR")
        for row in body:
            self.assertEqual(
                set(row),
                {"id", "name", "blurb", "description", "drug_class",
                 "source", "source_url", "retrieved"},
            )

    def test_catalogue_carries_the_copy_the_medications_page_renders(self):
        # The page used to read this text from the frontend's
        # placeholderData.js; migration 0007 moved it here, so it has to
        # actually come back on the wire.
        body = self.client.get("/api/medications/").json()
        concerta = next(r for r in body if r["id"] == "concerta")
        self.assertTrue(concerta["blurb"])
        self.assertTrue(concerta["description"])
        self.assertEqual(concerta["drug_class"], "methylphenidate-class stimulant")
        # Not every stimulant in the catalogue is a methylphenidate one --
        # the design mock said so for all five, which was wrong.
        vyvanse = next(r for r in body if r["id"] == "vyvanse")
        self.assertIn("amfetamine", vyvanse["drug_class"])

    def test_catalogue_provenance_is_still_blank_and_says_so(self):
        # Deliberate: nothing has been checked against Medsafe or the NZ
        # Formulary yet (TODO.md section 3), and the page shows "no source
        # recorded yet" rather than a plausible-looking citation. If this
        # test starts failing because the fields were filled in, that is the
        # good outcome -- update it then.
        for row in self.client.get("/api/medications/").json():
            self.assertEqual(row["source"], "")
            self.assertEqual(row["source_url"], "")
            self.assertIsNone(row["retrieved"])

    def test_my_medication_is_null_before_one_is_chosen(self):
        response = self.client.get("/api/my-medication/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["medication"])

    def test_selecting_a_medication_makes_it_active(self):
        response = self.client.post(
            "/api/my-medication/", {"medication": "methylphenidate-ir"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["medication"]["id"], "methylphenidate-ir")
        self.assertEqual(
            UserMedication.objects.filter(user=self.user, is_active=True).count(), 1
        )

    def test_selecting_a_second_medication_deactivates_the_first(self):
        # The model has a unique-active-per-user constraint, so the old
        # selection has to be stood down rather than left alongside.
        other = Medication.objects.create(id="lisdexamfetamine", name="Lisdexamfetamine")
        self.client.post("/api/my-medication/", {"medication": "methylphenidate-ir"},
                         content_type="application/json")
        self.client.post("/api/my-medication/", {"medication": other.id},
                         content_type="application/json")

        active = UserMedication.objects.filter(user=self.user, is_active=True)
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().medication_id, "lisdexamfetamine")
        self.assertEqual(UserMedication.objects.filter(user=self.user).count(), 2)

    def test_unknown_medication_is_404(self):
        response = self.client.post("/api/my-medication/", {"medication": "nope"},
                                    content_type="application/json")
        self.assertEqual(response.status_code, 404)

    def test_my_medication_does_not_leak_another_users_selection(self):
        self.select(user=self.other)
        self.assertIsNone(self.client.get("/api/my-medication/").json()["medication"])


class ScheduledTimeTests(ApiTestCase):
    """The daily time pk compares each dose against.

    It defaulted everyone to 8am with no way to change it, which made
    on-time/late wrong for anyone not on an 8am dose.
    """

    def _post(self, **payload):
        return self.client.post("/api/my-medication/", payload,
                                content_type="application/json")

    def test_scheduled_time_comes_back_with_the_selection(self):
        self.select(scheduled_time=datetime.time(7, 30))
        self.assertEqual(
            self.client.get("/api/my-medication/").json()["scheduled_time"], "07:30"
        )

    def test_scheduled_time_is_null_before_a_medication_is_chosen(self):
        self.assertIsNone(self.client.get("/api/my-medication/").json()["scheduled_time"])

    def test_time_alone_updates_the_current_selection_in_place(self):
        selection = self.select()
        response = self._post(scheduled_time="14:45")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["scheduled_time"], "14:45")
        selection.refresh_from_db()
        self.assertEqual(selection.scheduled_time, datetime.time(14, 45))
        # No churn: the same row, not a replacement selection.
        self.assertEqual(UserMedication.objects.filter(user=self.user).count(), 1)

    def test_medication_and_time_can_be_set_together(self):
        response = self._post(medication="methylphenidate-ir", scheduled_time="09:15")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["medication"]["id"], "methylphenidate-ir")
        self.assertEqual(response.json()["scheduled_time"], "09:15")

    def test_switching_medication_keeps_the_time_already_set(self):
        self.select(scheduled_time=datetime.time(6, 5))
        other = Medication.objects.create(id="lisdexamfetamine", name="Lisdexamfetamine")
        response = self._post(medication=other.id)
        self.assertEqual(response.json()["scheduled_time"], "06:05")

    def test_a_time_with_no_selection_yet_is_400(self):
        response = self._post(scheduled_time="09:00")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.assertEqual(UserMedication.objects.count(), 0)

    def test_an_unparseable_time_is_400_and_changes_nothing(self):
        selection = self.select()
        for bad in ("half nine", "25:00", 900):
            with self.subTest(bad=bad):
                response = self._post(scheduled_time=bad)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json())
        selection.refresh_from_db()
        self.assertEqual(selection.scheduled_time, datetime.time(8, 0))

    def test_the_scheduled_time_is_what_adherence_sends_pk(self):
        # The whole point of the picker: pk classifies against this value.
        self.select(scheduled_time=datetime.time(12, 30))
        with patch("tracker.views.compute_adherence", return_value={"days": []}) as pk:
            self.client.get("/api/adherence/", {"days": 1})
        sent = pk.call_args.args[0]
        self.assertEqual(sent[0]["scheduled"], "12:30")


class DoseLoggingTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.select()

    def test_logging_a_dose_uses_the_active_medication(self):
        # select()'s default schedule is 08:00; an explicit on-time taken_at
        # keeps this test's expected status independent of what time of day
        # it actually runs (classify_dose now decides that for real).
        taken_at = timezone.make_aware(
            datetime.datetime.combine(timezone.localdate(), datetime.time(8, 5))
        )
        response = self.client.post(
            "/api/doses/", {"taken_at": taken_at.isoformat()}, content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

        body = response.json()
        self.assertEqual(body["medication"], "methylphenidate-ir")
        self.assertEqual(body["medication_name"], "Methylphenidate IR")
        self.assertEqual(body["status"], Dose.Status.ON_TIME)
        self.assertEqual(body["date"], timezone.localdate().isoformat())
        self.assertIsNotNone(body["taken_at"])

    def test_logging_late_is_classified_late(self):
        # 60 minutes past the 08:00 schedule, comfortably past pk's
        # 30-minute LATE_AFTER_MINUTES threshold.
        taken_at = timezone.make_aware(
            datetime.datetime.combine(timezone.localdate(), datetime.time(9, 0))
        )
        response = self.client.post(
            "/api/doses/", {"taken_at": taken_at.isoformat()}, content_type="application/json",
        )
        self.assertEqual(response.json()["status"], "late")

    def test_doses_and_adherence_agree_on_the_same_dose(self):
        # The exact scenario TODO.md section 3 flagged: a dose logged at
        # 09:55 against an 08:00 schedule used to come back "on-time" from
        # POST /doses/ while /adherence/ classified it "late". Both now go
        # through pk.model.classify, so they can no longer disagree.
        taken_at = timezone.make_aware(
            datetime.datetime.combine(timezone.localdate(), datetime.time(9, 55))
        )
        dose_status = self.client.post(
            "/api/doses/", {"taken_at": taken_at.isoformat()}, content_type="application/json",
        ).json()["status"]

        adherence = self.client.get("/api/adherence/", {"days": 1}).json()
        today = timezone.localdate().isoformat()
        adherence_status = next(day["status"] for day in adherence["days"] if day["date"] == today)

        self.assertEqual(dose_status, "late")
        self.assertEqual(dose_status, adherence_status)

    def test_logging_without_an_active_medication_is_400(self):
        UserMedication.objects.all().delete()
        response = self.client.post("/api/doses/", {}, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.assertEqual(Dose.objects.count(), 0)

    def test_relogging_the_same_day_edits_rather_than_duplicates(self):
        self.client.post("/api/doses/", {}, content_type="application/json")
        taken_at = timezone.now().replace(microsecond=0)
        response = self.client.post(
            "/api/doses/", {"taken_at": taken_at.isoformat()},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], Dose.Status.EDITED)
        self.assertEqual(Dose.objects.filter(user=self.user).count(), 1)

    def test_explicit_taken_at_is_stored(self):
        taken_at = timezone.now().replace(microsecond=0)
        self.client.post("/api/doses/", {"taken_at": taken_at.isoformat()},
                         content_type="application/json")
        self.assertEqual(Dose.objects.get(user=self.user).taken_at, taken_at)

    def test_delete_clears_only_todays_dose(self):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        Dose.objects.create(user=self.user, medication=self.medication,
                            date=yesterday, taken_at=timezone.now())
        self.client.post("/api/doses/", {}, content_type="application/json")

        response = self.client.delete("/api/doses/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Dose.objects.filter(user=self.user, date=timezone.localdate()).exists())
        self.assertTrue(Dose.objects.filter(user=self.user, date=yesterday).exists())

    def test_delete_does_not_touch_another_users_doses(self):
        Dose.objects.create(user=self.other, medication=self.medication,
                            date=timezone.localdate(), taken_at=timezone.now())
        self.client.delete("/api/doses/")
        self.assertTrue(Dose.objects.filter(user=self.other).exists())


class DoseListingTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.select()
        self.today = timezone.localdate()

    def _dose(self, days_ago, user=None):
        return Dose.objects.create(
            user=user or self.user, medication=self.medication,
            date=self.today - datetime.timedelta(days=days_ago), taken_at=timezone.now(),
        )

    def test_default_listing_covers_the_last_fourteen_days(self):
        self._dose(0)
        self._dose(13)
        self._dose(14)  # just outside the window
        dates = {row["date"] for row in self.client.get("/api/doses/").json()}
        self.assertEqual(len(dates), 2)
        self.assertNotIn((self.today - datetime.timedelta(days=14)).isoformat(), dates)

    def test_date_today_narrows_to_today(self):
        self._dose(0)
        self._dose(1)
        body = self.client.get("/api/doses/", {"date": "today"}).json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["date"], self.today.isoformat())

    def test_listing_excludes_other_users_doses(self):
        self._dose(0, user=self.other)
        self.assertEqual(self.client.get("/api/doses/").json(), [])


class TimelineTests(ApiTestCase):

    PK_RESULT = {"events": [{"label": "peak", "t_h": 1.5}], "model_version": "1.0"}

    def test_timeline_forwards_todays_dose_and_the_medications_components(self):
        self.select()
        taken_at = timezone.now().replace(microsecond=0)
        Dose.objects.create(user=self.user, medication=self.medication,
                            date=timezone.localdate(), taken_at=taken_at)

        with patch("tracker.views.compute_timeline", return_value=self.PK_RESULT) as pk:
            response = self.client.get("/api/timeline/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.PK_RESULT)
        # The view converts to local time before calling compute_timeline, so
        # this compares as an aware datetime (equal by instant) rather than
        # the UTC-offset isoformat() string taken_at itself would produce.
        pk.assert_called_once_with(timezone.localtime(taken_at), COMPONENTS)

    def test_explicit_taken_at_overrides_the_logged_dose(self):
        self.select()
        with patch("tracker.views.compute_timeline", return_value=self.PK_RESULT) as pk:
            self.client.get("/api/timeline/", {"taken_at": "2026-09-10T08:00:00+12:00"})
        pk.assert_called_once_with("2026-09-10T08:00:00+12:00", COMPONENTS)

    def test_no_active_medication_is_400_without_calling_pk(self):
        with patch("tracker.views.compute_timeline") as pk:
            response = self.client.get("/api/timeline/")
        self.assertEqual(response.status_code, 400)
        pk.assert_not_called()

    def test_no_dose_logged_today_is_400_without_calling_pk(self):
        self.select()
        with patch("tracker.views.compute_timeline") as pk:
            response = self.client.get("/api/timeline/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        pk.assert_not_called()

    def test_medication_query_param_previews_another_medication(self):
        # What the Medications page draws its curve preview with: a
        # medication the user has not selected, at a time of the caller's
        # choosing, without needing a logged dose.
        other = Medication.objects.create(
            id="lisdexamfetamine", name="Lisdexamfetamine",
            pk_components=[{"fraction": 1.0, "delay_h": 0.0, "ka": 0.4, "half_life_h": 6.0}],
        )
        self.select()

        with patch("tracker.views.compute_timeline", return_value=self.PK_RESULT) as pk:
            response = self.client.get("/api/timeline/", {
                "medication": other.id, "taken_at": "2026-09-10T08:00:00+12:00",
            })

        self.assertEqual(response.status_code, 200)
        pk.assert_called_once_with("2026-09-10T08:00:00+12:00", other.pk_components)

    def test_previewing_needs_no_active_medication(self):
        with patch("tracker.views.compute_timeline", return_value=self.PK_RESULT) as pk:
            response = self.client.get("/api/timeline/", {
                "medication": self.medication.id, "taken_at": "2026-09-10T08:00:00+12:00",
            })
        self.assertEqual(response.status_code, 200)
        pk.assert_called_once_with("2026-09-10T08:00:00+12:00", COMPONENTS)

    def test_unknown_medication_query_param_is_404_without_calling_pk(self):
        self.select()
        with patch("tracker.views.compute_timeline") as pk:
            response = self.client.get("/api/timeline/", {"medication": "nope"})
        self.assertEqual(response.status_code, 404)
        pk.assert_not_called()

    def test_medication_without_components_is_400_without_calling_pk(self):
        bare = Medication.objects.create(id="unknown-med", name="Unknown", pk_components=[])
        self.select(medication=bare)
        Dose.objects.create(user=self.user, medication=bare,
                            date=timezone.localdate(), taken_at=timezone.now())
        with patch("tracker.views.compute_timeline") as pk:
            response = self.client.get("/api/timeline/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown", response.json()["error"])
        pk.assert_not_called()


class AdherencePayloadTests(ApiTestCase):
    """web's job here is assembling the day-by-day payload; pk classifies it."""

    def _adherence(self, **params):
        with patch("tracker.views.compute_adherence", return_value={"adherence": 1.0}) as pk:
            response = self.client.get("/api/adherence/", params)
        return response, pk

    def test_payload_covers_the_whole_window_newest_first(self):
        self.select()
        response, pk = self._adherence(days=3)
        self.assertEqual(response.status_code, 200)

        doses = pk.call_args.args[0]
        today = timezone.localdate()
        self.assertEqual(
            [row["date"] for row in doses],
            [(today - datetime.timedelta(days=n)).isoformat() for n in range(3)],
        )

    def test_days_with_no_dose_row_are_sent_as_missed(self):
        # Nothing is stored for a missed day, so the view has to synthesize a
        # taken_at of None or pk would never see the day at all.
        self.select()
        _, pk = self._adherence(days=2)
        self.assertEqual([row["taken_at"] for row in pk.call_args.args[0]], [None, None])

    def test_logged_doses_are_sent_as_local_clock_times(self):
        self.select()
        taken_at = timezone.make_aware(
            datetime.datetime.combine(timezone.localdate(), datetime.time(8, 42))
        )
        Dose.objects.create(user=self.user, medication=self.medication,
                            date=timezone.localdate(), taken_at=taken_at)
        _, pk = self._adherence(days=1)
        self.assertEqual(pk.call_args.args[0][0]["taken_at"], "08:42")

    def test_scheduled_time_comes_from_the_user_medication(self):
        self.select(scheduled_time=datetime.time(14, 30))
        _, pk = self._adherence(days=1)
        self.assertEqual(pk.call_args.args[0][0]["scheduled"], "14:30")

    def test_days_defaults_to_fourteen(self):
        self.select()
        _, pk = self._adherence()
        self.assertEqual(len(pk.call_args.args[0]), 14)

    def test_days_is_clamped_to_at_least_one(self):
        self.select()
        _, pk = self._adherence(days=0)
        self.assertEqual(len(pk.call_args.args[0]), 1)

    def test_non_integer_days_is_400(self):
        self.select()
        with patch("tracker.views.compute_adherence") as pk:
            response = self.client.get("/api/adherence/", {"days": "many"})
        self.assertEqual(response.status_code, 400)
        pk.assert_not_called()

    def test_no_active_medication_is_400(self):
        with patch("tracker.views.compute_adherence") as pk:
            response = self.client.get("/api/adherence/")
        self.assertEqual(response.status_code, 400)
        pk.assert_not_called()

    def test_another_users_doses_are_not_included(self):
        self.select()
        Dose.objects.create(user=self.other, medication=self.medication,
                            date=timezone.localdate(), taken_at=timezone.now())
        _, pk = self._adherence(days=1)
        self.assertIsNone(pk.call_args.args[0][0]["taken_at"])



class TimelineEndToEndTests(ApiTestCase):
    """/api/timeline/ against the real pk module -- nothing mocked.

    Absorbed from pk's own endpoint tests, back when pk was a separate HTTP
    service with its own Django test client hitting /timeline directly.
    These now go through the real tracker -> pk call the app actually makes,
    via the ?medication=/&taken_at= preview path so no Dose row is needed.
    """

    def _timeline(self, components, taken_at="2026-09-06T08:00:00+12:00"):
        medication = Medication.objects.create(
            id="preview-med", name="Preview", pk_components=components,
        )
        return self.client.get(
            "/api/timeline/", {"medication": medication.id, "taken_at": taken_at},
        )

    def test_events_are_chronological_and_carry_input_offset(self):
        response = self._timeline([
            {"fraction": 0.22, "delay_h": 0.0, "ka": 1.00, "ke": 0.277},
            {"fraction": 0.78, "delay_h": 3.0, "ka": 0.50, "ke": 0.277},
        ])
        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["computed_by"], "backend.pk")
        self.assertEqual(body["taken_at"], "2026-09-06T08:00:00+12:00")

        events = body["events"]
        self.assertGreater(len(events), 0)
        timestamps = [event["at"] for event in events]
        self.assertEqual(timestamps, sorted(timestamps))
        for event in events:
            self.assertTrue(event["at"].endswith("+12:00"))

        labels = [event["label"] for event in events]
        self.assertEqual(labels[0], "Taken")
        self.assertIn("Second release", labels)

    def test_negative_offset_is_preserved(self):
        response = self._timeline(
            [{"fraction": 1.0, "delay_h": 0.0, "ka": 1.0, "ke": 0.277}],
            taken_at="2026-09-06T08:00:00-05:00",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["taken_at"].endswith("-05:00"))
        for event in body["events"]:
            self.assertTrue(event["at"].endswith("-05:00"))

    def test_single_component_medication_has_no_second_release_event(self):
        response = self._timeline([{"fraction": 1.0, "delay_h": 0.0, "ka": 1.0, "ke": 0.277}])
        self.assertEqual(response.status_code, 200)
        labels = [event["label"] for event in response.json()["events"]]
        self.assertNotIn("Second release", labels)

    def test_missing_timezone_offset_is_400(self):
        response = self._timeline(
            [{"fraction": 1.0, "delay_h": 0.0, "ka": 1.0, "ke": 0.277}],
            taken_at="2026-09-06T08:00:00",
        )
        self.assertEqual(response.status_code, 400)

    def test_negative_rate_constant_is_400(self):
        response = self._timeline([{"fraction": 1.0, "delay_h": 0.0, "ka": -1.0, "ke": 0.277}])
        self.assertEqual(response.status_code, 400)

    def test_zero_rate_constant_is_400(self):
        response = self._timeline([{"fraction": 1.0, "delay_h": 0.0, "ka": 1.0, "ke": 0.0}])
        self.assertEqual(response.status_code, 400)

    def test_non_numeric_parameter_is_400(self):
        response = self._timeline([{"fraction": 1.0, "delay_h": 0.0, "ka": "fast", "ke": 0.277}])
        self.assertEqual(response.status_code, 400)


class NoteTests(ApiTestCase):

    def test_creating_a_note_defaults_to_today_and_unflagged(self):
        response = self.client.post("/api/notes/", {"text": "Felt focused by 9."},
                                    content_type="application/json")
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["text"], "Felt focused by 9.")
        self.assertEqual(body["date"], timezone.localdate().isoformat())
        self.assertFalse(body["flagged"])

    def test_date_and_flagged_can_be_set_explicitly(self):
        response = self.client.post(
            "/api/notes/", {"text": "Headache.", "date": "2026-09-01", "flagged": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["date"], "2026-09-01")
        self.assertTrue(response.json()["flagged"])

    def test_empty_text_is_rejected(self):
        response = self.client.post("/api/notes/", {"text": ""},
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Note.objects.count(), 0)

    def test_listing_returns_the_users_notes_newest_day_first(self):
        Note.objects.create(user=self.user, text="older", date=datetime.date(2026, 9, 1))
        Note.objects.create(user=self.user, text="newer", date=datetime.date(2026, 9, 5))
        self.assertEqual(
            [note["text"] for note in self.client.get("/api/notes/").json()],
            ["newer", "older"],
        )

    def test_listing_excludes_other_users_notes(self):
        Note.objects.create(user=self.other, text="not mine")
        self.assertEqual(self.client.get("/api/notes/").json(), [])

    def test_date_filter_narrows_to_one_day(self):
        Note.objects.create(user=self.user, text="on the day", date=datetime.date(2026, 9, 1))
        Note.objects.create(user=self.user, text="another day", date=datetime.date(2026, 9, 5))
        body = self.client.get("/api/notes/", {"date": "2026-09-01"}).json()
        self.assertEqual([note["text"] for note in body], ["on the day"])

    def test_date_today_narrows_to_today(self):
        Note.objects.create(user=self.user, text="today")
        Note.objects.create(user=self.user, text="last week",
                            date=timezone.localdate() - datetime.timedelta(days=7))
        body = self.client.get("/api/notes/", {"date": "today"}).json()
        self.assertEqual([note["text"] for note in body], ["today"])

    def test_unparseable_date_is_400(self):
        for value in ("yesterday", "2026-02-30", "10/09/2026"):
            with self.subTest(date=value):
                response = self.client.get("/api/notes/", {"date": value})
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json())
