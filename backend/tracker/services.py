"""The only place tracker touches the pk maths.

pk (backend/pk/) is a plain Python package -- no Django import, no I/O -- so
this is an in-process call, not a network one. Views should go through
compute_timeline / compute_adherence / classify_dose rather than importing
pk.model directly, so every call is validated and turned into a readable
error the same way, and so there is exactly one place that decides
on-time/late (see classify_dose).
"""

from django.utils import timezone

from pk import config, model

# Included on every timeline/adherence response, so it's visible on the wire
# that these numbers are computed, not measured, and which version of the
# maths produced them -- the same fields pk's old HTTP responses carried.
IDENTITY = {"computed_by": "backend.pk", "model_version": config.MODEL_VERSION}


class PkInputError(ValueError):
    """Bad parameters or a bad timestamp; the view turns this into a 400."""


def compute_timeline(taken_at, components):
    """taken_at: an aware datetime, or an ISO-8601 string carrying a UTC
    offset. components: a Medication's pk_components list, unmodified."""
    try:
        if isinstance(taken_at, str):
            taken_at = model.parse_iso_datetime(taken_at)
        samples, events = model.build_timeline(components)
    except model.ModelError as exc:
        raise PkInputError(str(exc))

    return {
        "taken_at": taken_at.isoformat(),
        "events": model.events_payload(events, taken_at),
        "curve": model.curve_payload(samples),
        **IDENTITY,
    }


def compute_adherence(doses):
    """doses: [{"date", "scheduled", "taken_at"}, ...], taken_at may be None."""
    try:
        report = model.adherence_report(doses)
    except model.ModelError as exc:
        raise PkInputError(str(exc))
    return {**report, **IDENTITY}


def classify_dose(scheduled_time, taken_at):
    """The on-time/late status for one dose, by the same rule adherence
    reporting uses -- so POST /doses/ and GET /adherence/ can never
    disagree about the same dose.

    scheduled_time: a datetime.time (as stored on UserMedication), or None
    if nothing has been scheduled yet. taken_at: an aware datetime. Returns
    a tracker.models.Dose.Status value, or ON_TIME when there is no
    schedule to classify against.
    """
    if scheduled_time is None:
        return model.STATUS_ON_TIME

    local_taken = timezone.localtime(taken_at)
    scheduled_minutes = scheduled_time.hour * 60 + scheduled_time.minute
    taken_minutes = local_taken.hour * 60 + local_taken.minute
    status, _minutes_late = model.classify(scheduled_minutes, taken_minutes)
    return status
