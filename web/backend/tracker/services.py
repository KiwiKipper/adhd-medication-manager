"""The only place web talks to the pk service.

web never computes a release curve or classifies a dose itself -- it fetches
parameters from the database and posts them to pk, then passes back whatever
pk returns. Views should go through call_pk_timeline / call_pk_adherence
rather than calling `requests` directly, so every pk call is validated and
turned into a readable error the same way.
"""

import requests
from django.conf import settings


class PkServiceError(Exception):
    """Raised when pk can't be reached, times out, or rejects the request.

    `status_code` is what the view should return to the browser: 400 when pk
    validly rejected the input (its own message is preserved), 502 when pk
    itself could not be reached or returned something unexpected -- a web
    problem, not a "you sent bad data" problem.
    """

    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _call_pk(path, payload):
    url = f"{settings.PK_SERVICE_URL}{path}"
    try:
        response = requests.post(url, json=payload, timeout=settings.PK_SERVICE_TIMEOUT)
    except requests.RequestException as exc:
        raise PkServiceError("pk service is unreachable: %s" % exc, status_code=502)

    if response.status_code == 400:
        try:
            detail = response.json().get("error", response.text)
        except ValueError:
            detail = response.text
        raise PkServiceError(detail, status_code=400)

    if response.status_code != 200:
        raise PkServiceError(
            "pk service returned unexpected status %s" % response.status_code,
            status_code=502,
        )

    try:
        return response.json()
    except ValueError:
        raise PkServiceError("pk service returned a non-JSON response", status_code=502)


def call_pk_timeline(taken_at, components):
    """taken_at: ISO-8601 string with a UTC offset. components: pk_components
    list straight off a Medication row."""
    return _call_pk("/timeline", {"taken_at": taken_at, "components": components})


def call_pk_adherence(doses):
    """doses: [{"date", "scheduled", "taken_at"}, ...], taken_at may be None."""
    return _call_pk("/adherence", {"doses": doses})
