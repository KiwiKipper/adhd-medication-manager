"""Bateman one-compartment curve shapes, plus adherence statistics.

Pure Python standard library. This module imports nothing from Django, so it
runs and is testable on a laptop with no VM:

    py -m unittest discover -s tests -t .

Everything here is about the *shape* of a curve over time, normalised so the
peak of the summed curve is 1.0. Absolute concentrations are not modelled and
no value here is calibrated against any real substance -- callers supply the
parameters.

Design notes
------------
* One code path serves every medication. An immediate-release product is the
  same code as an extended-release one with a single component instead of two.
* Each component's shape is normalised to a unit peak *before* being weighted
  by its ``fraction``, so ``fraction`` means "this share of the peak-effect
  budget" and stays legible regardless of that component's ka/ke. The summed
  curve is then renormalised so its own maximum is 1.0.
* Written for Python 3.6 (the Vagrant box is bento/ubuntu-18.04), so: no
  dataclasses, no datetime.fromisoformat, no walrus operator.
"""

import math
import re
from collections import namedtuple
from datetime import datetime, timedelta, timezone

import config

# Event labels. Presentation strings, not tunable thresholds.
LABEL_TAKEN          = "Taken"
LABEL_ONSET          = "Should start to feel it"
LABEL_FIRST_PEAK     = "First peak"
LABEL_SECOND_RELEASE = "Second release"
LABEL_FADE           = "Starting to fade"
LABEL_WORN           = "Largely worn off"

# Canonical ordering, used only to break ties when two events land on the same
# sample. Chronological order is otherwise determined by the sample index.
_LABEL_RANK = {
    LABEL_TAKEN: 0,
    LABEL_ONSET: 1,
    LABEL_FIRST_PEAK: 2,
    LABEL_SECOND_RELEASE: 3,
    LABEL_FADE: 4,
    LABEL_WORN: 5,
}

# Adherence statuses.
STATUS_ON_TIME = "on_time"
STATUS_LATE    = "late"
STATUS_MISSED  = "missed"


class ModelError(ValueError):
    """Bad input. Callers turn this into a 400 with the message as the reason."""


# A single sample of the curve. ``t_h`` is hours after taken_at; ``index`` is
# the sample number, which lets callers build exact timestamps with integer
# minute arithmetic instead of accumulating float error.
Sample = namedtuple("Sample", ["index", "t_h", "level"])

# An event pinned to a sample of the curve.
Event = namedtuple("Event", ["index", "t_h", "label"])


# --------------------------------------------------------------------------
# Numbers and timestamps
# --------------------------------------------------------------------------

