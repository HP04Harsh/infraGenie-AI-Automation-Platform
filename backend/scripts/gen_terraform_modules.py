"""Generate Terraform modules under /app/terraform/modules/.

Idempotent — safe to re-run.
Produces, for each module: main.tf, variables.tf, outputs.tf, versions.tf, README.md, terraform.tfvars.example
"""
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[2] / "terraform" / "modules"
ROOT.mkdir(parents=True, exist_ok=True)

VERSIONS = dedent("""\
    terraform {
      required_providers {
        azurerm = {
          source  = "hashicorp/azurerm"
          version = "~> 3.100"
        }
        random = {
          source  = "hashicorp/random"
          version = "~> 3.6"
        }
      }
      required_version = ">= 1.5.0"
    }
""")

# Helper to render variable blocks properly
def V(*args):
    """Render a single variable block. args=(name, type, ?default, ?sensitive)."""
    lines = [f'variable "{args[0]}" {{']
    lines.append(f'  type = {args[1]}')
    if len(args) >= 3 and args[2] is not None:
        lines.append(f'  default = {args[2]}')
    if len(args) >= 4 and args[3]:
        lines.append('  sensitive = true')
    lines.append('}')
    return "\n".join(lines) + "\n"

MODULES = {}

# ---------------- resource-group ----------------
MODULES["resource-group"] = {
    "main": dedent("""\
        resource "azurerm_resource_group" "this" {
          name     = var.name
          location = var.location
          tags     = var.tags
        }
    """),
    "variables": dedent("""\
        variable "name"     { type = string }
        variable "location" { type = string }
        variable "tags"     { type = map(string) default = {} }
    """),
    "outputs": dedent("""\
        output "id"       { value = azurerm_resource_group.this.id }
        output "name"     { value = azurerm_resource_group.this.name }
        output "location" { value = azurerm_resource_group.this.location }
    """),
    "tfvars_example": 'name     = "rg-prod-app"\nlocation = "centralindia"\ntags     = { env = "prod" }\n',
    "readme": "# Resource Group\n\nLogical grouping of Azure resources sharing the same lifecycle.\n",
}

# ---------------- virtual-machine-linux ----------------
MODULES["virtual-machine-linux"] = {
    "main": dedent("""\
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

        resource "azurerm_linux_virtual_machine" "this" {
          name                            = var.name
          location                        = var.location
          resource_group_name             = var.resource_group_name
          size                            = var.vm_size
          admin_username                  = var.admin_username
          network_interface_ids           = [azurerm_network_interface.this.id]
          disable_password_authentication = true

          admin_ssh_key {
            username   = var.admin_username
            public_key = var.ssh_public_key
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
    """),
    "variables": dedent("""\
        variable "name"                { type = string }
        variable "resource_group_name" { type = string }
        variable "location"            { type = string }
        variable "vm_size"             { type = string }
        variable "admin_username"      { type = string }
        variable "ssh_public_key"      { type = string }
        variable "subnet_id"           { type = string }
        variable "image_publisher"     { type = string default = "Canonical" }
        variable "image_offer"         { type = string default = "0001-com-ubuntu-server-jammy" }
        variable "image_sku"           { type = string default = "22_04-lts-gen2" }
        variable "image_version"       { type = string default = "latest" }
    """),
    "outputs": dedent("""\
        output "id"          { value = azurerm_linux_virtual_machine.this.id }
        output "private_ip"  { value = azurerm_network_interface.this.private_ip_address }
        output "name"        { value = azurerm_linux_virtual_machine.this.name }
    """),
    "tfvars_example": 'name="vm-prod-app-01"\nresource_group_name="rg-prod-app"\nlocation="centralindia"\nvm_size="Standard_B2s"\nadmin_username="azureuser"\nssh_public_key="ssh-rsa AAAA..."\nsubnet_id="/subscriptions/.../subnets/default"\n',
    "readme": "# Linux Virtual Machine\n\nUbuntu 22.04 LTS VM with managed identity-ready NIC.\n",
}

