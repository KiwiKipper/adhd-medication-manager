#!/bin/bash
set -e

apt-get update
apt-get install -y postgresql
sudo -u postgres psql -c "CREATE USER adhd WITH PASSWORD 'password';"
sudo -u postgres createdb -O adhd adhd
sudo -u postgres psql adhd -f /vagrant/db/schema.sql

# Let the pk/web VMs reach postgres over the private network instead of
# only the local UNIX socket.
PG_CONF=$(find /etc/postgresql -name postgresql.conf)
PG_HBA=$(find /etc/postgresql -name pg_hba.conf)

sed -i "s/^#listen_addresses.*/listen_addresses = '*'/" "$PG_CONF"
echo "host    adhd    adhd    192.168.56.0/24    md5" >> "$PG_HBA"

systemctl restart postgresql