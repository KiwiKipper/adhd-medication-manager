#!/bin/bash
# End-to-end check of the AWS deployment, from your laptop. The cloud
# counterpart of scripts/smoke.sh, in the same pass/fail style.
#
#   bash scripts/cloud-smoke.sh                       # URL from terraform output
#   BASE=http://ec2-....amazonaws.com bash scripts/cloud-smoke.sh
#
# 0. Asks AWS (via the CLI, so Learner Lab credentials must be current)
#    whether both dose-* instances are running, RDS dose-db is available and
#    the SNS topic has a confirmed subscriber.
# 1+. Logs in as the seeded demo account `dev1` through the frontend's public
#    URL, writes a note and reads it back -- a round trip through nginx, the
#    backend instance and RDS -- then reads the timeline and adherence.
#
# Not read-only: each run adds one note to dev1, marked "cloud-smoke".
# Needs aws, terraform (unless BASE is set), curl and Python 3.

set -u

TF_DIR="$(dirname "$0")/../infra/terraform"
BASE="${BASE:-$(terraform -chdir="$TF_DIR" output -raw frontend_url 2>/dev/null)}"
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
    echo "cloud-smoke: no working Python 3 interpreter found (tried python3, py, python)" >&2
    exit 1
fi

FAILED=0
step() { echo; echo "== $1 =="; }
fail() { echo "FAIL: $1" >&2; FAILED=1; }

# Same helper as smoke.sh: one field out of a JSON body by dotted path.
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

step "0. AWS: instances running, RDS available, SNS subscriber confirmed"
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "FAIL: AWS CLI has no valid credentials -- re-paste the Learner Lab credentials" >&2
    exit 1
fi
for role in frontend backend; do
    state=$(aws ec2 describe-instances \
        --filters "Name=tag:Name,Values=dose-$role" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
        --query "Reservations[0].Instances[0].State.Name" --output text 2>/dev/null)
    [ "$state" = "running" ] && echo "dose-$role: running" || fail "dose-$role instance is '$state', expected running"
done
db=$(aws rds describe-db-instances --db-instance-identifier dose-db \
    --query "DBInstances[0].DBInstanceStatus" --output text 2>/dev/null)
[ "$db" = "available" ] && echo "dose-db: available" || fail "RDS dose-db is '$db', expected available"
topic=$(aws sns list-topics --query "Topics[?ends_with(TopicArn, ':dose-alerts')].TopicArn | [0]" --output text 2>/dev/null)
if [ -z "$topic" ] || [ "$topic" = "None" ]; then
    fail "SNS topic dose-alerts not found"
else
    confirmed=$(aws sns list-subscriptions-by-topic --topic-arn "$topic" \
        --query "length(Subscriptions[?starts_with(SubscriptionArn, 'arn:')])" --output text 2>/dev/null)
    [ "${confirmed:-0}" -ge 1 ] 2>/dev/null && echo "dose-alerts: $confirmed confirmed subscriber(s)" \
        || fail "SNS topic has no confirmed subscription (click the email link)"
fi

if [ -z "$BASE" ]; then
    echo "FAIL: no frontend URL -- set BASE or run terraform apply first" >&2
    exit 1
fi
echo
echo "cloud-smoke: testing $BASE"

step "1. GET /auth/csrf/ through the frontend"
code=$(curl -s -m 15 -c "$COOKIES" -o /dev/null -w "%{http_code}" "$BASE/auth/csrf/")
if [ "$code" = "000" ]; then
    echo "FAIL: nothing answered at $BASE -- is the frontend running, and is this its current URL?" >&2
    exit 1
fi
[ "$code" = "200" ] || fail "csrf: expected 200, got $code (502 = nginx up but backend unreachable)"
CSRF_TOKEN=$(grep csrftoken "$COOKIES" | awk '{print $NF}')

post() {
    curl -s -m 15 -o "$2" -w "%{http_code}" -b "$COOKIES" -c "$COOKIES" \
        -H "Content-Type: application/json" -H "X-CSRFToken: $CSRF_TOKEN" -H "Referer: $BASE/" \
        -d "$3" "$BASE$1"
}
get() { curl -sf -m 15 -b "$COOKIES" -c "$COOKIES" "$BASE$1"; }

step "2. POST /auth/login/ as dev1"
code=$(post /auth/login/ /dev/null '{"username": "dev1", "password": "firstpassword"}')
[ "$code" = "200" ] || fail "login: expected 200, got $code (seeded? see seed_demo)"
CSRF_TOKEN=$(grep csrftoken "$COOKIES" | awk '{print $NF}')

step "3. POST /api/notes/ (write to RDS)"
MARKER="cloud-smoke $(date -u +%Y-%m-%dT%H:%M:%SZ) $RANDOM"
BODY="$(mktemp)"
code=$(post /api/notes/ "$BODY" "{\"text\": \"$MARKER\"}")
[ "$code" = "201" ] || fail "note write: expected 201, got $code: $(cat "$BODY")"
rm -f "$BODY"

step "4. GET /api/notes/?date=today (read the write back from RDS)"
body=$(get '/api/notes/?date=today') || fail "note read: request failed"
grep -qF "$MARKER" <<<"$body" && echo "read back: $MARKER" || fail "note read: the note just written is not in today's notes"

step "5. GET /api/doses/ (seeded history from RDS)"
body=$(get /api/doses/) || fail "doses: request failed"
count=$("$PY" -c "import json,sys; print(len(json.load(sys.stdin)))" <<<"$body" 2>/dev/null)
[ "${count:-0}" -ge 1 ] 2>/dev/null && echo "doses: $count rows" || fail "doses: expected >= 1 row, got '$count'"

step "6. GET /api/timeline/ and /api/adherence/"
# taken_at=now, so the check does not depend on a dose being logged today.
body=$(get "/api/timeline/?taken_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)") || fail "timeline: request failed"
[ "$(json '.computed_by' <<<"$body" 2>/dev/null)" = "backend.pk" ] || fail "timeline: expected computed_by backend.pk"
body=$(get '/api/adherence/?days=14') || fail "adherence: request failed"
[ "$(json '.of' <<<"$body" 2>/dev/null)" = "14" ] || fail "adherence: expected of=14"

echo
if [ "$FAILED" -eq 0 ]; then
    echo "cloud-smoke: all checks passed against $BASE"
    exit 0
else
    echo "cloud-smoke: one or more checks FAILED against $BASE -- see above" >&2
    exit 1
fi
