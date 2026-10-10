# Backend EC2: gunicorn + Django, provisioned at first boot by the same
# scripts/common.sh and scripts/backend.sh that Vagrant runs.

# Both instances live in the first default subnet. The backend gets a fixed
# private address inside it so the frontend's nginx can be told where to send
# requests without Terraform having to read the backend instance's address
# (which would make the two instances depend on each other).
data "aws_subnet" "app" {
  id = sort(data.aws_subnets.default.ids)[0]
}

locals {
  app_subnet_id      = data.aws_subnet.app.id
  backend_private_ip = cidrhost(data.aws_subnet.app.cidr_block, 20)
}

resource "random_password" "django_secret" {
  length  = 50
  special = false
}

resource "aws_instance" "backend" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"
  key_name      = var.key_name

  subnet_id                   = local.app_subnet_id
  private_ip                  = local.backend_private_ip
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.backend.id]

  # The Learner Lab does not allow creating IAM roles, so use the lab's own
  # instance profile. The AWS SDK on the instance fetches short-lived
  # credentials from it, so no keys are stored on disk.
  iam_instance_profile = "LabInstanceProfile"

  user_data = templatefile("${path.module}/../templates/backend-userdata.sh.tftpl", {
    git_ref            = var.git_ref
    db_host            = aws_db_instance.db.address
    db_password        = random_password.db.result
    secret_key         = random_password.django_secret.result
    backend_private_ip = local.backend_private_ip
  })

  # user_data only runs on first boot, so a changed template must replace
  # the instance to take effect.
  user_data_replace_on_change = true

  # `most_recent` on the AMI lookup would otherwise replace both instances
  # whenever Canonical publishes a new image.
  lifecycle {
    ignore_changes = [ami]
  }

  tags = { Name = "${var.project}-backend" }
}

output "backend_public_dns" {
  description = "Backend public DNS name, for SSH only (port 8000 is not open to the internet)."
  value       = aws_instance.backend.public_dns
}

output "backend_private_ip" {
  description = "Backend address inside the VPC; the frontend proxies to this."
  value       = local.backend_private_ip
}
