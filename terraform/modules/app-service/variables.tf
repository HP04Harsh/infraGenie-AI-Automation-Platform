variable "name" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "location" {
  type = string
}
variable "sku_name" {
  type = string
  default = "B1"
}
variable "runtime_stack" {
  type = string
  default = "python"
}
