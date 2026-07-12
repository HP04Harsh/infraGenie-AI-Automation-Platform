resource "azurerm_network_interface" "this" {
  name                = "${var.name}-nic"
  location            = var.location
  resource_group_name = var.resource_group_name

  ip_configuration {
    name                          = "primary"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "random_password" "fallback" {
  count   = var.admin_password == "" && var.ssh_public_key == "" ? 1 : 0
  length  = 32
  special = false
}

resource "azurerm_linux_virtual_machine" "this" {
  name                            = var.name
  location                        = var.location
  resource_group_name             = var.resource_group_name
  size                            = var.vm_size
  admin_username                  = var.admin_username
  network_interface_ids           = [azurerm_network_interface.this.id]
  disable_password_authentication = var.ssh_public_key != "" ? true : false

  admin_password = var.admin_password != "" ? var.admin_password : (
    var.ssh_public_key != "" ? null : random_password.fallback[0].result
  )

  dynamic "admin_ssh_key" {
    for_each = var.ssh_public_key == "" ? [] : [1]
    content {
      username   = var.admin_username
      public_key = var.ssh_public_key
    }
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = var.image_publisher
    offer     = var.image_offer
    sku       = var.image_sku
    version   = var.image_version
  }
}
