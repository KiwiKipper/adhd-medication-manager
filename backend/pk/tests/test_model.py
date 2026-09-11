"""Model-only tests. No HTTP, no Django, no VM required.

Run with:

    py -m unittest discover -s tests -t .

(from the pk/ directory).
"""

import math
import sys
import unittest
from datetime import timedelta
from os.path import abspath, dirname, join

# Make the pk/ package root (one level up from tests/) importable regardless
# of the working directory the tests are launched from.
sys.path.insert(0, abspath(join(dirname(__file__), "..")))

import config
import model


def _single(ka, ke, fraction=1.0, delay_h=0.0):
    return [{"fraction": fraction, "delay_h": delay_h, "ka": ka, "ke": ke}]


class UnitPeakShapeTests(unittest.TestCase):

    def test_single_component_peaks_at_closed_form_time(self):
        ka, ke = 1.0, 0.277
        components = model.validate_components(_single(ka, ke))
        samples = model.sample_curve(components, sample_minutes=1, window_hours=24)

        expected_t_max = math.log(ka / ke) / (ka - ke)
        peak_sample = max(samples, key=lambda sample: sample.level)

        step_h = 1 / 60.0
        self.assertLessEqual(abs(peak_sample.t_h - expected_t_max), step_h)
        self.assertAlmostEqual(peak_sample.level, 1.0, places=6)

    def test_curve_starts_near_zero_and_decays_back_toward_zero(self):
        components = model.validate_components(_single(1.0, 0.277))
        samples = model.sample_curve(components, sample_minutes=5, window_hours=24)

        self.assertAlmostEqual(samples[0].level, 0.0, places=6)
        self.assertLess(samples[-1].level, 0.05)

    def test_ka_equals_ke_does_not_raise_or_nan(self):
        components = model.validate_components(_single(0.3, 0.3))
        samples = model.sample_curve(components, sample_minutes=5, window_hours=24)
        for sample in samples:
            self.assertFalse(math.isnan(sample.level))
            self.assertFalse(math.isinf(sample.level))
        self.assertAlmostEqual(max(sample.level for sample in samples), 1.0, places=6)

    def test_ka_very_close_to_ke_matches_limiting_case(self):
        # Values close enough that the naive closed form is numerically ugly,
        # but not within KA_KE_EPSILON, should still agree with the ka==ke
        # limiting shape to a loose tolerance.
        exact = model.validate_components(_single(0.3, 0.3))
        near = model.validate_components(_single(0.3, 0.3 + 1e-6))
        exact_samples = model.sample_curve(exact, sample_minutes=15, window_hours=24)
        near_samples = model.sample_curve(near, sample_minutes=15, window_hours=24)
        for a, b in zip(exact_samples, near_samples):
            self.assertAlmostEqual(a.level, b.level, places=3)


class TwoComponentShapeTests(unittest.TestCase):

    def test_concerta_style_curve_has_exactly_two_local_maxima(self):
        components = model.validate_components([
            {"fraction": 0.22, "delay_h": 0.0, "ka": 1.00, "ke": 0.277},
            {"fraction": 0.78, "delay_h": 3.0, "ka": 0.50, "ke": 0.277},
        ])
        samples = model.sample_curve(components, sample_minutes=5, window_hours=24)
        levels = [sample.level for sample in samples]
        maxima = model.local_maxima(levels)
        self.assertEqual(len(maxima), 2)

    def test_single_component_has_no_second_release_event(self):
        components = model.validate_components(_single(1.0, 0.277))
        samples = model.sample_curve(components, sample_minutes=5, window_hours=24)
        events = model.derive_events(samples)
        labels = [event.label for event in events]
        self.assertNotIn(model.LABEL_SECOND_RELEASE, labels)

    def test_two_component_curve_emits_events_in_order(self):
        components = model.validate_components([
            {"fraction": 0.22, "delay_h": 0.0, "ka": 1.00, "ke": 0.277},
            {"fraction": 0.78, "delay_h": 3.0, "ka": 0.50, "ke": 0.277},
        ])
        samples = model.sample_curve(components, sample_minutes=5, window_hours=24)
        events = model.derive_events(samples)
        labels = [event.label for event in events]

        self.assertEqual(labels[0], model.LABEL_TAKEN)
        self.assertIn(model.LABEL_FIRST_PEAK, labels)
        self.assertIn(model.LABEL_SECOND_RELEASE, labels)
        self.assertLess(labels.index(model.LABEL_FIRST_PEAK), labels.index(model.LABEL_SECOND_RELEASE))

        indices = [event.index for event in events]
        self.assertEqual(indices, sorted(indices))


