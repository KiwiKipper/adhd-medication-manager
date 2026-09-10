"""HTTP views for the pk service.

Thin wrappers only: every calculation happens in model.py, which is plain
Python with no Django import. Views here do request parsing, calling into
model.py, and shaping the JSON response -- nothing else. pk never touches a
database, never knows about users or sessions, and keeps no state between
requests.
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

import config
import model

# Included on every response, success or error, so a verification script can
# confirm a request actually reached this service rather than being faked
# upstream in web.
_IDENTITY = {
    "computed_by": "pk-service",
    "model_version": config.MODEL_VERSION,
}


def _ok(payload, status=200):
    body = dict(payload)
    body.update(_IDENTITY)
    return JsonResponse(body, status=status)


def _bad_request(message):
    body = {"error": str(message)}
    body.update(_IDENTITY)
    return JsonResponse(body, status=400)


def _parse_json_object(request):
    """Parse the request body as a JSON object, raising model.ModelError on
    anything that is not valid JSON or not an object -- malformed JSON is an
    input error, not a server error."""
    raw = request.body
    if not raw:
        raise model.ModelError("request body must not be empty")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise model.ModelError("request body is not valid JSON: %s" % exc)
    if not isinstance(payload, dict):
        raise model.ModelError("request body must be a JSON object")
    return payload


def _require_field(payload, field):
    if field not in payload:
        raise model.ModelError("missing required field %r" % (field,))
    return payload[field]


@require_GET
def health(request):
    """No dependencies, no I/O -- just confirms the process is up."""
    return _ok({"status": "ok", "service": "pk"})


@csrf_exempt
@require_POST
def timeline(request):
    """Sample the Bateman curve for one dose and derive its labelled events."""
    try:
        payload = _parse_json_object(request)
        taken_at = model.parse_iso_datetime(_require_field(payload, "taken_at"))
        components = model.validate_components(_require_field(payload, "components"))
    except model.ModelError as exc:
        return _bad_request(exc)

    samples = model.sample_curve(components)
    events = model.derive_events(samples)

    return _ok({
        "taken_at": taken_at.isoformat(),
        "events": model.events_payload(events, taken_at),
        "curve": model.curve_payload(samples),
    })


@csrf_exempt
@require_POST
def adherence(request):
    """Classify each dose and summarise adherence, streak and missed count."""
    try:
        payload = _parse_json_object(request)
        report = model.adherence_report(_require_field(payload, "doses"))
    except model.ModelError as exc:
        return _bad_request(exc)

    return _ok(report)