# ---------------- virtual-machine-windows ----------------
MODULES["virtual-machine-windows"] = {
    "main": dedent("""\
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

        resource "azurerm_windows_virtual_machine" "this" {
          name                = var.name
          location            = var.location
          resource_group_name = var.resource_group_name
          size                = var.vm_size
          admin_username      = var.admin_username
          admin_password      = var.admin_password
          network_interface_ids = [azurerm_network_interface.this.id]

          os_disk {
            caching              = "ReadWrite"
            storage_account_type = "Standard_LRS"
          }

          source_image_reference {
            publisher = "MicrosoftWindowsServer"
            offer     = "WindowsServer"
            sku       = var.os_sku
            version   = "latest"
          }
        }
    """),
    "variables": dedent("""\
        variable "name"                { type = string }
        variable "resource_group_name" { type = string }
        variable "location"            { type = string }
        variable "vm_size"             { type = string }
        variable "admin_username"      { type = string }
        variable "admin_password"      { type = string sensitive = true }
        variable "subnet_id"           { type = string }
        variable "os_sku"              { type = string default = "2022-Datacenter" }
    """),
    "outputs": dedent("""\
        output "id"   { value = azurerm_windows_virtual_machine.this.id }
        output "name" { value = azurerm_windows_virtual_machine.this.name }
    """),
    "tfvars_example": 'name="vm-prod-win-01"\nresource_group_name="rg-prod-app"\nlocation="centralindia"\nvm_size="Standard_D2s_v5"\nadmin_username="azureadmin"\nadmin_password="REPLACE_ME"\nsubnet_id="..."\n',
    "readme": "# Windows Virtual Machine\n\nWindows Server 2022 Datacenter VM.\n",
}

# ---------------- storage-account ----------------
MODULES["storage-account"] = {
    "main": dedent("""\
        resource "azurerm_storage_account" "this" {
          name                     = var.name
          resource_group_name      = var.resource_group_name
          location                 = var.location
          account_tier             = var.account_tier
          account_replication_type = var.replication_type
          min_tls_version          = "TLS1_2"
          tags                     = var.tags
        }
    """),
    "variables": dedent("""\
        variable "name"                { type = string }
        variable "resource_group_name" { type = string }
        variable "location"            { type = string }
        variable "account_tier"        { type = string default = "Standard" }
        variable "replication_type"    { type = string default = "LRS" }
        variable "tags"                { type = map(string) default = {} }
    """),
    "outputs": dedent("""\
        output "id"                  { value = azurerm_storage_account.this.id }
        output "name"                { value = azurerm_storage_account.this.name }
        output "primary_blob_endpoint" { value = azurerm_storage_account.this.primary_blob_endpoint }
    """),
    "tfvars_example": 'name="stprodapp001"\nresource_group_name="rg-prod-app"\nlocation="centralindia"\naccount_tier="Standard"\nreplication_type="LRS"\n',
    "readme": "# Storage Account\n\nBlob, file, queue, and table storage.\n",
}

# ---------------- virtual-network ----------------
MODULES["virtual-network"] = {
    "main": dedent("""\
        resource "azurerm_virtual_network" "this" {
          name                = var.name
          location            = var.location
          resource_group_name = var.resource_group_name
          address_space       = var.address_space
          tags                = var.tags
        }
    """),
    "variables": dedent("""\
        variable "name"                { type = string }
        variable "resource_group_name" { type = string }
        variable "location"            { type = string }
        variable "address_space"       { type = list(string) }
        variable "tags"                { type = map(string) default = {} }
    """),
    "outputs": dedent("""\
        output "id"   { value = azurerm_virtual_network.this.id }
        output "name" { value = azurerm_virtual_network.this.name }
    """),
    "tfvars_example": 'name="vnet-prod"\nresource_group_name="rg-prod-app"\nlocation="centralindia"\naddress_space=["10.0.0.0/16"]\n',
    "readme": "# Virtual Network\n\nIsolated VNet with custom address space.\n",
}