class HalfLifeTests(unittest.TestCase):

    def _time_to_worn_off(self, ke):
        components = model.validate_components(_single(1.0, ke))
        samples = model.sample_curve(components, sample_minutes=1, window_hours=48)
        events = model.derive_events(samples)
        for event in events:
            if event.label == model.LABEL_WORN:
                return event.t_h
        self.fail("expected a 'Largely worn off' event within the window")

    def test_halving_ke_roughly_doubles_time_to_worn_off(self):
        ke = 0.277
        t_worn_full = self._time_to_worn_off(ke)
        t_worn_half = self._time_to_worn_off(ke / 2.0)

        ratio = t_worn_half / t_worn_full
        # "Roughly doubles": the onset/absorption phase is unaffected by ke,
        # so this is not exact, but should land well within a generous band.
        self.assertGreater(ratio, 1.6)
        self.assertLess(ratio, 2.4)

    def test_elimination_rate_from_half_life(self):
        ke = model.elimination_rate_from_half_life(2.5)
        self.assertAlmostEqual(ke, math.log(2.0) / 2.5)

    def test_elimination_rate_rejects_non_positive_half_life(self):
        with self.assertRaises(model.ModelError):
            model.elimination_rate_from_half_life(0)
        with self.assertRaises(model.ModelError):
            model.elimination_rate_from_half_life(-1)


class ComponentValidationTests(unittest.TestCase):

    def test_fractions_not_summing_to_one_are_normalised(self):
        components = model.validate_components([
            {"fraction": 1.0, "delay_h": 0.0, "ka": 1.0, "ke": 0.277},
            {"fraction": 1.0, "delay_h": 3.0, "ka": 0.5, "ke": 0.277},
        ])
        self.assertAlmostEqual(sum(c.fraction for c in components), 1.0)

    def test_fractions_summing_to_zero_are_rejected(self):
        with self.assertRaises(model.ModelError):
            model.validate_components([
                {"fraction": 0.0, "delay_h": 0.0, "ka": 1.0, "ke": 0.277},
            ])

    def test_non_positive_rate_constants_are_rejected(self):
        with self.assertRaises(model.ModelError):
            model.validate_components(_single(0.0, 0.277))
        with self.assertRaises(model.ModelError):
            model.validate_components(_single(1.0, -0.1))

    def test_negative_delay_is_rejected(self):
        with self.assertRaises(model.ModelError):
            model.validate_components(_single(1.0, 0.277, delay_h=-1.0))

    def test_missing_field_is_rejected(self):
        with self.assertRaises(model.ModelError):
            model.validate_components([{"fraction": 1.0, "delay_h": 0.0, "ka": 1.0}])

    def test_half_life_h_is_accepted_in_place_of_ke(self):
        components = model.validate_components([
            {"fraction": 1.0, "delay_h": 0.0, "ka": 1.0, "half_life_h": 2.5},
        ])
        self.assertAlmostEqual(components[0].ke, math.log(2.0) / 2.5)

    def test_delay_past_end_of_window_contributes_nothing(self):
        # A component that starts after the sampling window ends should not
        # crash or dominate -- it simply never turns on.
        components = model.validate_components([
            {"fraction": 0.5, "delay_h": 0.0, "ka": 1.0, "ke": 0.277},
            {"fraction": 0.5, "delay_h": 100.0, "ka": 1.0, "ke": 0.277},
        ])
        samples = model.sample_curve(components, sample_minutes=5, window_hours=24)
        self.assertAlmostEqual(max(sample.level for sample in samples), 1.0, places=6)
        for sample in samples:
            self.assertFalse(math.isnan(sample.level))

    def test_not_a_list_is_rejected(self):
        with self.assertRaises(model.ModelError):
            model.validate_components({"fraction": 1.0})

    def test_empty_list_is_rejected(self):
        with self.assertRaises(model.ModelError):
            model.validate_components([])


class TimestampParsingTests(unittest.TestCase):

    def test_parses_positive_offset(self):
        dt = model.parse_iso_datetime("2026-09-06T08:00:00+12:00")
        self.assertEqual(dt.utcoffset(), timedelta(hours=12))
        self.assertEqual(dt.isoformat(), "2026-09-06T08:00:00+12:00")

    def test_parses_negative_offset(self):
        dt = model.parse_iso_datetime("2026-09-06T08:00:00-05:00")
        self.assertEqual(dt.utcoffset(), -timedelta(hours=5))

    def test_parses_z_suffix(self):
        dt = model.parse_iso_datetime("2026-09-06T08:00:00Z")
        self.assertEqual(dt.utcoffset(), timedelta(0))

    def test_rejects_missing_offset(self):
        with self.assertRaises(model.ModelError):
            model.parse_iso_datetime("2026-09-06T08:00:00")

    def test_rejects_garbage(self):
        with self.assertRaises(model.ModelError):
            model.parse_iso_datetime("not a timestamp")

    def test_rejects_non_string(self):
        with self.assertRaises(model.ModelError):
            model.parse_iso_datetime(12345)


