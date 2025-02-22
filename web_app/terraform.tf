terraform {
  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = "0.138.0"
    }
  }
}

# Переменные для настройки провайдера Yandex Cloud
variable "zone" {
  default = "ru-central1-a"
}
variable "yc_token" { }
variable "yc_cloud_id" { }
variable "yc_folder_id" { }

provider "yandex" {
  token     = var.yc_token
  cloud_id  = var.yc_cloud_id
  folder_id = var.yc_folder_id
  zone      = var.zone
}

# Получение ID образа Ubuntu 22.04 LTS
data "yandex_compute_image" "ubuntu_image" {
  family = "ubuntu-2204-lts"
}

# Создание виртуальной машины
resource "yandex_compute_instance" "vm" {
  name        = "web-server"
  platform_id = "standard-v1"
  zone        = var.zone

  resources {
    cores  = 2
    memory = 2
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu_image.id
      size     = 20
    }
  }

  network_interface {
    subnet_id = yandex_vpc_subnet.subnet.id
    nat       = true
  }

  metadata = {
    ssh-keys = "ubuntu:${file("~/.ssh/id_rsa.pub")}"
  }
}

# Создание VPC сети
resource "yandex_vpc_network" "network" {
  name = "network"
}

# Создание подсети
resource "yandex_vpc_subnet" "subnet" {
  name           = "subnet"
  zone           = var.zone
  network_id     = yandex_vpc_network.network.id
  v4_cidr_blocks = ["192.168.10.0/24"]
}

# Создание DNS-зоны
resource "yandex_dns_zone" "zone" {
  name        = "vvot03-itiscl-ru"
  zone        = "vvot03.itiscl.ru."
  public      = true
}

# Создание DNS-записи
resource "yandex_dns_recordset" "project_dns" {
  zone_id = yandex_dns_zone.zone.id
  name    = "project.vvot03.itiscl.ru."
  type    = "A"
  ttl     = 300
  data    = [yandex_compute_instance.vm.network_interface[0].nat_ip_address]
}

# Вывод публичного IP адреса
output "public_ip" {
  value = yandex_compute_instance.vm.network_interface[0].nat_ip_address
}