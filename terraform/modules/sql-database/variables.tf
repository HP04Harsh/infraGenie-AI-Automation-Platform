variable "name" {
  type = string
}
variable "server_name" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "sku_name" {
  type = string
  default = "S0"
}
variable "max_size_gb" {
  type = number
  default = 50
}
