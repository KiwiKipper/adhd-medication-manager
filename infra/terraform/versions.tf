terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.region

  # Every resource gets these, so the console and the CLI can filter on
  # Project=dose to find everything this stack owns.
  default_tags {
    tags = {
      Project = var.project
      Course  = "COSC349-A2"
    }
  }
}
