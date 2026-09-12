#!/bin/bash
set -e

# Provisions the postgres node. Django owns the schema (migrate on the
# backend VM builds every table), so nothing here defines tables. This only
# creates the role and empty database and opens postgres to the private
# network.
#
# Safe to rerun: the role, database and pg_hba rule are each created only if
# missing. Existing data is never dropped.

# Must match DB_PASSWORD in the backend VM's environment -- see
# backend/deploy/backend.env and backend/config/settings.py.
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
# scram-sha-256 rather than md5, because that's what PG16's default
# password_encryption already stored for the ALTER ROLE above.
HBA_RULE="host    $DB_NAME    $DB_USER    192.168.56.0/24    scram-sha-256"
if ! grep -qF "$HBA_RULE" "$PG_HBA"; then
    echo "$HBA_RULE" >> "$PG_HBA"
fi

systemctl restart postgresql

# Fail loudly rather than leave a green `vagrant up` behind a database the
# backend can't reach. Connecting over the private IP rather than the local
# socket is the point: it exercises listen_addresses, the pg_hba rule and
# scram auth together, the same way Django will.
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
