variable "name" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "location" {
  type = string
}
variable "vm_size" {
  type = string
}
variable "admin_username" {
  type = string
}
variable "admin_password" {
  type    = string
  default = ""
}

variable "ssh_public_key" {
  type    = string
  default = ""
}
variable "subnet_id" {
  type = string
}
variable "image_publisher" {
  type    = string
  default = "Canonical"
}
variable "image_offer" {
  type    = string
  default = "0001-com-ubuntu-server-jammy"
}
variable "image_sku" {
  type    = string
  default = "22_04-lts-gen2"
}
variable "image_version" {
  type    = string
  default = "latest"
}
