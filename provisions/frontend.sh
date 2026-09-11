#!/bin/bash
set -e

# Provisions the frontend node: nginx serving the built Vue SPA, proxying
# every API path to gunicorn on the backend VM (192.168.56.11:8000) over the
# host-only network. This node owns no data and runs no Django -- it is
# just the browser's entry point.
#
# Safe to rerun on every `vagrant provision`: npm install, the systemd-managed
# nginx site and its config are all rewritten in place, and nginx is always
# restarted so a synced source change actually takes effect.
#
# python3 and curl are assumed installed by provisions/common.sh, which the
# Vagrantfile runs immediately before this script (python3 isn't actually
# used here, but common.sh installs it on every node for consistency).

FRONTEND_SRC=/vagrant/frontend
FRONTEND_BUILD=/opt/frontend
DEPLOY=/vagrant/frontend/deploy
BACKEND_URL=http://192.168.56.11:8000

# vite 8 requires node >= 20.19, and 24.04 ships 18 -- so node comes from
# NodeSource rather than the distro.
NODE_MAJOR=22

apt-get install -y nginx

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
        echo "frontend: node $(node -v) already installed"
    fi
fi
if [ "$need_node" -eq 1 ]; then
    curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
    apt-get install -y nodejs
    echo "frontend: installed node $(node -v)"
fi

# --------------------------------------------------------------------------
# build
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
# nginx
# --------------------------------------------------------------------------
install -m 0644 "$DEPLOY/proxy_params_backend" /etc/nginx/proxy_params_backend
install -m 0644 "$DEPLOY/frontend.nginx.conf" /etc/nginx/sites-available/frontend
ln -sf /etc/nginx/sites-available/frontend /etc/nginx/sites-enabled/frontend
# Ubuntu's stock site is a `default_server` on :80 and would otherwise sit
# there serving the nginx welcome page next to ours.
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

# --------------------------------------------------------------------------
# health check
# --------------------------------------------------------------------------
# The Vagrantfile brings db and backend up before frontend, but provisioning
# is not instantaneous -- a `vagrant up` of just this node, or a backend
# reprovision still in flight, can leave this VM's first request arriving
# before gunicorn is actually listening. Waited for here rather than failed
# on immediately.
echo "frontend: waiting for the backend API at $BACKEND_URL"
for attempt in $(seq 1 30); do
    if curl -sf "$BACKEND_URL/auth/csrf/" > /dev/null; then
        echo "frontend: backend reachable"
        break
    fi
    if [ "$attempt" -eq 30 ]; then
        echo "frontend: backend at $BACKEND_URL never responded -- is the backend VM running?" >&2
        exit 1
    fi
    sleep 2
done

# Fail loudly rather than leaving a green `vagrant up` behind a dead site.
# Checking /auth/csrf/ *through this VM's own nginx* (not a direct curl at
# the backend, which the step above already did) proves the whole chain --
# nginx, the proxy to the backend VM, gunicorn, Django and the database --
# actually works end to end, which is what a browser on the host will do.
for attempt in $(seq 1 15); do
    if curl -sf http://127.0.0.1/auth/csrf/ > /dev/null; then
        echo "frontend: API reachable through nginx on :80/auth/csrf/"
        if curl -sf http://127.0.0.1/ > /dev/null; then
            echo "frontend: SPA served OK on :80/"
            echo "frontend: open http://localhost:8000 on the host"
            exit 0
        fi
        echo "frontend: API is up but nginx is not serving the SPA from $FRONTEND_BUILD/dist" >&2
        exit 1
    fi
    sleep 2
done

echo "frontend: site did not respond on :80/auth/csrf/ after provisioning" >&2
systemctl status nginx --no-pager || true
exit 1
