# Looked up rather than created: the Learner Lab account already has a default
# VPC with a public subnet per availability zone (data-source pattern from
# COSC349 Lab 3).
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }

  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# Ubuntu 24.04 LTS, matching the Vagrant boxes. Looked up by name from
# Canonical's account (099720109477) so no AMI ID is hard-coded and the stack
# builds in any account.
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
