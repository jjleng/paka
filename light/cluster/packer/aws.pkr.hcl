packer {
  required_plugins {
    amazon = {
      source  = "github.com/hashicorp/amazon"
      version = "~> 1"
    }
  }
}

locals {
  timestamp = regex_replace(timestamp(), "[- TZ:]", "")
}

variable "region" {
  type = string
}

data "amazon-ami" "nomad" {
  filters = {
    architecture        = "x86_64"
    name                = "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"
    root-device-type    = "ebs"
    virtualization-type = "hvm"
  }
  most_recent = true
  owners      = ["099720109477"]
  region      = var.region
}


source "amazon-ebs" "nomad" {
  ami_name              = "nomad-${local.timestamp}"
  instance_type         = "t2.medium"
  region                = var.region
  source_ami            = "${data.amazon-ami.nomad.id}"
  ssh_username          = "ubuntu"
  force_deregister      = true
  force_delete_snapshot = true

  tags = {
    Name          = "nomad"
    Base_AMI_ID   = "{{ .SourceAMI }}"
    Base_AMI_Name = "{{ .SourceAMIName }}"
  }

  snapshot_tags = {
    Name = "nomad"
  }
}

build {
  sources = ["source.amazon-ebs.nomad"]

  provisioner "shell" {
    inline = ["sudo mkdir -p /ops/shared", "sudo chmod 777 -R /ops"]
  }

  provisioner "file" {
    destination = "/ops"
    source      = "./shared"
  }

  provisioner "shell" {
    environment_vars = ["CLOUD_ENV=aws"]
    script           = "./shared/scripts/setup.sh"
  }

}