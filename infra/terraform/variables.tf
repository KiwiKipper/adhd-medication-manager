variable "region" {
  description = "AWS region. The Learner Lab only allows us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Prefix for resource names (dose-<role>) and the Project tag."
  type        = string
  default     = "dose"
}

variable "my_ip" {
  description = "Your public IP as a /32 CIDR. The only address allowed to SSH in."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{1,3}(\\.[0-9]{1,3}){3}/32$", var.my_ip))
    error_message = "my_ip must be a single IPv4 address in /32 form, e.g. 203.0.113.7/32."
  }
}

variable "key_name" {
  description = "Name of an existing EC2 key pair, for SSH access to the instances."
  type        = string
  default     = "dose-key"
}

variable "alert_email" {
  description = "Email address that receives late-dose alerts from SNS."
  type        = string
}

variable "git_ref" {
  description = "Branch or tag the instances clone at first boot."
  type        = string
  default     = "cloud/aws-terraform"
}
