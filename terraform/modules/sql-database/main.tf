data "azurerm_mssql_server" "this" {
  name                = var.server_name
  resource_group_name = var.resource_group_name
}

resource "azurerm_mssql_database" "this" {
  name           = var.name
  server_id      = data.azurerm_mssql_server.this.id
  sku_name       = var.sku_name
  max_size_gb    = var.max_size_gb
  zone_redundant = false
}