# ---------------- subnet ----------------
MODULES["subnet"] = {
    "main": dedent("""\
        resource "azurerm_subnet" "this" {
          name                 = var.name
          resource_group_name  = var.resource_group_name
          virtual_network_name = var.virtual_network_name
          address_prefixes     = [var.address_prefix]
        }
    """),
    "variables": dedent("""\
        variable "name"                 { type = string }
        variable "resource_group_name"  { type = string }
        variable "virtual_network_name" { type = string }
        variable "address_prefix"       { type = string }
    """),
    "outputs": dedent("""\
        output "id"   { value = azurerm_subnet.this.id }
        output "name" { value = azurerm_subnet.this.name }
    """),
    "tfvars_example": 'name="default"\nresource_group_name="rg-prod-app"\nvirtual_network_name="vnet-prod"\naddress_prefix="10.0.1.0/24"\n',
    "readme": "# Subnet\n\nSubnet within an existing VNet.\n",
}

# ---------------- network-security-group ----------------
MODULES["network-security-group"] = {
    "main": dedent("""\
        resource "azurerm_network_security_group" "this" {
          name                = var.name
          location            = var.location
          resource_group_name = var.resource_group_name

          dynamic "security_rule" {
            for_each = var.rules
            content {
              name                       = security_rule.value.name
              priority                   = security_rule.value.priority
              direction                  = security_rule.value.direction
              access                     = security_rule.value.access
              protocol                   = security_rule.value.protocol
              source_port_range          = security_rule.value.source_port_range
              destination_port_range     = security_rule.value.destination_port_range
              source_address_prefix      = security_rule.value.source_address_prefix
              destination_address_prefix = security_rule.value.destination_address_prefix
            }
          }
        }
    """),
    "variables": dedent("""\
        variable "name"                { type = string }
        variable "resource_group_name" { type = string }
        variable "location"            { type = string }
        variable "rules" {
          type    = list(any)
          default = []
        }
    """),
    "outputs": dedent("""\
        output "id"   { value = azurerm_network_security_group.this.id }
        output "name" { value = azurerm_network_security_group.this.name }
    """),
    "tfvars_example": 'name="nsg-prod"\nresource_group_name="rg-prod-app"\nlocation="centralindia"\n',
    "readme": "# Network Security Group\n\nInbound/outbound rules attached to subnets or NICs.\n",
}

# ---------------- sql-server ----------------
MODULES["sql-server"] = {
    "main": dedent("""\
        resource "azurerm_mssql_server" "this" {
          name                         = var.name
          resource_group_name          = var.resource_group_name
          location                     = var.location
          version                      = "12.0"
          administrator_login          = var.administrator_login
          administrator_login_password = var.administrator_password
          minimum_tls_version          = "1.2"
        }
    """),
    "variables": dedent("""\
        variable "name"                   { type = string }
        variable "resource_group_name"    { type = string }
        variable "location"               { type = string }
        variable "administrator_login"    { type = string }
        variable "administrator_password" { type = string sensitive = true }
    """),
    "outputs": dedent("""\
        output "id"   { value = azurerm_mssql_server.this.id }
        output "name" { value = azurerm_mssql_server.this.name }
    """),
    "tfvars_example": 'name="sql-prod-srv-01"\nresource_group_name="rg-prod-app"\nlocation="centralindia"\nadministrator_login="sqladmin"\nadministrator_password="REPLACE_ME"\n',
    "readme": "# SQL Server\n\nLogical SQL Server to host databases.\n",
}

# ---------------- sql-database ----------------
MODULES["sql-database"] = {
    "main": dedent("""\
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
    """),
    "variables": dedent("""\
        variable "name"                { type = string }
        variable "server_name"         { type = string }
        variable "resource_group_name" { type = string }
        variable "sku_name"            { type = string default = "S0" }
        variable "max_size_gb"         { type = number default = 50 }
    """),
    "outputs": dedent("""\
        output "id"   { value = azurerm_mssql_database.this.id }
        output "name" { value = azurerm_mssql_database.this.name }
    """),
    "tfvars_example": 'name="db-reporting"\nserver_name="sql-prod-srv-01"\nresource_group_name="rg-prod-app"\nsku_name="S0"\nmax_size_gb=50\n',
    "readme": "# SQL Database\n\nManaged relational database on a SQL Server.\n",
}

