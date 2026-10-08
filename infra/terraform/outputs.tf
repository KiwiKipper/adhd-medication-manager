output "ami_id" {
  description = "Ubuntu 24.04 AMI the instances will use."
  value       = data.aws_ami.ubuntu.id
}

output "ami_name" {
  description = "Name of that AMI, so a plan shows which image was picked."
  value       = data.aws_ami.ubuntu.name
}
