output "vm_name" { value = azurerm_linux_virtual_machine.this.name }
output "public_ip" { value = azurerm_public_ip.this.ip_address }
output "ssh_command" { value = "ssh ${var.admin_username}@${azurerm_public_ip.this.ip_address}" }
output "http_url" { value = "http://${azurerm_public_ip.this.ip_address}" }
