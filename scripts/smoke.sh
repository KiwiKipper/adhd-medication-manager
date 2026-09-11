#!/bin/bash
# End-to-end check against a running stack, from the host.
#
#   scripts/smoke.sh                          # against http://localhost:8000
#   BASE=http://192.168.56.12 scripts/smoke.sh  # against a specific address
#
# Logs in as the seeded demo account `ada` (see
# backend/tracker/management/commands/seed_demo.py) and walks every page the
# frontend actually calls on load, so a pass here means nginx, the proxy to
# the backend VM, gunicorn, Django, the pk module and postgres are all
# working together -- not just that a port answers.
#
# Needs curl and a Python 3 interpreter (tried in order below) for JSON;
# nothing else.

set -u

BASE="${BASE:-http://localhost:8000}"
COOKIES="$(mktemp)"
trap 'rm -f "$COOKIES"' EXIT

PY=""
for candidate in python3 py python; do
    if command -v "$candidate" > /dev/null 2>&1 && "$candidate" -c "" > /dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "smoke: no working Python 3 interpreter found (tried python3, py, python)" >&2
    exit 1
fi

FAILED=0
step() { echo; echo "== $1 =="; }
fail() { echo "FAIL: $1" >&2; FAILED=1; }

# Pulls one field out of a JSON response body via a dotted path, e.g.
# `json '.medication.id' <<<"$body"`. Missing/null comes back as the
# literal string "None" from repr() below -- good enough for the
# string/substring comparisons this script makes.
json() {
    "$PY" -c "
import json, sys
data = json.load(sys.stdin)
path = sys.argv[1].lstrip('.').split('.') if sys.argv[1] not in ('.', '') else []
for part in path:
    if part.isdigit():
        data = data[int(part)]
    else:
        data = data[part]
print(data)
" "$1"
}

echo "smoke: testing $BASE"

step "1. GET /auth/csrf/ sets the CSRF cookie"
code=$(curl -sf -c "$COOKIES" -o /dev/null -w "%{http_code}" "$BASE/auth/csrf/")
[ "$code" = "200" ] || fail "csrf: expected 200, got $code"
grep -q csrftoken "$COOKIES" || fail "csrf: csrftoken cookie was not set"

CSRF_TOKEN=$(grep csrftoken "$COOKIES" | awk '{print $NF}')

step "2. POST /auth/login/ as ada"
code=$(curl -sf -b "$COOKIES" -c "$COOKIES" -o /tmp/smoke_login.json -w "%{http_code}" \
    -X POST "$BASE/auth/login/" \
    -H "Content-Type: application/json" -H "X-CSRFToken: $CSRF_TOKEN" \
    -d '{"username": "ada", "password": "dose-demo-2026"}')
[ "$code" = "200" ] || fail "login: expected 200, got $code (is the backend seeded? see seed_demo)"

get() { curl -sf -b "$COOKIES" -c "$COOKIES" "$BASE$1"; }

step "3. GET /api/my-medication/"
body=$(get /api/my-medication/) || fail "my-medication: request failed"
[ "$(json '.medication.id' <<<"$body")" = "concerta" ] || fail "my-medication: expected medication.id concerta, got: $body"
[ "$(json '.scheduled_time' <<<"$body")" = "08:00" ] || fail "my-medication: expected scheduled_time 08:00, got: $body"

step "4. GET /api/doses/"
body=$(get /api/doses/) || fail "doses: request failed"
count=$("$PY" -c "import json,sys; print(len(json.load(sys.stdin)))" <<<"$body")
[ "$count" -ge 9 ] || fail "doses: expected >= 9 rows, got $count"
today=$("$PY" -c "import datetime; print(datetime.date.today().isoformat())")
echo "$body" | grep -q "\"date\": *\"$today\"" || fail "doses: no row dated today ($today)"

step "5. GET /api/timeline/"
body=$(get /api/timeline/) || fail "timeline: request failed"
curve_len=$("$PY" -c "import json,sys; print(len(json.load(sys.stdin)['curve']))" <<<"$body" 2>/dev/null)
[ "$curve_len" = "289" ] || fail "timeline: expected 289 curve samples, got: $curve_len"
[ "$(json '.events.0.label' <<<"$body")" = "Taken" ] || fail "timeline: expected events[0].label Taken"
[ "$(json '.computed_by' <<<"$body")" = "backend.pk" ] || fail "timeline: expected computed_by backend.pk"

step "6. GET /api/adherence/"
body=$(get '/api/adherence/?days=14') || fail "adherence: request failed"
[ "$(json '.of' <<<"$body")" = "14" ] || fail "adherence: expected of=14"
streak=$(json '.streak_days' <<<"$body")
[ "$streak" -ge 0 ] 2>/dev/null || fail "adherence: streak_days not a number: $streak"
echo "$body" | grep -q '"status": *"late"' || fail "adherence: expected at least one late day in the seeded window"

step "7. GET /api/notes/"
body=$(get /api/notes/) || fail "notes: request failed"
count=$("$PY" -c "import json,sys; print(len(json.load(sys.stdin)))" <<<"$body")
[ "$count" -ge 8 ] || fail "notes: expected >= 8, got $count"
echo "$body" | grep -q '"flagged": *true' || fail "notes: expected at least one flagged note"

step "8. GET /curve (SPA fallback on a client-side route)"
code=$(curl -sf -b "$COOKIES" -o /tmp/smoke_curve.html -w "%{http_code}" "$BASE/curve")
[ "$code" = "200" ] || fail "curve page: expected 200, got $code"
grep -q 'id="app"' /tmp/smoke_curve.html || fail "curve page: response body has no #app mount point -- is this index.html?"

step "9. GET /static/admin/css/base.css (WhiteNoise through the proxy)"
code=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE/static/admin/css/base.css")
[ "$code" = "200" ] || fail "admin static: expected 200, got $code"

echo
if [ "$FAILED" -eq 0 ]; then
    echo "smoke: all checks passed against $BASE"
    exit 0
else
    echo "smoke: one or more checks FAILED against $BASE -- see above" >&2
    exit 1
fi
