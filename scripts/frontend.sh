#!/bin/bash
set -e

# Provisions the frontend node: nginx serving the built Vue SPA and proxying
# the API paths to gunicorn on the backend VM over the host-only network.
# No data and no Django here -- it's just the browser's entry point.
#
# Safe to rerun: the build and the nginx config are rewritten in place, and
# nginx always restarts so a synced source change takes effect.
#
# curl comes from scripts/common.sh, which runs just before this.

FRONTEND_SRC=/vagrant/frontend
FRONTEND_BUILD=/opt/frontend
DEPLOY=/vagrant/frontend/deploy
BACKEND_URL=http://192.168.56.11:8000

# vite 8 requires node >= 20.19, and 24.04 ships 18 -- so node comes from
# NodeSource rather than the distro.
NODE_MAJOR=22

apt-get install -y nginx

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

# Built from a guest-local copy rather than in place. /vagrant lives on the
# host filesystem, so installing node_modules there is slow, writes tens of
# thousands of files back to the host, and breaks outright on a Windows host
# when a package ships a symlink or a case-conflicting path.
mkdir -p "$FRONTEND_BUILD"
rsync -a --delete \
    --exclude node_modules --exclude dist \
    "$FRONTEND_SRC/" "$FRONTEND_BUILD/"

cd "$FRONTEND_BUILD"
# `npm ci` (not `install`) so the build matches package-lock.json exactly and
# a reprovision cannot silently pick up newer dependencies.
npm ci --no-audit --no-fund
npm run build

install -m 0644 "$DEPLOY/proxy_params_backend" /etc/nginx/proxy_params_backend
install -m 0644 "$DEPLOY/frontend.nginx.conf" /etc/nginx/sites-available/frontend
ln -sf /etc/nginx/sites-available/frontend /etc/nginx/sites-enabled/frontend
# Ubuntu's stock site is a `default_server` on :80 and would otherwise sit
# there serving the nginx welcome page next to ours.
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

# The Vagrantfile boots backend first, but provisioning isn't instant: a
# `vagrant up` of just this node, or a backend reprovision still running, can
# leave the first request arriving before gunicorn listens. So wait.
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

# Fail loudly rather than leave a green `vagrant up` behind a dead site.
# Going through this VM's own nginx, rather than curling the backend again,
# is what proves the whole chain works the way a browser will use it.
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