# ---------------- app-service ----------------
MODULES["app-service"] = {
    "main": dedent("""\
        resource "azurerm_service_plan" "this" {
          name                = "${var.name}-plan"
          resource_group_name = var.resource_group_name
          location            = var.location
          os_type             = "Linux"
          sku_name            = var.sku_name
        }

        resource "azurerm_linux_web_app" "this" {
          name                = var.name
          resource_group_name = var.resource_group_name
          location            = var.location
          service_plan_id     = azurerm_service_plan.this.id

          site_config {
            application_stack {
              python_version = var.runtime_stack == "python" ? "3.11" : null
              node_version   = var.runtime_stack == "node"   ? "20-lts" : null
            }
          }
        }
    """),
    "variables": dedent("""\
        variable "name"                { type = string }
        variable "resource_group_name" { type = string }
        variable "location"            { type = string }
        variable "sku_name"            { type = string default = "B1" }
        variable "runtime_stack"       { type = string default = "python" }
    """),
    "outputs": dedent("""\
        output "id"           { value = azurerm_linux_web_app.this.id }
        output "default_hostname" { value = azurerm_linux_web_app.this.default_hostname }
    """),
    "tfvars_example": 'name="app-prod-api"\nresource_group_name="rg-prod-app"\nlocation="centralindia"\nsku_name="B1"\nruntime_stack="python"\n',
    "readme": "# App Service\n\nManaged Linux web app with App Service plan.\n",
}

# ---------------- key-vault ----------------
MODULES["key-vault"] = {
    "main": dedent("""\
        data "azurerm_client_config" "current" {}

        resource "azurerm_key_vault" "this" {
          name                       = var.name
          location                   = var.location
          resource_group_name        = var.resource_group_name
          tenant_id                  = data.azurerm_client_config.current.tenant_id
          sku_name                   = var.sku_name
          purge_protection_enabled   = false
          soft_delete_retention_days = 7
        }
    """),
    "variables": dedent("""\
        variable "name"                { type = string }
        variable "resource_group_name" { type = string }
        variable "location"            { type = string }
        variable "sku_name"            { type = string default = "standard" }
    """),
    "outputs": dedent("""\
        output "id"   { value = azurerm_key_vault.this.id }
        output "vault_uri" { value = azurerm_key_vault.this.vault_uri }
    """),
    "tfvars_example": 'name="kv-prod-secrets-01"\nresource_group_name="rg-prod-app"\nlocation="centralindia"\nsku_name="standard"\n',
    "readme": "# Key Vault\n\nSecure secret/key/certificate storage.\n",
}

# ---------------- function-app ----------------
MODULES["function-app"] = {
    "main": dedent("""\
        data "azurerm_storage_account" "this" {
          name                = var.storage_account_name
          resource_group_name = var.resource_group_name
        }

        resource "azurerm_service_plan" "this" {
          name                = "${var.name}-plan"
          resource_group_name = var.resource_group_name
          location            = var.location
          os_type             = "Linux"
          sku_name            = "Y1"
        }

        resource "azurerm_linux_function_app" "this" {
          name                       = var.name
          resource_group_name        = var.resource_group_name
          location                   = var.location
          service_plan_id            = azurerm_service_plan.this.id
          storage_account_name       = data.azurerm_storage_account.this.name
          storage_account_access_key = data.azurerm_storage_account.this.primary_access_key

          site_config {
            application_stack {
              python_version = var.runtime_stack == "python" ? "3.11" : null
              node_version   = var.runtime_stack == "node"   ? "20"     : null
            }
          }
        }
    """),
    "variables": dedent("""\
        variable "name"                 { type = string }
        variable "resource_group_name"  { type = string }
        variable "location"             { type = string }
        variable "storage_account_name" { type = string }
        variable "runtime_stack"        { type = string default = "python" }
    """),
    "outputs": dedent("""\
        output "id"   { value = azurerm_linux_function_app.this.id }
        output "default_hostname" { value = azurerm_linux_function_app.this.default_hostname }
    """),
    "tfvars_example": 'name="fn-prod-worker"\nresource_group_name="rg-prod-app"\nlocation="centralindia"\nstorage_account_name="stprodapp001"\nruntime_stack="python"\n',
    "readme": "# Function App\n\nServerless event-driven compute on Linux consumption plan.\n",
}

