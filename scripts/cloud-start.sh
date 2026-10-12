#!/bin/bash
# Starts a deployment stopped by scripts/cloud-stop.sh, waits until it is
# usable and prints the new URL. A stopped instance gets a new public IP and
# DNS name when it starts, so the old URL no longer works.
#
# The database starts first: the backend's gunicorn connects to it lazily,
# so the order only matters for how soon the first request succeeds.
set -euo pipefail

TF_DIR="$(dirname "$0")/../infra/terraform"

db=$(aws rds describe-db-instances --db-instance-identifier dose-db \
    --query "DBInstances[0].DBInstanceStatus" --output text)
if [ "$db" = "stopped" ]; then
    echo "cloud-start: starting RDS dose-db"
    aws rds start-db-instance --db-instance-identifier dose-db > /dev/null
fi

ids=$(aws ec2 describe-instances \
    --filters "Name=tag:Project,Values=dose" "Name=instance-state-name,Values=stopped,stopping,pending,running" \
    --query "Reservations[].Instances[].InstanceId" --output text)
if [ -z "$ids" ]; then
    echo "cloud-start: no dose EC2 instances exist -- run terraform apply instead" >&2
    exit 1
fi
# A stop that is still finishing can't be started yet.
stopping=$(aws ec2 describe-instances --instance-ids $ids \
    --query "Reservations[].Instances[?State.Name=='stopping'].InstanceId" --output text)
[ -n "$stopping" ] && aws ec2 wait instance-stopped --instance-ids $stopping
echo "cloud-start: starting EC2 $ids"
aws ec2 start-instances --instance-ids $ids > /dev/null

echo "cloud-start: waiting for EC2 (about 1 minute) and RDS (several minutes)"
aws ec2 wait instance-running --instance-ids $ids
aws rds wait db-instance-available --db-instance-identifier dose-db

# Pull the new public DNS names into Terraform state so its outputs are
# current. -refresh-only changes no infrastructure.
terraform -chdir="$TF_DIR" apply -refresh-only -auto-approve > /dev/null
url=$(terraform -chdir="$TF_DIR" output -raw frontend_url)
echo "cloud-start: up. The app is at $url"
echo "cloud-start: services take a minute after boot; verify with: bash scripts/cloud-smoke.sh"
