"""Endpoint tests, via the Django test client. No real VM, no real network --
Django's test client calls the view functions in-process.

Run with:

    py manage.py test tests

(from the pk/ directory, with Django installed -- see requirements.txt).
These are separate from tests/test_model.py, which needs no Django install
at all.
"""

import json
import sys
from os.path import abspath, dirname, join

sys.path.insert(0, abspath(join(dirname(__file__), "..")))

from django.test import SimpleTestCase

import config


class HealthTests(SimpleTestCase):

    def test_health_returns_200_with_expected_body(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["service"], "pk")
        self.assertEqual(body["model_version"], config.MODEL_VERSION)
        self.assertEqual(body["computed_by"], "pk-service")

    def test_health_rejects_post(self):
        response = self.client.post("/health")
        self.assertEqual(response.status_code, 405)


class TimelineEndpointTests(SimpleTestCase):

    def _post(self, payload):
        return self.client.post(
            "/timeline",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_events_are_chronological_and_carry_input_offset(self):
        response = self._post({
            "taken_at": "2026-09-06T08:00:00+12:00",
            "components": [
                {"fraction": 0.22, "delay_h": 0.0, "ka": 1.00, "ke": 0.277},
                {"fraction": 0.78, "delay_h": 3.0, "ka": 0.50, "ke": 0.277},
            ],
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["computed_by"], "pk-service")
        self.assertEqual(body["model_version"], config.MODEL_VERSION)
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
        response = self._post({
            "taken_at": "2026-09-06T08:00:00-05:00",
            "components": [
                {"fraction": 1.0, "delay_h": 0.0, "ka": 1.0, "ke": 0.277},
            ],
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["taken_at"].endswith("-05:00"))
        for event in body["events"]:
            self.assertTrue(event["at"].endswith("-05:00"))

    def test_single_component_medication_has_no_second_release_event(self):
        response = self._post({
            "taken_at": "2026-09-06T08:00:00+12:00",
            "components": [
                {"fraction": 1.0, "delay_h": 0.0, "ka": 1.0, "ke": 0.277},
            ],
        })
        self.assertEqual(response.status_code, 200)
        labels = [event["label"] for event in response.json()["events"]]
        self.assertNotIn("Second release", labels)

    def test_malformed_json_returns_400_not_500(self):
        response = self.client.post(
            "/timeline", data="not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("error", body)
        self.assertEqual(body["computed_by"], "pk-service")

    def test_missing_field_returns_400(self):
        response = self._post({"taken_at": "2026-09-06T08:00:00+12:00"})
        self.assertEqual(response.status_code, 400)

    def test_missing_timezone_offset_returns_400(self):
        response = self._post({
            "taken_at": "2026-09-06T08:00:00",
            "components": [{"fraction": 1.0, "delay_h": 0.0, "ka": 1.0, "ke": 0.277}],
        })
        self.assertEqual(response.status_code, 400)

    def test_negative_rate_constant_returns_400(self):
        response = self._post({
            "taken_at": "2026-09-06T08:00:00+12:00",
            "components": [{"fraction": 1.0, "delay_h": 0.0, "ka": -1.0, "ke": 0.277}],
        })
        self.assertEqual(response.status_code, 400)

    def test_zero_rate_constant_returns_400(self):
        response = self._post({
            "taken_at": "2026-09-06T08:00:00+12:00",
            "components": [{"fraction": 1.0, "delay_h": 0.0, "ka": 1.0, "ke": 0.0}],
        })
        self.assertEqual(response.status_code, 400)

    def test_non_numeric_parameter_returns_400(self):
        response = self._post({
            "taken_at": "2026-09-06T08:00:00+12:00",
            "components": [{"fraction": 1.0, "delay_h": 0.0, "ka": "fast", "ke": 0.277}],
        })
        self.assertEqual(response.status_code, 400)

    def test_get_is_not_allowed(self):
        response = self.client.get("/timeline")
        self.assertEqual(response.status_code, 405)


class AdherenceEndpointTests(SimpleTestCase):

    def _post(self, payload):
        return self.client.post(
            "/adherence",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_five_minutes_late_is_on_time_and_forty_five_is_late(self):
        original = config.LATE_AFTER_MINUTES
        config.LATE_AFTER_MINUTES = 30
        try:
            response = self._post({
                "doses": [
                    {"date": "2026-09-06", "scheduled": "08:00", "taken_at": "08:05"},
                    {"date": "2026-09-07", "scheduled": "08:00", "taken_at": "08:45"},
                ]
            })
        finally:
            config.LATE_AFTER_MINUTES = original

        self.assertEqual(response.status_code, 200)
        days = {day["date"]: day for day in response.json()["days"]}
        self.assertEqual(days["2026-09-06"]["status"], "on_time")
        self.assertEqual(days["2026-09-07"]["status"], "late")

    def test_empty_list_does_not_raise(self):
        response = self._post({"doses": []})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["of"], 0)
        self.assertEqual(body["adherence"], 0.0)
        self.assertEqual(body["computed_by"], "pk-service")

    def test_malformed_json_returns_400_not_500(self):
        response = self.client.post(
            "/adherence", data="not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_doses_field_returns_400(self):
        response = self._post({})
        self.assertEqual(response.status_code, 400)

    def test_bad_date_returns_400(self):
        response = self._post({
            "doses": [{"date": "not-a-date", "scheduled": "08:00", "taken_at": "08:00"}]
        })
        self.assertEqual(response.status_code, 400)

    def test_get_is_not_allowed(self):
        response = self.client.get("/adherence")
        self.assertEqual(response.status_code, 405)