# ---------------- load-balancer ----------------
MODULES["load-balancer"] = {
    "main": dedent("""\
        resource "azurerm_public_ip" "lb" {
          name                = "${var.name}-pip"
          location            = var.location
          resource_group_name = var.resource_group_name
          allocation_method   = "Static"
          sku                 = "Standard"
        }

        resource "azurerm_lb" "this" {
          name                = var.name
          location            = var.location
          resource_group_name = var.resource_group_name
          sku                 = var.sku
          frontend_ip_configuration {
            name                 = "front"
            public_ip_address_id = azurerm_public_ip.lb.id
          }
        }
    """),
    "variables": dedent("""\
        variable "name"                { type = string }
        variable "resource_group_name" { type = string }
        variable "location"            { type = string }
        variable "sku"                 { type = string default = "Standard" }
    """),
    "outputs": dedent("""\
        output "id"          { value = azurerm_lb.this.id }
        output "public_ip"   { value = azurerm_public_ip.lb.ip_address }
    """),
    "tfvars_example": 'name="lb-prod"\nresource_group_name="rg-prod-app"\nlocation="centralindia"\nsku="Standard"\n',
    "readme": "# Load Balancer\n\nStandard SKU LB with a static public frontend IP.\n",
}

# ---------------- public-ip ----------------
MODULES["public-ip"] = {
    "main": dedent("""\
        resource "azurerm_public_ip" "this" {
          name                = var.name
          location            = var.location
          resource_group_name = var.resource_group_name
          allocation_method   = var.allocation_method
          sku                 = "Standard"
        }
    """),
    "variables": dedent("""\
        variable "name"                { type = string }
        variable "resource_group_name" { type = string }
        variable "location"            { type = string }
        variable "allocation_method"   { type = string default = "Static" }
    """),
    "outputs": dedent("""\
        output "id"        { value = azurerm_public_ip.this.id }
        output "ip_address"{ value = azurerm_public_ip.this.ip_address }
    """),
    "tfvars_example": 'name="pip-prod-01"\nresource_group_name="rg-prod-app"\nlocation="centralindia"\nallocation_method="Static"\n',
    "readme": "# Public IP\n\nStandard SKU public IP.\n",
}

# ---------------- managed-identity ----------------
MODULES["managed-identity"] = {
    "main": dedent("""\
        resource "azurerm_user_assigned_identity" "this" {
          name                = var.name
          resource_group_name = var.resource_group_name
          location            = var.location
        }
    """),
    "variables": dedent("""\
        variable "name"                { type = string }
        variable "resource_group_name" { type = string }
        variable "location"            { type = string }
    """),
    "outputs": dedent("""\
        output "id"           { value = azurerm_user_assigned_identity.this.id }
        output "principal_id" { value = azurerm_user_assigned_identity.this.principal_id }
        output "client_id"    { value = azurerm_user_assigned_identity.this.client_id }
    """),
    "tfvars_example": 'name="mi-prod-app"\nresource_group_name="rg-prod-app"\nlocation="centralindia"\n',
    "readme": "# Managed Identity\n\nUser-assigned identity for Azure resources.\n",
}


def write(key: str, contents: dict):
    folder = ROOT / key
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "main.tf").write_text(contents["main"])
    (folder / "variables.tf").write_text(contents["variables"])
    (folder / "outputs.tf").write_text(contents["outputs"])
    (folder / "versions.tf").write_text(VERSIONS)
    (folder / "terraform.tfvars.example").write_text(contents["tfvars_example"])
    (folder / "README.md").write_text(contents["readme"])


def main():
    for key, contents in MODULES.items():
        write(key, contents)
    print(f"Wrote {len(MODULES)} modules to {ROOT}")


if __name__ == "__main__":
    main()
