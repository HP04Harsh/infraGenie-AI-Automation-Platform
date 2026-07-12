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
  type = string
  sensitive = true
}
variable "subnet_id" {
  type = string
}
variable "os_sku" {
  type = string
  default = "2022-Datacenter"
}
