#!/bin/bash
set -e

apt-get update
apt-get install -y curl ca-certificates python3 python3-venv python3-pip

# The whole app is time-based -- dose times, onset, wear-off.
# A VM defaulting to UTC will silently shift every timeline by 12/13 hours.
timedatectl set-timezone Pacific/Auckland

# Let the VMs refer to each other by name instead of memorising IPs.
cat >> /etc/hosts <<'EOF'
192.168.56.10  db
192.168.56.11  pk
192.168.56.12  web
EOF