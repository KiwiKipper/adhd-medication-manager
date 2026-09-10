#!/bin/bash
set -e

# Runs on every node before that node's own script. Anything here is a
# prerequisite shared by db, pk and web -- node-specific packages belong in
# the node's own script.

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y curl ca-certificates rsync python3 python3-venv python3-pip

# The whole app is time-based -- dose times, onset, wear-off.
# A VM defaulting to UTC will silently shift every timeline by 12/13 hours.
timedatectl set-timezone Pacific/Auckland

# Let the VMs refer to each other by name instead of memorising IPs.
#
# Appending unconditionally would stack up a duplicate block per provision,
# so the whole block is delimited and rewritten in place instead. sed deletes
# any previous copy (no-op on a first run) before the new one is appended.
sed -i '/# BEGIN vagrant nodes/,/# END vagrant nodes/d' /etc/hosts
cat >> /etc/hosts <<'HOSTS'
# BEGIN vagrant nodes
192.168.56.10  db
192.168.56.11  pk
192.168.56.12  web
# END vagrant nodes
HOSTS