class AdherenceTests(unittest.TestCase):

    def test_empty_list_does_not_raise(self):
        report = model.adherence_report([])
        self.assertEqual(report["of"], 0)
        self.assertEqual(report["adherence"], 0.0)
        self.assertEqual(report["streak_days"], 0)
        self.assertEqual(report["missed"], 0)
        self.assertEqual(report["days"], [])

    def test_five_minutes_late_is_on_time_at_default_threshold(self):
        report = model.adherence_report([
            {"date": "2026-09-06", "scheduled": "08:00", "taken_at": "08:05"},
        ])
        self.assertEqual(report["days"][0]["status"], model.STATUS_ON_TIME)
        self.assertEqual(report["days"][0]["minutes_late"], 5)

    def test_forty_five_minutes_late_is_late_at_default_threshold(self):
        report = model.adherence_report([
            {"date": "2026-09-06", "scheduled": "08:00", "taken_at": "08:45"},
        ])
        self.assertEqual(report["days"][0]["status"], model.STATUS_LATE)
        self.assertEqual(report["days"][0]["minutes_late"], 45)

    def test_null_taken_at_is_missed(self):
        report = model.adherence_report([
            {"date": "2026-09-06", "scheduled": "08:00", "taken_at": None},
        ])
        self.assertEqual(report["days"][0]["status"], model.STATUS_MISSED)
        self.assertNotIn("minutes_late", report["days"][0])

    def test_unsorted_input_is_sorted_by_date_most_recent_first(self):
        report = model.adherence_report([
            {"date": "2026-09-04", "scheduled": "08:00", "taken_at": "08:00"},
            {"date": "2026-09-06", "scheduled": "08:00", "taken_at": "08:00"},
            {"date": "2026-09-05", "scheduled": "08:00", "taken_at": "08:00"},
        ])
        dates = [day["date"] for day in report["days"]]
        self.assertEqual(dates, ["2026-09-06", "2026-09-05", "2026-09-04"])

    def test_streak_counts_back_from_most_recent_and_stops_at_missed(self):
        report = model.adherence_report([
            {"date": "2026-09-01", "scheduled": "08:00", "taken_at": None},
            {"date": "2026-09-02", "scheduled": "08:00", "taken_at": "08:00"},
            {"date": "2026-09-03", "scheduled": "08:00", "taken_at": "08:10"},
            {"date": "2026-09-04", "scheduled": "08:00", "taken_at": "08:00"},
            {"date": "2026-09-05", "scheduled": "08:00", "taken_at": None},
            {"date": "2026-09-06", "scheduled": "08:00", "taken_at": "08:00"},
        ])
        self.assertEqual(report["streak_days"], 1)
        self.assertEqual(report["missed"], 2)
        self.assertEqual(report["of"], 6)

    def test_custom_late_after_minutes(self):
        report = model.adherence_report(
            [{"date": "2026-09-06", "scheduled": "08:00", "taken_at": "08:10"}],
            late_after_minutes=5,
        )
        self.assertEqual(report["days"][0]["status"], model.STATUS_LATE)

    def test_missing_taken_at_field_is_rejected(self):
        with self.assertRaises(model.ModelError):
            model.adherence_report([{"date": "2026-09-06", "scheduled": "08:00"}])

    def test_bad_date_is_rejected(self):
        with self.assertRaises(model.ModelError):
            model.adherence_report([
                {"date": "not-a-date", "scheduled": "08:00", "taken_at": "08:00"},
            ])

    def test_bad_time_is_rejected(self):
        with self.assertRaises(model.ModelError):
            model.adherence_report([
                {"date": "2026-09-06", "scheduled": "8am", "taken_at": "08:00"},
            ])


class ConfigWiringTests(unittest.TestCase):
    """A sanity check that config.py values actually drive the model,
    since the assignment's "redeploy" demonstration depends on it."""

    def test_onset_threshold_is_read_from_config(self):
        original = config.ONSET_THRESHOLD
        try:
            components = model.validate_components(_single(1.0, 0.277))
            samples = model.sample_curve(components, sample_minutes=5, window_hours=24)

            config.ONSET_THRESHOLD = 0.01
            events_low = model.derive_events(samples)
            onset_low = next(e for e in events_low if e.label == model.LABEL_ONSET)

            config.ONSET_THRESHOLD = 0.9
            events_high = model.derive_events(samples)
            onset_high = next(e for e in events_high if e.label == model.LABEL_ONSET)

            self.assertLess(onset_low.t_h, onset_high.t_h)
        finally:
            config.ONSET_THRESHOLD = original


if __name__ == "__main__":
    unittest.main()
