#!/bin/bash
set -e

# Provisions the backend node: the Django API under gunicorn. It owns the
# schema on the db VM, so it also runs migrations, and it seeds two demo
# accounts with history so the app works the moment `vagrant up` finishes --
# see tracker/management/commands/seed_demo.py.
#
# Safe to rerun on every `vagrant provision`: the venv and systemd unit are
# created only if absent or rewritten in place, `migrate` is a no-op once
# applied, and seed_demo skips any demo user that already exists. The
# service is always restarted so a synced source change actually takes
# effect. Set SEED_RESET=1 to wipe and regenerate the demo users' data
# instead (never automatic -- see the seed_demo docstring).
#
# python3 and curl are assumed installed by provisions/common.sh, which the
# Vagrantfile runs immediately before this script.

VENV=/opt/backend/venv
BACKEND=/vagrant/backend
DEPLOY=/vagrant/backend/deploy

apt-get install -y python3-venv

# --------------------------------------------------------------------------
# python environment
# --------------------------------------------------------------------------
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi

"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$BACKEND/requirements.txt"

# One copy of the settings environment, shared by the gunicorn unit
# (EnvironmentFile) and the manage.py calls below, so they cannot disagree
# about which database they are pointed at. 0640 because it holds the
# database password and the secret key.
install -m 0640 "$DEPLOY/backend.env" /etc/backend.env

# Load the same file into this shell so the manage.py calls below see it.
#
# Deliberately NOT `. /etc/backend.env`. The file is in systemd's format,
# where a value is literal text to end of line -- but bash sourcing it would
# evaluate that text as shell, and the secret key alone contains `(`, `!`,
# `#` and `$`. Reading key/value pairs and exporting them directly keeps the
# systemd reading of the file authoritative. Splitting on the first `=` only,
# so a value containing `=` survives intact.
while IFS='=' read -r key value; do
    case "$key" in
        ''|\#*) continue ;;
    esac
    export "$key=$value"
done < /etc/backend.env

# --------------------------------------------------------------------------
# database
# --------------------------------------------------------------------------
# The Vagrantfile brings db up before backend, but "the VM booted" is not
# "the postgres inside it is accepting connections", and `migrate` against a
# database that is still starting fails the whole provision.
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
# Creates every table from the models, and runs the data migrations that seed
# the medication catalogue and its pk components.
"$VENV/bin/python" manage.py migrate --noinput
# DEBUG is off in backend.env, so Django will not serve admin/DRF assets
# itself; WhiteNoise does, proxied through nginx on the frontend VM.
"$VENV/bin/python" manage.py collectstatic --noinput

# --------------------------------------------------------------------------
# demo data
# --------------------------------------------------------------------------
# Out-of-the-box users and history: two accounts, ten days of doses and
# notes each. Idempotent -- an existing demo user is left alone unless
# SEED_RESET=1 is set, so a routine reprovision never wipes what a marker
# has logged in the meantime.
if [ "${SEED_RESET:-0}" = "1" ]; then
    "$VENV/bin/python" manage.py seed_demo --reset
else
    "$VENV/bin/python" manage.py seed_demo
fi

# --------------------------------------------------------------------------
# service
# --------------------------------------------------------------------------
install -m 0644 "$DEPLOY/backend.service" /etc/systemd/system/backend.service
systemctl daemon-reload
systemctl enable backend
systemctl restart backend

# --------------------------------------------------------------------------
# health check
# --------------------------------------------------------------------------
# Fail loudly rather than leaving a green `vagrant up` behind a dead API.
# /auth/csrf/ is the one endpoint that needs no session, so a 200 from it
# proves gunicorn, Django and the database are all actually working -- not
# just that a port is open. Checked over loopback, since gunicorn binds
# 0.0.0.0:8000 on this VM either way; whether the frontend VM's nginx can
# reach this VM's private IP is that VM's own health check to make.
for attempt in $(seq 1 15); do
    if curl -sf http://127.0.0.1:8000/auth/csrf/ > /dev/null; then
        echo "backend: API responded OK on :8000/auth/csrf/"
        echo "backend: demo accounts -- see backend/tracker/management/commands/seed_demo.py"
        exit 0
    fi
    sleep 2
done

echo "backend: API did not respond on :8000/auth/csrf/ after provisioning" >&2
systemctl status backend --no-pager || true
journalctl -u backend --no-pager -n 50 || true
exit 1
