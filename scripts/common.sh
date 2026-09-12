#!/bin/bash
set -e

# Runs on every node before that node's own script. Shared prerequisites
# only -- node-specific packages belong in db.sh, backend.sh or frontend.sh.

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y curl ca-certificates rsync python3 python3-venv python3-pip

# The whole app is time-based: dose times, onset, wear-off. A VM left on UTC
# silently shifts every timeline by 12-13 hours.
timedatectl set-timezone Pacific/Auckland

# Let the VMs reach each other by name. The block is delimited and rewritten
# in place because appending unconditionally would stack up a copy per
# provision; the sed is a no-op on a first run.
sed -i '/# BEGIN vagrant nodes/,/# END vagrant nodes/d' /etc/hosts
cat >> /etc/hosts <<'HOSTS'
# BEGIN vagrant nodes
192.168.56.10  db
192.168.56.11  backend
192.168.56.12  frontend
# END vagrant nodes
HOSTS