def _as_number(value, what):
    """Coerce to float, rejecting bools, strings, None and non-finite values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelError("%s must be a number, got %r" % (what, value))
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        raise ModelError("%s must be a finite number, got %r" % (what, value))
    return number


_ISO_RE = re.compile(
    r"^(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2})"
    r"[Tt ](?P<h>\d{2}):(?P<mi>\d{2})(?::(?P<s>\d{2})(?:\.(?P<us>\d{1,6}))?)?"
    r"(?P<tz>[Zz]|[+-]\d{2}:?\d{2})$"
)


def parse_iso_datetime(text):
    """Parse an ISO-8601 timestamp that carries an explicit UTC offset.

    Returns an aware datetime whose tzinfo is that fixed offset, so the offset
    round-trips through isoformat() unchanged and no conversion to UTC or to
    the server's local time ever happens.

    A timestamp with no offset is rejected rather than guessed at: there would
    be no offset to preserve, and defaulting to the server clock is exactly
    what this service must not do.
    """
    if not isinstance(text, str):
        raise ModelError("timestamp must be a string, got %r" % (text,))
    match = _ISO_RE.match(text.strip())
    if match is None:
        raise ModelError(
            "timestamp %r is not an ISO-8601 datetime with a UTC offset "
            "(expected e.g. 2026-09-06T08:00:00+12:00)" % (text,)
        )

    parts = match.groupdict()
    tz_text = parts["tz"]
    if tz_text in ("Z", "z"):
        offset = timezone.utc
    else:
        sign = -1 if tz_text[0] == "-" else 1
        digits = tz_text[1:].replace(":", "")
        hours = int(digits[:2])
        minutes = int(digits[2:4])
        if minutes > 59:
            raise ModelError("timestamp %r has an invalid UTC offset" % (text,))
        offset = timezone(sign * timedelta(hours=hours, minutes=minutes))

    microsecond = int((parts["us"] or "").ljust(6, "0") or 0)
    try:
        return datetime(
            int(parts["y"]), int(parts["mo"]), int(parts["d"]),
            int(parts["h"]), int(parts["mi"]), int(parts["s"] or 0),
            microsecond, tzinfo=offset,
        )
    except ValueError as exc:
        raise ModelError("timestamp %r is not a real date or time: %s" % (text, exc))


# --------------------------------------------------------------------------
# The Bateman shape
# --------------------------------------------------------------------------

def elimination_rate_from_half_life(half_life_hours):
    """ke = ln(2) / half-life."""
    half_life = _as_number(half_life_hours, "half_life_h")
    if half_life <= 0:
        raise ModelError("half_life_h must be greater than 0, got %r" % (half_life_hours,))
    return math.log(2.0) / half_life


def component_peak_time(ka, ke):
    """Hours from a component's own start to its maximum.

    Closed form t_max = ln(ka/ke) / (ka - ke). When ka == ke that divides by
    zero, so the limiting case t_max = 1/ka is used instead: as ka approaches
    ke the scaled Bateman function tends to ka*t*exp(-ka*t), whose maximum is
    at 1/ka.
    """
    if abs(ka - ke) < config.KA_KE_EPSILON:
        return 1.0 / ka
    return math.log(ka / ke) / (ka - ke)


def unit_peak_shape(t_h, ka, ke):
    """A component's shape at ``t_h`` hours after its own start, peak == 1.0.

    Zero at or before its start, so a component that has not begun contributes
    nothing. Handles ka == ke (the limiting case above) and ka < ke, where the
    raw difference of exponentials is negative everywhere and dividing by the
    equally negative peak still yields a positive unit-peak shape.
    """
    if t_h <= 0.0:
        return 0.0

    if abs(ka - ke) < config.KA_KE_EPSILON:
        # Limiting case, written in unit-peak form: (t/tp) * exp(1 - t/tp).
        ratio = t_h / (1.0 / ka)
        return ratio * math.exp(1.0 - ratio)

    t_max = component_peak_time(ka, ke)
    peak = math.exp(-ke * t_max) - math.exp(-ka * t_max)
    if peak == 0.0:
        # Unreachable for positive ka != ke, but never emit a NaN.
        return 0.0
    return (math.exp(-ke * t_h) - math.exp(-ka * t_h)) / peak


# --------------------------------------------------------------------------
# Components
# --------------------------------------------------------------------------

Component = namedtuple("Component", ["fraction", "delay_h", "ka", "ke"])


def validate_components(raw_components):
    """Validate and normalise the component list.

    Each component needs ``fraction``, ``delay_h``, ``ka``, and exactly one of
    ``ke`` or ``half_life_h``. Fractions that do not sum to 1.0 are normalised
    rather than rejected; a set of fractions summing to zero has no shape at
    all and is rejected.
    """
    if not isinstance(raw_components, list):
        raise ModelError("components must be a list, got %r" % (raw_components,))
    if not raw_components:
        raise ModelError("components must contain at least one component")

    parsed = []
    for position, raw in enumerate(raw_components):
        where = "components[%d]" % position
        if not isinstance(raw, dict):
            raise ModelError("%s must be an object, got %r" % (where, raw))

        for field in ("fraction", "delay_h", "ka"):
            if field not in raw:
                raise ModelError("%s is missing required field %r" % (where, field))

        has_ke = "ke" in raw and raw["ke"] is not None
        has_half_life = "half_life_h" in raw and raw["half_life_h"] is not None
        if has_ke and has_half_life:
            raise ModelError("%s must give either ke or half_life_h, not both" % where)
        if not has_ke and not has_half_life:
            raise ModelError("%s is missing required field 'ke' (or 'half_life_h')" % where)

        fraction = _as_number(raw["fraction"], "%s.fraction" % where)
        delay_h = _as_number(raw["delay_h"], "%s.delay_h" % where)
        ka = _as_number(raw["ka"], "%s.ka" % where)
        if has_ke:
            ke = _as_number(raw["ke"], "%s.ke" % where)
        else:
            ke = elimination_rate_from_half_life(raw["half_life_h"])

        if fraction < 0:
            raise ModelError("%s.fraction must not be negative, got %r" % (where, fraction))
        if delay_h < 0:
            raise ModelError("%s.delay_h must not be negative, got %r" % (where, delay_h))
        if ka <= 0:
            raise ModelError("%s.ka must be greater than 0, got %r" % (where, ka))
        if ke <= 0:
            raise ModelError("%s.ke must be greater than 0, got %r" % (where, ke))

        parsed.append(Component(fraction, delay_h, ka, ke))

    total = sum(component.fraction for component in parsed)
    if total <= 0:
        raise ModelError("component fractions must sum to more than 0")
    return [component._replace(fraction=component.fraction / total) for component in parsed]


# --------------------------------------------------------------------------
# Sampling
# --------------------------------------------------------------------------

def sample_curve(components, sample_minutes=None, window_hours=None):
    """Sample the summed curve at a fixed step, normalised so its peak is 1.0.

    ``components`` must already have been through validate_components. A
    component whose delay falls at or beyond the end of the window simply
    contributes zero to every sample. If no component contributes anything --
    every delay is past the window -- the result is a flat zero curve rather
    than a division by zero.
    """
    if sample_minutes is None:
        sample_minutes = config.SAMPLE_MINUTES
    if window_hours is None:
        window_hours = config.WINDOW_HOURS
    if sample_minutes <= 0:
        raise ModelError("sample_minutes must be greater than 0")
    if window_hours <= 0:
        raise ModelError("window_hours must be greater than 0")

    step_count = int(round(window_hours * 60.0 / sample_minutes))
    raw_levels = []
    for index in range(step_count + 1):
        t_h = index * sample_minutes / 60.0
        level = 0.0
        for component in components:
            level += component.fraction * unit_peak_shape(
                t_h - component.delay_h, component.ka, component.ke
            )
        raw_levels.append(level)

    peak = max(raw_levels)
    scale = (1.0 / peak) if peak > 0.0 else 0.0
    return [
        Sample(index, index * sample_minutes / 60.0, level * scale)
        for index, level in enumerate(raw_levels)
    ]


def local_maxima(levels, min_dip=None):
    """Indices of the curve's local maxima, ignoring insignificant wobbles.

    Two bumps only count separately if the curve dips at least ``min_dip``
    below both of them in between; otherwise they are the same bump and the
    higher sample wins. The first and last samples are never candidates, since
    a curve still rising at the end of the window has not peaked within it.
    """
    if min_dip is None:
        min_dip = config.LOCAL_MAX_MIN_DIP

    candidates = []
    for index in range(1, len(levels) - 1):
        if levels[index] > levels[index - 1] and levels[index] >= levels[index + 1]:
            if levels[index] > 0.0:
                candidates.append(index)

    kept = []
    for candidate in candidates:
        if not kept:
            kept.append(candidate)
            continue
        previous = kept[-1]
        valley = min(levels[previous:candidate + 1])
        if min(levels[previous], levels[candidate]) - valley >= min_dip:
            kept.append(candidate)
        elif levels[candidate] > levels[previous]:
            kept[-1] = candidate
    return kept


def _first_index_at_or_above(levels, threshold, start=0):
    for index in range(start, len(levels)):
        if levels[index] >= threshold:
            return index
    return None


def _first_index_below(levels, threshold, start=0):
    for index in range(start, len(levels)):
        if levels[index] < threshold:
            return index
    return None


def derive_events(samples):
    """Derive the labelled events from an already-sampled curve.

    Events that do not occur within the window are omitted: a single-component
    medication has no second release, and a curve that never clears the onset
    threshold gets no onset event. The returned list is in chronological order.

    Thresholds are compared directly against the levels because the curve is
    normalised to a peak of 1.0, which makes every level a proportion of peak.

    "First peak" is the earliest maximum of the summed curve and "Second
    release" the next one after a dip, so the two labels always come out in
    that order. With a single maximum -- every immediate-release medication --
    the first peak is also the global maximum. Fade and worn-off are searched
    from the *last* maximum onwards, so the dip between two bumps cannot be
    mistaken for the curve wearing off.
    """
    levels = [sample.level for sample in samples]
    found = []

    if samples:
        found.append((samples[0].index, LABEL_TAKEN))

    if not levels or max(levels) <= 0.0:
        # Nothing ever begins inside the window; "Taken" is all we can say.
        return _ordered(samples, found)

    maxima = local_maxima(levels)
    if not maxima:
        # Monotonic within the window (e.g. a late component still rising at
        # the end): fall back to the global maximum.
        maxima = [levels.index(max(levels))]

    onset = _first_index_at_or_above(levels, config.ONSET_THRESHOLD)
    if onset is not None:
        found.append((onset, LABEL_ONSET))

    found.append((maxima[0], LABEL_FIRST_PEAK))
    if len(maxima) > 1:
        found.append((maxima[1], LABEL_SECOND_RELEASE))

    after_last_peak = maxima[-1] + 1
    fade = _first_index_below(levels, config.FADE_THRESHOLD, after_last_peak)
    if fade is not None:
        found.append((fade, LABEL_FADE))
    worn = _first_index_below(levels, config.WORN_THRESHOLD, after_last_peak)
    if worn is not None:
        found.append((worn, LABEL_WORN))

    return _ordered(samples, found)


def _ordered(samples, found):
    by_index = {sample.index: sample for sample in samples}
    found = sorted(found, key=lambda pair: (pair[0], _LABEL_RANK[pair[1]]))
    return [Event(index, by_index[index].t_h, label) for index, label in found]


def build_timeline(raw_components, sample_minutes=None, window_hours=None):
    """Validate, sample and derive events in one call. No I/O, no state."""
    components = validate_components(raw_components)
    samples = sample_curve(components, sample_minutes, window_hours)
    return samples, derive_events(samples)


# --------------------------------------------------------------------------
# Adherence
# --------------------------------------------------------------------------

_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_TIME_RE = re.compile(r"^(\d{2}):(\d{2})(?::(\d{2}))?$")


def _parse_date(text, where):
    if not isinstance(text, str) or _DATE_RE.match(text.strip()) is None:
        raise ModelError("%s must be a YYYY-MM-DD date, got %r" % (where, text))
    year, month, day = (int(part) for part in _DATE_RE.match(text.strip()).groups())
    try:
        return datetime(year, month, day).date()
    except ValueError as exc:
        raise ModelError("%s is not a real date: %s" % (where, exc))


def _parse_minutes_of_day(text, where):
    if not isinstance(text, str) or _TIME_RE.match(text.strip()) is None:
        raise ModelError("%s must be an HH:MM time, got %r" % (where, text))
    hours, minutes, _seconds = _TIME_RE.match(text.strip()).groups()
    hours, minutes = int(hours), int(minutes)
    if hours > 23 or minutes > 59:
        raise ModelError("%s is not a real time of day, got %r" % (where, text))
    return hours * 60 + minutes


def adherence_report(raw_doses, late_after_minutes=None):
    """Classify each dose and summarise the run of them.

    The input is sorted by date here rather than trusted to arrive sorted, and
    the days come back most recent first. An empty list yields zeroes instead
    of dividing by zero.

    ``minutes_late`` is signed and reported as measured, so a dose taken before
    its scheduled time reads as a negative number and still counts as on time.
    A dose is compared against its own day's scheduled time only, so a time
    that has wrapped past midnight reads as early rather than very late.

    The streak counts back from the most recent day and stops at the first
    missed day. A date with no dose record at all is not treated as a break,
    because a gap may simply mean nothing was scheduled that day.
    """
    if late_after_minutes is None:
        late_after_minutes = config.LATE_AFTER_MINUTES

    if not isinstance(raw_doses, list):
        raise ModelError("doses must be a list, got %r" % (raw_doses,))

    parsed = []
    for position, raw in enumerate(raw_doses):
        where = "doses[%d]" % position
        if not isinstance(raw, dict):
            raise ModelError("%s must be an object, got %r" % (where, raw))
        for field in ("date", "scheduled"):
            if field not in raw:
                raise ModelError("%s is missing required field %r" % (where, field))
        if "taken_at" not in raw:
            raise ModelError(
                "%s is missing required field 'taken_at' (use null for a missed dose)" % where
            )

        date = _parse_date(raw["date"], "%s.date" % where)
        scheduled = _parse_minutes_of_day(raw["scheduled"], "%s.scheduled" % where)

        if raw["taken_at"] is None:
            parsed.append((date, STATUS_MISSED, None))
            continue

        taken = _parse_minutes_of_day(raw["taken_at"], "%s.taken_at" % where)
        minutes_late = taken - scheduled
        status = STATUS_LATE if minutes_late > late_after_minutes else STATUS_ON_TIME
        parsed.append((date, status, minutes_late))

    parsed.sort(key=lambda row: row[0], reverse=True)

    days = []
    for date, status, minutes_late in parsed:
        day = {"date": date.isoformat(), "status": status}
        if minutes_late is not None:
            day["minutes_late"] = minutes_late
        days.append(day)

    total = len(parsed)
    missed = sum(1 for row in parsed if row[1] == STATUS_MISSED)
    taken_count = total - missed

    streak = 0
    for _date, status, _minutes_late in parsed:  # already most recent first
        if status == STATUS_MISSED:
            break
        streak += 1

    adherence = 0.0 if total == 0 else round(
        taken_count / float(total), config.ADHERENCE_DECIMALS
    )

    return {
        "days": days,
        "adherence": adherence,
        "streak_days": streak,
        "missed": missed,
        "of": total,
    }


# --------------------------------------------------------------------------
# Payload shaping. Kept here so the views stay thin and framework-agnostic.
# --------------------------------------------------------------------------

def curve_payload(samples):
    return [
        {
            "t_h": round(sample.t_h, config.CURVE_TIME_DECIMALS),
            "level": round(sample.level, config.CURVE_LEVEL_DECIMALS),
        }
        for sample in samples
    ]


def events_payload(events, taken_at, sample_minutes=None):
    """Stamp each event with a real timestamp in taken_at's own offset.

    Offsets are added as whole minutes from the sample index, so no float drift
    reaches the emitted timestamps, and taken_at's tzinfo is a fixed offset so
    the arithmetic cannot shift it.
    """
    if sample_minutes is None:
        sample_minutes = config.SAMPLE_MINUTES
    return [
        {
            "at": (taken_at + timedelta(minutes=event.index * sample_minutes)).isoformat(),
            "label": event.label,
        }
        for event in events
    ]
