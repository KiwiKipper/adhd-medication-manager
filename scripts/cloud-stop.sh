#!/bin/bash
# Stops the AWS deployment without deleting anything: both dose-* EC2
# instances and the dose-db RDS instance. Compute stops billing; EBS volumes,
# RDS storage and its backups are kept (and still billed), so all data
# survives. Start it again with scripts/cloud-start.sh.
#
# AWS restarts a stopped RDS instance by itself after 7 days.
set -euo pipefail

ids=$(aws ec2 describe-instances \
    --filters "Name=tag:Project,Values=dose" "Name=instance-state-name,Values=pending,running" \
    --query "Reservations[].Instances[].InstanceId" --output text)
if [ -n "$ids" ]; then
    echo "cloud-stop: stopping EC2 $ids"
    aws ec2 stop-instances --instance-ids $ids > /dev/null
else
    echo "cloud-stop: no running dose EC2 instances"
fi

db=$(aws rds describe-db-instances --db-instance-identifier dose-db \
    --query "DBInstances[0].DBInstanceStatus" --output text)
if [ "$db" = "available" ]; then
    echo "cloud-stop: stopping RDS dose-db"
    aws rds stop-db-instance --db-instance-identifier dose-db > /dev/null
else
    echo "cloud-stop: RDS dose-db is '$db', leaving it"
fi

if [ -n "$ids" ]; then
    aws ec2 wait instance-stopped --instance-ids $ids
    echo "cloud-stop: EC2 instances stopped"
fi
echo "cloud-stop: RDS stops in a few minutes (check: aws rds describe-db-instances --db-instance-identifier dose-db)"
