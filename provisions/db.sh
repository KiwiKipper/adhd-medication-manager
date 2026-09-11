#!/bin/bash
set -e

# Provisions the postgres node. Django owns the schema -- `manage.py migrate`
# on the backend VM creates every table from the models in backend/tracker
# and backend/users -- so nothing here defines tables. This script only
# creates the role and the empty database, and opens postgres up to the
# private network.
#
# Safe to rerun on every `vagrant provision`: the role, the database and the
# pg_hba rule are each created only if they aren't already there, so a
# second run is a no-op rather than a failure. Existing data is never
# dropped.

# Must match DB_PASSWORD in the backend VM's gunicorn environment -- see
# provisions/backend.sh and backend/config/settings.py.
DB_NAME=adhd
DB_USER=adhd
DB_PASSWORD=password

apt-get update
apt-get install -y postgresql

psql_su() {
    sudo -u postgres psql -v ON_ERROR_STOP=1 "$@"
}

# `CREATE USER` on an existing role is an error under `set -e`, so ask first.
# The password is set every run regardless, so changing it above and
# reprovisioning actually takes effect.
if psql_su -tAc "SELECT 1 FROM pg_roles WHERE rolname = '$DB_USER'" | grep -q 1; then
    echo "db: role $DB_USER already exists"
else
    psql_su -c "CREATE ROLE $DB_USER WITH LOGIN;"
    echo "db: created role $DB_USER"
fi
psql_su -c "ALTER ROLE $DB_USER WITH PASSWORD '$DB_PASSWORD';"

if psql_su -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1; then
    echo "db: database $DB_NAME already exists"
else
    sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
    echo "db: created database $DB_NAME"
fi

# Let the backend VM reach postgres over the private network instead of
# only the local UNIX socket.
PG_CONF=$(find /etc/postgresql -name postgresql.conf)
PG_HBA=$(find /etc/postgresql -name pg_hba.conf)

sed -i "s/^#\?listen_addresses.*/listen_addresses = '*'/" "$PG_CONF"

# Appending unconditionally would stack up a duplicate rule per provision.
# scram-sha-256, not md5: PG16's own default password_encryption is
# scram-sha-256, so this is what ALTER ROLE ... WITH PASSWORD above already
# stored -- asking for it explicitly here is the stronger of the two
# methods that would otherwise both "work" against a SCRAM-hashed password.
HBA_RULE="host    $DB_NAME    $DB_USER    192.168.56.0/24    scram-sha-256"
if ! grep -qF "$HBA_RULE" "$PG_HBA"; then
    echo "$HBA_RULE" >> "$PG_HBA"
fi

systemctl restart postgresql

# Fail loudly rather than leaving a green `vagrant up` behind a database the
# backend VM can't actually reach. Connecting over the private IP (not the
# local socket) is the point: it exercises listen_addresses, the pg_hba rule
# and scram-sha-256 auth together, which is exactly what Django will do from
# the backend VM.
for attempt in $(seq 1 10); do
    if PGPASSWORD="$DB_PASSWORD" psql -h 192.168.56.10 -U "$DB_USER" -d "$DB_NAME" \
        -tAc "SELECT 1" > /dev/null 2>&1; then
        echo "db: $DB_NAME reachable as $DB_USER over the private network"
        exit 0
    fi
    sleep 1
done

echo "db: could not connect to $DB_NAME as $DB_USER on 192.168.56.10 after provisioning" >&2
systemctl status postgresql --no-pager || true
exit 1
