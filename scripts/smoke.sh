#!/bin/bash
# End-to-end check against a running stack, from the host.
#
#   scripts/smoke.sh                            # against http://localhost:8000
#   BASE=http://192.168.56.12 scripts/smoke.sh  # against a specific address
#
# First confirms all three VMs are running, then logs in as the seeded demo
# account `admin` (see backend/tracker/management/commands/seed_demo.py) and
# walks every page the frontend calls on load, so a pass means nginx, the
# proxy to the backend VM, gunicorn, Django, the pk module and postgres are
# all working together -- not just that a port answers.
#
# Read-only: it logs no doses or notes, so running it never changes the demo
# data. Needs vagrant, curl and a Python 3 interpreter on the host.
#
# Restored after a21d280 removed it: the provisioning health checks only run
# during `vagrant provision`, and the assignment asks for a verify command
# that can be run on its own against an already-deployed system.

set -u

BASE="${BASE:-http://localhost:8000}"
COOKIES="$(mktemp)"
BODY="$(mktemp)"
trap 'rm -f "$COOKIES" "$BODY"' EXIT

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
# literal string "None" -- good enough for the comparisons made here.
json() {
    "$PY" -c "
import json, sys
data = json.load(sys.stdin)
path = sys.argv[1].lstrip('.').split('.') if sys.argv[1] not in ('.', '') else []
for part in path:
    data = data[int(part)] if part.isdigit() else data[part]
print(data)
" "$1"
}

step "0. vagrant status: db, backend and frontend are running"
status=$(vagrant status --machine-readable 2>/dev/null)
for node in db backend frontend; do
    if echo "$status" | grep -q ",$node,state,running"; then
        echo "$node: running"
    else
        fail "$node VM is not running (vagrant up $node)"
    fi
done

echo
echo "smoke: testing $BASE"

step "1. GET /auth/csrf/ sets the CSRF cookie"
code=$(curl -s -c "$COOKIES" -o /dev/null -w "%{http_code}" "$BASE/auth/csrf/")
if [ "$code" = "000" ]; then
    # Nothing answered at all, so every later check would fail the same way.
    echo "FAIL: nothing is listening at $BASE -- are the VMs up, and is that the forwarded port?" >&2
    exit 1
fi
[ "$code" = "200" ] || fail "csrf: expected 200, got $code"
grep -q csrftoken "$COOKIES" || fail "csrf: csrftoken cookie was not set"

CSRF_TOKEN=$(grep csrftoken "$COOKIES" | awk '{print $NF}')

step "2. POST /auth/login/ as admin"
code=$(curl -s -b "$COOKIES" -c "$COOKIES" -o "$BODY" -w "%{http_code}" \
    -X POST "$BASE/auth/login/" \
    -H "Content-Type: application/json" -H "X-CSRFToken: $CSRF_TOKEN" \
    -H "Referer: $BASE/" \
    -d '{"username": "admin", "password": "password"}')
[ "$code" = "200" ] || fail "login: expected 200, got $code (is the backend seeded? see seed_demo)"

get() { curl -sf -b "$COOKIES" -c "$COOKIES" "$BASE$1"; }

step "3. GET /api/my-medication/ (stored selection, from postgres)"
body=$(get /api/my-medication/) || fail "my-medication: request failed"
[ "$(json '.medication.id' <<<"$body")" = "vyvanse" ] || fail "my-medication: expected medication.id vyvanse, got: $body"
[ "$(json '.scheduled_time' <<<"$body")" = "08:00" ] || fail "my-medication: expected scheduled_time 08:00, got: $body"

step "4. GET /api/doses/ (seeded history)"
body=$(get /api/doses/) || fail "doses: request failed"
count=$("$PY" -c "import json,sys; print(len(json.load(sys.stdin)))" <<<"$body")
[ "$count" -ge 9 ] 2>/dev/null || fail "doses: expected >= 9 rows, got $count"
today=$("$PY" -c "import datetime; print(datetime.date.today().isoformat())")
echo "$body" | grep -q "\"date\": *\"$today\"" || fail "doses: no row dated today ($today)"

step "5. GET /api/timeline/ (curve computed by backend.pk)"
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
[ "$count" -ge 7 ] 2>/dev/null || fail "notes: expected >= 7, got $count"
echo "$body" | grep -q '"flagged": *true' || fail "notes: expected at least one flagged note"

step "8. GET /curve (SPA fallback on a client-side route)"
code=$(curl -s -o "$BODY" -w "%{http_code}" "$BASE/curve")
[ "$code" = "200" ] || fail "curve page: expected 200, got $code"
grep -q 'id="app"' "$BODY" || fail "curve page: response has no #app mount point -- is this index.html?"

step "9. GET /static/admin/css/base.css (WhiteNoise through the proxy)"
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/static/admin/css/base.css")
[ "$code" = "200" ] || fail "admin static: expected 200, got $code"

echo
if [ "$FAILED" -eq 0 ]; then
    echo "smoke: all checks passed against $BASE"
    exit 0
else
    echo "smoke: one or more checks FAILED against $BASE -- see above" >&2
    exit 1
fi
