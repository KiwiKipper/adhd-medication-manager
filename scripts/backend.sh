#!/bin/bash
set -e

# Provisions the backend node: the Django API under gunicorn. It owns the
# schema on the db VM, so it runs migrations too, and seeds demo accounts so
# the app has something to show as soon as `vagrant up` finishes (see
# tracker/management/commands/seed_demo.py).
#
# Safe to rerun. The venv and systemd unit are created if absent or rewritten
# in place, migrate is a no-op once applied, and seed_demo skips users that
# already exist. The service always restarts so a synced source change takes
# effect. SEED_RESET=1 wipes and regenerates the demo data instead.
#
# python3 and curl come from scripts/common.sh, which runs just before this.

VENV=/opt/backend/venv
BACKEND=/vagrant/backend
DEPLOY=/vagrant/backend/deploy

apt-get install -y python3-venv

if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi

"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$BACKEND/requirements.txt"

# One copy of the settings environment, shared by the gunicorn unit
# (EnvironmentFile) and the manage.py calls below so they can't disagree
# about which database they point at. 0640 -- it holds the DB password and
# the secret key.
install -m 0640 "$DEPLOY/backend.env" /etc/backend.env

# Load the same file into this shell for the manage.py calls.
#
# Deliberately not `. /etc/backend.env`. That file is in systemd's format,
# where a value is literal text to end of line, but bash would evaluate it as
# shell -- and the secret key alone contains `(`, `!`, `#` and `$`. Reading
# the pairs directly keeps systemd's reading authoritative. Split on the
# first `=` only, so a value containing `=` survives.
while IFS='=' read -r key value; do
    case "$key" in
        ''|\#*) continue ;;
    esac
    export "$key=$value"
done < /etc/backend.env

# The Vagrantfile boots db first, but "the VM booted" isn't "postgres is
# accepting connections", and migrate against a starting database fails the
# whole provision.
echo "backend: waiting for postgres at $DB_HOST:$DB_PORT"
for attempt in $(seq 1 30); do
    if "$VENV/bin/python" - <<'PY' > /dev/null 2>&1
import os, socket, sys
s = socket.create_connection((os.environ["DB_HOST"], int(os.environ["DB_PORT"])), 2)
s.close()
PY
    then
        echo "backend: postgres reachable"
        break
    fi
    if [ "$attempt" -eq 30 ]; then
        echo "backend: postgres at $DB_HOST:$DB_PORT never came up -- is the db VM running?" >&2
        exit 1
    fi
    sleep 2
done

cd "$BACKEND"
# Builds every table, and runs the data migrations that seed the medication
# catalogue and its pk components.
"$VENV/bin/python" manage.py migrate --noinput
# DEBUG is off in backend.env, so Django won't serve admin/DRF assets itself.
# WhiteNoise does, proxied through nginx on the frontend VM.
"$VENV/bin/python" manage.py collectstatic --noinput

# Demo users and history. Idempotent unless SEED_RESET=1, so a routine
# reprovision never wipes what someone logged in the meantime.
if [ "${SEED_RESET:-0}" = "1" ]; then
    "$VENV/bin/python" manage.py seed_demo --reset
else
    "$VENV/bin/python" manage.py seed_demo
fi

install -m 0644 "$DEPLOY/backend.service" /etc/systemd/system/backend.service
systemctl daemon-reload
systemctl enable backend
systemctl restart backend

# Fail loudly rather than leave a green `vagrant up` behind a dead API.
# /auth/csrf/ needs no session, so a 200 proves gunicorn, Django and the
# database all work -- not just that a port is open. Over loopback, since
# whether nginx can reach this VM is the frontend's own health check.
for attempt in $(seq 1 15); do
    if curl -sf http://127.0.0.1:8000/auth/csrf/ > /dev/null; then
        echo "backend: API responded OK on :8000/auth/csrf/"
        echo "backend: log in as admin / password"
        exit 0
    fi
    sleep 2
done

echo "backend: API did not respond on :8000/auth/csrf/ after provisioning" >&2
systemctl status backend --no-pager || true
journalctl -u backend --no-pager -n 50 || true
exit 1
