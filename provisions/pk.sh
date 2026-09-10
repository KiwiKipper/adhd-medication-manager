#!/bin/bash
set -e

# Provisions the pk service: a stateless calculator with no database, no
# auth and no persistence. Safe to rerun on every `vagrant provision` --
# venv creation, pip install and the systemd unit are all idempotent, and
# the unit is always restarted so a redeployed source change (e.g. editing
# pk/config.py) actually takes effect rather than requiring a manual
# `systemctl restart` after every sync.
#
# python3 and general packages are assumed already installed by
# provisions/common.sh, which the Vagrantfile runs immediately before this
# script on every provision.

apt-get install -y python3-venv

VENV=/opt/pk/venv
PROJECT=/vagrant/pk

if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi

"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$PROJECT/requirements.txt"

install -m 0644 "$PROJECT/deploy/pk.service" /etc/systemd/system/pk.service

systemctl daemon-reload
systemctl enable pk
systemctl restart pk

# Fail loudly rather than leaving a green `vagrant up` with a dead service.
for attempt in $(seq 1 10); do
    if curl -sf http://127.0.0.1:8001/health > /dev/null; then
        echo "pk: /health responded OK"
        exit 0
    fi
    sleep 1
done

echo "pk: service did not respond on :8001/health after provisioning" >&2
systemctl status pk --no-pager || true
journalctl -u pk --no-pager -n 50 || true
exit 1
