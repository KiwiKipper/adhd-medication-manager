# Frontend EC2: nginx serving the built Vue SPA and proxying /api, /auth,
# /admin and /static to the backend over its private address. Provisioned by
# the same scripts/common.sh and scripts/frontend.sh that Vagrant runs.

resource "aws_instance" "frontend" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"
  key_name      = var.key_name

  subnet_id                   = local.app_subnet_id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.frontend.id]

  # node_modules plus the Vite build do not fit comfortably in the default
  # 8 GB root volume next to the OS and Node.
  root_block_device {
    volume_size = 12
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/../templates/frontend-userdata.sh.tftpl", {
    git_ref            = var.git_ref
    backend_private_ip = local.backend_private_ip
  })

  user_data_replace_on_change = true

  lifecycle {
    ignore_changes = [ami]
  }

  tags = { Name = "${var.project}-frontend" }
}

output "frontend_url" {
  description = "Where to open the app."
  value       = "http://${aws_instance.frontend.public_dns}"
}
