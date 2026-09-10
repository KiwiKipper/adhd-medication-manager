#!/bin/bash
set -e

# Provisions the web node: the Django API under gunicorn, with nginx in front
# serving the built Vue SPA and proxying the API paths to it. Unlike pk this
# node is stateful -- it owns the schema on the db VM -- so it also runs
# migrations.
#
# Safe to rerun on every `vagrant provision`: the venv, npm install, systemd
# unit and nginx site are all created only if absent or rewritten in place,
# and `migrate` is a no-op once applied. Both services are always restarted
# so a synced source change actually takes effect.
#
# python3, curl and rsync are assumed installed by provisions/common.sh,
# which the Vagrantfile runs immediately before this script.

VENV=/opt/web/venv
BACKEND=/vagrant/web/backend
FRONTEND_SRC=/vagrant/web/frontend
FRONTEND_BUILD=/opt/web/frontend
DEPLOY=/vagrant/web/deploy

# vite 8 requires node >= 20.19, and 24.04 ships 18 -- so node comes from
# NodeSource rather than the distro.
NODE_MAJOR=22

apt-get install -y python3-venv nginx

# --------------------------------------------------------------------------
# node
# --------------------------------------------------------------------------
# Guarded so a reprovision doesn't re-add the apt source and reinstall node
# every time. `node -v` prints e.g. v22.14.0.
need_node=1
if command -v node > /dev/null 2>&1; then
    current="$(node -v | tr -d 'v' | cut -d. -f1)"
    if [ "$current" -ge "$NODE_MAJOR" ]; then
        need_node=0
        echo "web: node $(node -v) already installed"
    fi
fi
if [ "$need_node" -eq 1 ]; then
    curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
    apt-get install -y nodejs
    echo "web: installed node $(node -v)"
fi

# --------------------------------------------------------------------------
# python environment
# --------------------------------------------------------------------------
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi

"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r /vagrant/web/requirements.txt

# One copy of the settings environment, shared by the gunicorn unit
# (EnvironmentFile) and the manage.py calls below, so they cannot disagree
# about which database they are pointed at. 0640 because it holds the
# database password and the secret key.
install -m 0640 "$DEPLOY/web.env" /etc/web.env

# `set -a` exports everything defined until `set +a`, which is how the same
# systemd-format file gets into this shell's environment.
set -a
# shellcheck disable=SC1091
. /etc/web.env
set +a

# --------------------------------------------------------------------------
# database
# --------------------------------------------------------------------------
# The Vagrantfile brings db up before web, but "the VM booted" is not "the
# postgres inside it is accepting connections", and `migrate` against a
# database that is still starting fails the whole provision.
echo "web: waiting for postgres at $DB_HOST:$DB_PORT"
for attempt in $(seq 1 30); do
    if "$VENV/bin/python" - <<'PY' > /dev/null 2>&1
import os, socket, sys
s = socket.create_connection((os.environ["DB_HOST"], int(os.environ["DB_PORT"])), 2)
s.close()
PY
    then
        echo "web: postgres reachable"
        break
    fi
    if [ "$attempt" -eq 30 ]; then
        echo "web: postgres at $DB_HOST:$DB_PORT never came up -- is the db VM running?" >&2
        exit 1
    fi
    sleep 2
done

cd "$BACKEND"
# Creates every table from the models, and runs the data migrations that seed
# the medication catalogue and its pk components.
"$VENV/bin/python" manage.py migrate --noinput
# DEBUG is off in web.env, so Django will not serve admin/DRF assets itself;
# nginx serves this directory.
"$VENV/bin/python" manage.py collectstatic --noinput

# --------------------------------------------------------------------------
# frontend build
# --------------------------------------------------------------------------
# Built from a guest-local copy rather than in place. /vagrant is a synced
# folder on the host's filesystem: installing node_modules into it is slow,
# writes tens of thousands of files back onto the host, and breaks outright
# when the host is Windows and a package ships a symlink or a
# case-conflicting path.
mkdir -p "$FRONTEND_BUILD"
rsync -a --delete \
    --exclude node_modules --exclude dist \
    "$FRONTEND_SRC/" "$FRONTEND_BUILD/"

cd "$FRONTEND_BUILD"
# `npm ci` (not `install`) so the build matches package-lock.json exactly and
# a reprovision cannot silently pick up newer dependencies.
npm ci --no-audit --no-fund
npm run build

# --------------------------------------------------------------------------
# services
# --------------------------------------------------------------------------
install -m 0644 "$DEPLOY/web.service" /etc/systemd/system/web.service
systemctl daemon-reload
systemctl enable web
systemctl restart web

install -m 0644 "$DEPLOY/proxy_params_web" /etc/nginx/proxy_params_web
install -m 0644 "$DEPLOY/web.nginx.conf" /etc/nginx/sites-available/web
ln -sf /etc/nginx/sites-available/web /etc/nginx/sites-enabled/web
# Ubuntu's stock site is a `default_server` on :80 and would otherwise sit
# there serving the nginx welcome page next to ours.
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

# --------------------------------------------------------------------------
# health check
# --------------------------------------------------------------------------
# Fail loudly rather than leaving a green `vagrant up` behind a dead site.
# /auth/csrf/ is the one endpoint that needs no session, so a 200 from it
# proves nginx, gunicorn, Django and the database are all actually working --
# not just that a port is open.
for attempt in $(seq 1 15); do
    if curl -sf http://127.0.0.1:8000/auth/csrf/ > /dev/null; then
        echo "web: API responded OK on :8000/auth/csrf/"
        if curl -sf http://127.0.0.1:8000/ > /dev/null; then
            echo "web: SPA served OK on :8000/"
            echo "web: open http://localhost:8000 on the host"
            exit 0
        fi
        echo "web: API is up but nginx is not serving the SPA from $FRONTEND_BUILD/dist" >&2
        exit 1
    fi
    sleep 2
done

echo "web: site did not respond on :8000/auth/csrf/ after provisioning" >&2
systemctl status web --no-pager || true
journalctl -u web --no-pager -n 50 || true
systemctl status nginx --no-pager || true
exit 1
