"""InfraGenie AI Provisioning Agent — orchestration service.

Owns:
  - Resource catalog (15 Terraform modules)
  - Multi-turn AI conversation (intent classification + tfvar collection)
  - Real cost estimation via pricing_service
  - Cloud-init generation for common workloads
  - Dependency graph for resource planning
  - Demo-mode Terraform plan/cost/apply (AI-generated, realistic, dynamic)
  - Ticket creation tied to each operation
"""
from __future__ import annotations

import json
import os
import re
import uuid
import shutil
import logging
import random
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ai_provider_service import chat_json, parse_json_response
from pricing_service import estimate_cost as _pricing_estimate_cost

try:
    from infracost_service import estimate_with_infracost
except ImportError:
    async def estimate_with_infracost(tf_dir, module_key, tfvars):
        return None

logger = logging.getLogger("provisioning")

ROOT = Path(__file__).parent
TERRAFORM_ROOT = ROOT / "terraform"
MODULES_DIR = TERRAFORM_ROOT / "modules"
RUNTIME_DIR = TERRAFORM_ROOT / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------
# Resource Catalog — 15 modules
# ----------------------------------------------------------------------
# Each entry maps to a folder in /app/terraform/modules/{module_key}/
# `required_vars` drives the AI follow-up question loop.

CATALOG: List[Dict[str, Any]] = [
    {
        "key": "linux-vm-nginx",
        "label": "Linux VM with NGINX (all-in-one)",
        "category": "Compute",
        "icon": "server",
        "accent": "emerald",
        "description": "Complete stack: RG, VNet, Subnet, NSG (SSH+HTTP), Public IP, NIC, Ubuntu VM with NGINX preinstalled via cloud-init. Supports password OR SSH key auth.",
        "popular": True,
        "required_vars": [
            {"name": "name",                "label": "VM name",              "type": "string", "example": "web01"},
            {"name": "resource_group_name", "label": "Resource group",       "type": "string", "example": "rg-infragenie-test"},
            {"name": "location",            "label": "Azure region",         "type": "azure_region", "example": "centralindia"},
            {"name": "vm_size",             "label": "VM size",              "type": "vm_size", "example": "Standard_B2s"},
            {"name": "admin_username",      "label": "Admin username",       "type": "string", "example": "azureuser"},
            {"name": "admin_password",      "label": "Admin password",       "type": "secret", "optional": True},
            {"name": "ssh_public_key",      "label": "SSH public key",       "type": "ssh_pub", "optional": True},
        ],
    },
    {
        "key": "resource-group",
        "label": "Resource Group",
        "category": "Foundation",
        "icon": "folder",
        "accent": "slate",
        "description": "Logical container that groups Azure resources sharing the same lifecycle.",
        "popular": False,
        "required_vars": [
            {"name": "name",     "label": "Resource group name",                "type": "string", "example": "rg-prod-app"},
            {"name": "location", "label": "Azure region",                       "type": "azure_region", "example": "centralindia"},
            {"name": "tags",     "label": "Tags (optional, comma key=value)",   "type": "tags",   "optional": True},
        ],
    },
    {
        "key": "virtual-machine-linux",
        "label": "Linux Virtual Machine",
        "category": "Compute",
        "icon": "server",
        "accent": "indigo",
        "description": "Linux compute instance with managed identity and OS disk. Supports password OR SSH key auth.",
        "popular": True,
        "required_vars": [
            {"name": "name",                 "label": "VM name",            "type": "string", "example": "vm-prod-app-01"},
            {"name": "resource_group_name",  "label": "Resource group",     "type": "string", "example": "rg-prod-app"},
            {"name": "location",             "label": "Azure region",       "type": "azure_region", "example": "centralindia"},
            {"name": "vm_size",              "label": "VM size",            "type": "vm_size", "example": "Standard_B2s"},
            {"name": "admin_username",       "label": "Admin username",     "type": "string", "example": "azureuser"},
            {"name": "os_image",             "label": "OS image",           "type": "os_image_linux", "example": "Ubuntu 22.04 LTS"},
            {"name": "admin_password",       "label": "Admin password",     "type": "secret", "optional": True},
            {"name": "ssh_public_key",       "label": "SSH public key",     "type": "ssh_pub", "example": "ssh-rsa AAAA...", "optional": True},
            {"name": "subnet_id",            "label": "Subnet ID (optional)","type": "string", "optional": True},
        ],
    },
    {
        "key": "virtual-machine-windows",
        "label": "Windows Virtual Machine",
        "category": "Compute",
        "icon": "server",
        "accent": "indigo",
        "description": "Windows Server compute instance with managed identity.",
        "popular": False,
        "required_vars": [
            {"name": "name",                 "label": "VM name",            "type": "string", "example": "vm-prod-win-01"},
            {"name": "resource_group_name",  "label": "Resource group",     "type": "string"},
            {"name": "location",             "label": "Azure region",       "type": "azure_region"},
            {"name": "vm_size",              "label": "VM size",            "type": "vm_size"},
            {"name": "admin_username",       "label": "Admin username",     "type": "string"},
            {"name": "admin_password",       "label": "Admin password",     "type": "secret"},
            {"name": "os_image",             "label": "OS image",           "type": "os_image_windows", "example": "Windows Server 2022 Datacenter"},
        ],
    },
    {
        "key": "storage-account",
        "label": "Storage Account",
        "category": "Storage",
        "icon": "hard-drive",
        "accent": "amber",
        "description": "Blob, file, queue, and table storage for any workload.",
        "popular": True,
        "required_vars": [
            {"name": "name",                 "label": "Storage account name (3-24 lowercase)", "type": "storage_name"},
            {"name": "resource_group_name",  "label": "Resource group", "type": "string"},
            {"name": "location",             "label": "Azure region",   "type": "azure_region"},
            {"name": "account_tier",         "label": "Account tier (Standard/Premium)", "type": "enum", "options": ["Standard", "Premium"], "example": "Standard"},
            {"name": "replication_type",     "label": "Replication", "type": "enum", "options": ["LRS","GRS","RAGRS","ZRS","GZRS","RAGZRS"], "example": "LRS"},
        ],
    },
    {
        "key": "virtual-network",
        "label": "Virtual Network",
        "category": "Networking",
        "icon": "git-merge",
        "accent": "emerald",
        "description": "Isolated networking with subnets and custom addressing.",
        "popular": False,
        "required_vars": [
            {"name": "name",                "label": "VNet name", "type": "string"},
            {"name": "resource_group_name", "label": "Resource group", "type": "string"},
            {"name": "location",            "label": "Azure region", "type": "azure_region"},
            {"name": "address_space",       "label": "Address space (CIDR)", "type": "cidr", "example": "10.0.0.0/16"},
        ],
    },
    {
        "key": "subnet",
        "label": "Subnet",
        "category": "Networking",
        "icon": "git-merge",
        "accent": "emerald",
        "description": "Subnet within a virtual network.",
        "popular": False,
        "required_vars": [
            {"name": "name",                  "label": "Subnet name", "type": "string"},
            {"name": "resource_group_name",   "label": "Resource group", "type": "string"},
            {"name": "virtual_network_name",  "label": "VNet name", "type": "string"},
            {"name": "address_prefix",        "label": "Address prefix (CIDR)", "type": "cidr", "example": "10.0.1.0/24"},
        ],
    },
    {
        "key": "network-security-group",
        "label": "Network Security Group",
        "category": "Networking",
        "icon": "shield-check",
        "accent": "rose",
        "description": "Inbound/outbound traffic rules for subnets and NICs.",
        "popular": False,
        "required_vars": [
            {"name": "name",                "label": "NSG name", "type": "string"},
            {"name": "resource_group_name", "label": "Resource group", "type": "string"},
            {"name": "location",            "label": "Azure region", "type": "azure_region"},
        ],
    },
    {
        "key": "sql-server",
        "label": "SQL Server",
        "category": "Database",
        "icon": "database",
        "accent": "violet",
        "description": "Logical SQL server to host databases.",
        "popular": False,
        "required_vars": [
            {"name": "name",                  "label": "Server name (lowercase, 3-63)", "type": "string"},
            {"name": "resource_group_name",   "label": "Resource group", "type": "string"},
            {"name": "location",              "label": "Azure region", "type": "azure_region"},
            {"name": "administrator_login",   "label": "Admin login", "type": "string"},
            {"name": "administrator_password","label": "Admin password", "type": "secret"},
        ],
    },
    {
        "key": "sql-database",
        "label": "SQL Database",
        "category": "Database",
        "icon": "database",
        "accent": "violet",
        "description": "Managed relational database with high availability.",
        "popular": True,
        "required_vars": [
            {"name": "name",            "label": "Database name", "type": "string"},
            {"name": "server_name",     "label": "SQL Server name", "type": "string"},
            {"name": "resource_group_name", "label": "Resource group", "type": "string"},
            {"name": "sku_name",        "label": "Pricing tier (S0/S1/P1/...)", "type": "enum",
             "options": ["S0","S1","S2","S3","P1","P2"], "example": "S0"},
            {"name": "max_size_gb",     "label": "Max size (GB)", "type": "int", "example": 50},
        ],
    },
    {
        "key": "app-service",
        "label": "App Service",
        "category": "Compute",
        "icon": "boxes",
        "accent": "sky",
        "description": "Managed platform for hosting web apps and APIs.",
        "popular": False,
        "required_vars": [
            {"name": "name",                "label": "App name (globally unique)", "type": "string"},
            {"name": "resource_group_name", "label": "Resource group", "type": "string"},
            {"name": "location",            "label": "Azure region", "type": "azure_region"},
            {"name": "sku_name",            "label": "App plan SKU", "type": "enum",
             "options": ["B1","B2","S1","S2","P1v3","P2v3"], "example": "B1"},
            {"name": "runtime_stack",       "label": "Runtime stack", "type": "enum",
             "options": ["python","node","dotnet","java"], "example": "python"},
        ],
    },
    {
        "key": "key-vault",
        "label": "Key Vault",
        "category": "Security",
        "icon": "key-round",
        "accent": "rose",
        "description": "Secure secret, key, and certificate storage.",
        "popular": False,
        "required_vars": [
            {"name": "name",                "label": "Key Vault name (3-24 alphanumeric)", "type": "string"},
            {"name": "resource_group_name", "label": "Resource group", "type": "string"},
            {"name": "location",            "label": "Azure region", "type": "azure_region"},
            {"name": "sku_name",            "label": "SKU", "type": "enum",
             "options": ["standard","premium"], "example": "standard"},
        ],
    },
    {
        "key": "function-app",
        "label": "Function App",
        "category": "Compute",
        "icon": "boxes",
        "accent": "sky",
        "description": "Serverless event-driven compute.",
        "popular": False,
        "required_vars": [
            {"name": "name",                  "label": "Function App name", "type": "string"},
            {"name": "resource_group_name",   "label": "Resource group", "type": "string"},
            {"name": "location",              "label": "Azure region", "type": "azure_region"},
            {"name": "storage_account_name",  "label": "Backing storage account", "type": "string"},
            {"name": "runtime_stack",         "label": "Runtime stack", "type": "enum",
             "options": ["python","node","dotnet","java"], "example": "python"},
        ],
    },
    {
        "key": "load-balancer",
        "label": "Load Balancer",
        "category": "Networking",
        "icon": "git-merge",
        "accent": "emerald",
        "description": "Distribute traffic across compute instances.",
        "popular": False,
        "required_vars": [
            {"name": "name",                "label": "LB name", "type": "string"},
            {"name": "resource_group_name", "label": "Resource group", "type": "string"},
            {"name": "location",            "label": "Azure region", "type": "azure_region"},
            {"name": "sku",                 "label": "SKU", "type": "enum", "options": ["Basic","Standard"], "example": "Standard"},
        ],
    },
    {
        "key": "public-ip",
        "label": "Public IP",
        "category": "Networking",
        "icon": "git-merge",
        "accent": "emerald",
        "description": "Static or dynamic public IP address.",
        "popular": False,
        "required_vars": [
            {"name": "name",                "label": "Public IP name", "type": "string"},
            {"name": "resource_group_name", "label": "Resource group", "type": "string"},
            {"name": "location",            "label": "Azure region", "type": "azure_region"},
            {"name": "allocation_method",   "label": "Allocation method", "type": "enum",
             "options": ["Static","Dynamic"], "example": "Static"},
        ],
    },
    {
        "key": "managed-identity",
        "label": "Managed Identity",
        "category": "Security",
        "icon": "key-round",
        "accent": "rose",
        "description": "User-assigned Azure AD identity for resources.",
        "popular": False,
        "required_vars": [
            {"name": "name",                "label": "Identity name", "type": "string"},
            {"name": "resource_group_name", "label": "Resource group", "type": "string"},
            {"name": "location",            "label": "Azure region", "type": "azure_region"},
        ],
    },
]

CATALOG_BY_KEY = {m["key"]: m for m in CATALOG}


# ----------------------------------------------------------------------
# Dependency graph for resource planning
# ----------------------------------------------------------------------
DEPENDENCY_GRAPH: Dict[str, List[Dict[str, Any]]] = {
    "virtual-machine-linux": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain the VM"},
        {"module": "virtual-network", "relationship": "depends_on", "description": "VNet for the VM's network"},
        {"module": "subnet", "relationship": "depends_on", "description": "Subnet within the VNet"},
        {"module": "network-security-group", "relationship": "depends_on", "description": "NSG to secure the VM"},
        {"module": "public-ip", "relationship": "optional_depends_on", "description": "Public IP for external access"},
        {"module": "managed-identity", "relationship": "optional_depends_on", "description": "Managed identity for Azure resource access"},
    ],
    "virtual-machine-windows": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain the VM"},
        {"module": "virtual-network", "relationship": "depends_on", "description": "VNet for the VM's network"},
        {"module": "subnet", "relationship": "depends_on", "description": "Subnet within the VNet"},
        {"module": "network-security-group", "relationship": "depends_on", "description": "NSG to secure the VM"},
        {"module": "public-ip", "relationship": "optional_depends_on", "description": "Public IP for external access"},
    ],
    "linux-vm-nginx": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain all resources"},
        {"module": "virtual-network", "relationship": "depends_on", "description": "VNet for networking"},
        {"module": "subnet", "relationship": "depends_on", "description": "Subnet within the VNet"},
        {"module": "network-security-group", "relationship": "depends_on", "description": "NSG with SSH+HTTP rules"},
        {"module": "public-ip", "relationship": "depends_on", "description": "Public IP for the NIC"},
    ],
    "storage-account": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain the storage account"},
    ],
    "virtual-network": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain the VNet"},
    ],
    "subnet": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group containing the VNet"},
        {"module": "virtual-network", "relationship": "depends_on", "description": "Parent VNet for the subnet"},
    ],
    "network-security-group": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain the NSG"},
    ],
    "sql-server": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain the SQL server"},
    ],
    "sql-database": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group containing the SQL server"},
        {"module": "sql-server", "relationship": "depends_on", "description": "Parent SQL server for the database"},
    ],
    "app-service": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain the App Service"},
    ],
    "key-vault": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain the Key Vault"},
    ],
    "function-app": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain the Function App"},
        {"module": "storage-account", "relationship": "depends_on", "description": "Backing storage account for the Function App"},
    ],
    "load-balancer": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain the LB"},
        {"module": "public-ip", "relationship": "optional_depends_on", "description": "Public IP frontend for the LB"},
    ],
    "public-ip": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain the Public IP"},
    ],
    "managed-identity": [
        {"module": "resource-group", "relationship": "depends_on", "description": "Resource group to contain the Managed Identity"},
    ],
    "resource-group": [],
}


def build_dependency_graph(module_key: str) -> List[Dict[str, Any]]:
    """Return the dependency graph for a given module.

    Returns a list of dependency nodes, each with:
      - module: the dependent module key
      - relationship: "depends_on" | "optional_depends_on"
      - description: human-readable explanation
    """
    return DEPENDENCY_GRAPH.get(module_key, [])


# ----------------------------------------------------------------------
# Cloud-init generation
# ----------------------------------------------------------------------
CLOUD_INIT_WORKLOADS = {
    "docker": {
        "label": "Docker Engine",
        "description": "Install Docker Engine and Docker Compose for container workloads",
    },
    "nginx": {
        "label": "NGINX Web Server",
        "description": "Install and configure NGINX as a reverse proxy or static file server",
    },
    "apache": {
        "label": "Apache HTTP Server",
        "description": "Install and configure Apache HTTP Server",
    },
    "python": {
        "label": "Python Application Server",
        "description": "Install Python 3, pip, and common application dependencies",
    },
    "nodejs": {
        "label": "Node.js Application Server",
        "description": "Install Node.js, npm, and PM2 process manager",
    },
    "kubernetes": {
        "label": "Kubernetes Node (kubeadm)",
        "description": "Install kubelet, kubeadm, and kubectl for cluster joining",
    },
    "monitoring": {
        "label": "Monitoring Agent",
        "description": "Install Prometheus Node Exporter and Azure Monitor agent",
    },
}


def _ci_header() -> str:
    return """#cloud-config
package_update: true
package_upgrade: false
"""


def _ci_user_data(admin_username: str, ssh_public_key: str) -> str:
    if not ssh_public_key:
        return ""
    return f"""
users:
  - name: {admin_username}
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - {ssh_public_key}
"""


def _ci_packages(pkgs: List[str]) -> str:
    if not pkgs:
        return ""
    formatted = "\n".join(f"  - {p}" for p in pkgs)
    return f"""
packages:
{formatted}
"""


def _ci_write_files(files: List[Dict[str, str]]) -> str:
    if not files:
        return ""
    entries = ""
    for f in files:
        path = f.get("path", "")
        content = f.get("content", "")
        permissions = f.get("permissions", "0644")
        owner = f.get("owner", "root:root")
        entries += f"""
  - path: {path}
    content: |
{_indent(content, 6)}
    permissions: '{permissions}'
    owner: {owner}
"""
    return f"""
write_files:
{entries}
"""


def _indent(text: str, spaces: int = 4) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.split("\n"))


def _ci_runcmd(commands: List[str]) -> str:
    if not commands:
        return ""
    formatted = "\n".join(f"  - {c}" for c in commands)
    return f"""
runcmd:
{formatted}
"""


def generate_cloud_init(
    workload: str,
    admin_username: str = "azureuser",
    ssh_public_key: str = "",
    app_script: str = "",
    extra_packages: Optional[List[str]] = None,
) -> str:
    """Generate cloud-init YAML for a given workload type.

    Supported workloads: docker, nginx, apache, python, nodejs, kubernetes, monitoring.

    Returns a complete cloud-init YAML string suitable for Azure VM custom_data.
    """
    parts = [_ci_header()]
    parts.append(_ci_user_data(admin_username, ssh_public_key))

    base_packages = ["curl", "wget", "git", "htop", "net-tools"]
    pkgs = list(base_packages)
    if extra_packages:
        pkgs.extend(extra_packages)

    runcmd: List[str] = []

    if workload == "docker":
        pkgs.extend(["apt-transport-https", "ca-certificates", "software-properties-common"])
        runcmd.extend([
            "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -",
            "add-apt-repository \"deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable\"",
        ])
        pkgs.append("docker-ce")
        runcmd.extend([
            "systemctl enable docker",
            "systemctl start docker",
            "usermod -aG docker ubuntu",
            "curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)\" -o /usr/local/bin/docker-compose",
            "chmod +x /usr/local/bin/docker-compose",
        ])
        if app_script:
            runcmd.append(f"cd /home/{admin_username} && echo \"{app_script}\" > docker-compose.yml && docker-compose up -d")

    elif workload == "nginx":
        pkgs.append("nginx")
        runcmd.extend([
            "systemctl enable nginx",
            "systemctl start nginx",
            "ufw allow 'Nginx HTTP'",
        ])
        if app_script:
            files = [{
                "path": f"/etc/nginx/sites-available/{admin_username}-app",
                "content": app_script,
                "permissions": "0644",
            }]
            parts.append(_ci_write_files(files))
            runcmd.append(f"ln -sf /etc/nginx/sites-available/{admin_username}-app /etc/nginx/sites-enabled/")
            runcmd.append("systemctl reload nginx")

    elif workload == "apache":
        pkgs.append("apache2")
        runcmd.extend([
            "systemctl enable apache2",
            "systemctl start apache2",
            "ufw allow 'Apache Full'",
        ])
        if app_script:
            files = [{
                "path": "/var/www/html/index.html",
                "content": app_script,
                "permissions": "0644",
            }]
            parts.append(_ci_write_files(files))

    elif workload == "python":
        pkgs.extend(["python3", "python3-pip", "python3-venv", "build-essential"])
        if app_script:
            files = [{
                "path": f"/home/{admin_username}/app/app.py",
                "content": app_script,
                "permissions": "0644",
                "owner": f"{admin_username}:{admin_username}",
            }]
            parts.append(_ci_write_files(files))
            runcmd.extend([
                f"mkdir -p /home/{admin_username}/app",
                f"python3 -m venv /home/{admin_username}/app/venv",
                f"chown -R {admin_username}:{admin_username} /home/{admin_username}/app",
            ])

    elif workload == "nodejs":
        runcmd.extend([
            "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
            "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        ])
        pkgs.append("nodejs")
        runcmd.extend([
            "npm install -g pm2",
        ])
        if app_script:
            files = [{
                "path": f"/home/{admin_username}/app/app.js",
                "content": app_script,
                "permissions": "0644",
                "owner": f"{admin_username}:{admin_username}",
            }]
            parts.append(_ci_write_files(files))
            runcmd.extend([
                f"mkdir -p /home/{admin_username}/app",
                f"cd /home/{admin_username}/app && npm init -y",
                f"cd /home/{admin_username}/app && npm install express --save",
                f"chown -R {admin_username}:{admin_username} /home/{admin_username}/app",
            ])

    elif workload == "kubernetes":
        pkgs.extend(["apt-transport-https", "ca-certificates", "curl", "gnupg", "lsb-release"])
        runcmd.extend([
            "curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -",
            "echo \"deb https://apt.kubernetes.io/ kubernetes-xenial main\" | tee /etc/apt/sources.list.d/kubernetes.list",
        ])
        pkgs.extend(["kubelet", "kubeadm", "kubectl"])
        runcmd.append("apt-mark hold kubelet kubeadm kubectl")

    elif workload == "monitoring":
        runcmd.extend([
            "curl -fsSL https://github.com/prometheus/node_exporter/releases/download/v1.7.0/node_exporter-1.7.0.linux-amd64.tar.gz -o /tmp/node_exporter.tar.gz",
            "tar -xzf /tmp/node_exporter.tar.gz -C /tmp/",
            "cp /tmp/node_exporter-1.7.0.linux-amd64/node_exporter /usr/local/bin/",
            "useradd -rs /bin/false node_exporter || true",
            "chown node_exporter:node_exporter /usr/local/bin/node_exporter",
        ])
        node_exporter_service = """[Unit]
Description=Prometheus Node Exporter
After=network.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target"""
        files = [{
            "path": "/etc/systemd/system/node_exporter.service",
            "content": node_exporter_service,
            "permissions": "0644",
        }]
        parts.append(_ci_write_files(files))
        runcmd.extend([
            "systemctl daemon-reload",
            "systemctl enable node_exporter",
            "systemctl start node_exporter",
        ])

    parts.append(_ci_packages(pkgs))
    parts.append(_ci_runcmd(runcmd))

    return "\n".join(p for p in parts if p.strip())


# ----------------------------------------------------------------------
# Cost estimation wrapper
# ----------------------------------------------------------------------
async def estimate_deployment_cost(module_key: str, tfvars: Dict[str, Any], action: str = "create",
                                   runtime_path: Optional[Path] = None) -> Dict[str, Any]:
    """Estimate the monthly cost of a deployment.

    Tries Infracost CLI first (if a runtime_path is provided and Infracost is configured),
    then falls back to Azure Retail Pricing API.
    """
    if runtime_path and action != "destroy":
        try:
            infracost_result = await estimate_with_infracost(runtime_path, module_key, tfvars)
            if infracost_result and (infracost_result.get("monthly_total") or 0) > 0:
                return infracost_result
            if infracost_result:
                logger.info("Infracost returned $0 cost, falling back to Azure Retail Pricing API")
        except Exception as e:
            logger.debug("Infracost path failed, falling back: %s", e)

    try:
        return await _pricing_estimate_cost(module_key, tfvars, action=action)
    except Exception as e:
        logger.exception("estimate_deployment_cost failed for %s", module_key)
        return {
            "monthly_total": 0.0,
            "currency": "USD",
            "breakdown": [{"label": "Cost estimate unavailable", "monthly": 0.0, "note": str(e)}],
            "one_time": 0.0,
            "optimization_suggestions": [],
        }


# ----------------------------------------------------------------------
# Intent classification (heuristic + AI assist)
# ----------------------------------------------------------------------
INTENT_KEYWORDS = {
    "virtual-machine-linux":   ["linux", "ubuntu", "centos", "rhel", "debian", "linux vm"],
    "virtual-machine-windows": ["windows", "win", "windows vm", "win server"],
    "storage-account":         ["storage", "blob", "file share"],
    "virtual-network":         ["vnet", "virtual network", "network"],
    "subnet":                  ["subnet"],
    "network-security-group":  ["nsg", "security group", "firewall rules"],
    "sql-database":            ["sql db", "sql database", "database", "mssql"],
    "sql-server":              ["sql server"],
    "app-service":             ["app service", "web app", "webapp"],
    "key-vault":               ["key vault", "secret", "vault"],
    "function-app":            ["function app", "lambda", "serverless"],
    "load-balancer":           ["load balancer", "lb"],
    "public-ip":               ["public ip", "static ip"],
    "managed-identity":        ["managed identity", "msi", "uami"],
    "resource-group":          ["resource group", " rg "],
}


def heuristic_intent(text: str) -> Optional[str]:
    t = f" {text.lower()} "
    best = None
    best_score = 0
    for key, words in INTENT_KEYWORDS.items():
        for w in words:
            if w in t and len(w) > best_score:
                best, best_score = key, len(w)
    return best


# ----------------------------------------------------------------------
# AI orchestration helpers
# ----------------------------------------------------------------------
SYS_INTENT = """You are InfraGenie, an intelligent AI Azure infrastructure engineer and cloud advisor.
Your job is to understand the user's DEPLOYMENT GOAL and help them provision Azure infrastructure.

For every request, follow this process:
1. Ask about the user's PURPOSE / WORKLOAD first (e.g., "What will this server be used for? Web hosting, Docker containers, database, dev/test?").
2. Based on their purpose, recommend the RIGHT module and best-fit configuration. For VMs: recommend VM sizes available in their chosen region (e.g., B-series for dev/test, D-series for production, E-series for memory-intensive). For databases: recommend tier/SKU based on expected load.
3. Build a dependency graph of ALL resources needed for that module.
4. Ask for ALL missing information in ONE MESSAGE — NEVER ask one variable at a time.
5. If the user mentions a workload (Docker, Nginx, Apache, Python, NodeJS, Kubernetes, monitoring), offer to generate cloud-init for it.
6. Make smart recommendations: suggest VM sizes based on workload (e.g. "Standard_D4s_v5 is good for Docker workloads with 4 vCPUs and 16GB RAM"), recommend regions based on latency, suggest SKUs based on scale.

Return a JSON object with EXACTLY this shape:
{
  "module_key": "<one of the supported keys or null if unclear>",
  "confidence": "high|medium|low",
  "extracted_vars": { "<var_name>": "<value>", ... },
  "missing_vars": ["<var_name>", ...],
  "next_question": "<a SINGLE friendly message that lists ALL still-missing variables together with their labels, helpful defaults, and examples, so the user can answer them in one reply. If the user asks for a recommendation (e.g. VM size), suggest a specific value with reasoning. Suggest existing Azure resources from the 'existing_resources' field if available. Do NOT use markdown formatting — plain English only.>",
  "existing_resources": {
    "resource_groups": [{"name": "...", "location": "..."}],
    "vnets": [{"name": "...", "location": "..."}],
    "subnets": [{"name": "...", "vnet": "..."}],
    "vms": [{"name": "...", "size": "..."}]
  },
  "recommendations": {
    "vm_size": {"suggested": "Standard_D4s_v5", "reason": "4 vCPUs, 16 GB RAM — good for Docker/container workloads"},
    "region": {"suggested": "centralindia", "reason": "Low latency for India-based workloads"},
    "disk_type": {"suggested": "Premium_LRS", "reason": "Better IOPS for database workloads"},
    "workload_cloud_init": "<workload_key or null>",
    "workload_note": "<explanation of what cloud-init will configure>"
  }
}

Rules:
- Only set module_key if you are at least 70% sure. If uncertain, ask a clarifying question first.
- IMPORTANT: If the user CHANGES their mind and explicitly asks for a different resource type, SWITCH to the new module. Do NOT stay locked to the previous choice. Update module_key accordingly and reset extracted_vars for the new module.
- When a user wants to deploy infrastructure from scratch (no mentioning existing VNet/subnet), ALWAYS prefer ALL-IN-ONE modules such as "linux-vm-nginx" which creates RG+VNet+Subnet+NSG+PIP+NIC+VM. NEVER choose "virtual-machine-linux" or "virtual-machine-windows" unless the user explicitly says they have an existing subnet. Standalone VM modules require a "subnet_id" which is NOT appropriate for brand-new deployments.
- Do not invent values the user did not give — but you MAY suggest sensible defaults in `next_question`.
- IMPORTANT: If the user says "use defaults" / "all default" / "just use defaults" / "default everything" or similar, fill ALL missing mandatory variables with sensible defaults (e.g. location='eastus', vm_size='Standard_B2s', admin_username='azureuser', name='vm-default', resource_group_name='rg-default'). If starting from scratch, ALWAYS choose "linux-vm-nginx" as the module (it is all-in-one and needs no existing infrastructure). Then set next_question to "READY" and missing_vars to []. Do NOT ask any follow-up questions. The user wants the fastest path to deployment.
- If everything required is collected, set "next_question" to "READY" and "missing_vars" to [].
- Always ask for ALL remaining fields in one go using a numbered list (1., 2., 3., ...) with each field on its own line. NEVER write paragraphs.
- When the user asks for a recommendation (VM size, region, SKU, image), propose a concrete value and explain trade-offs briefly. Provide region-specific VM size options when the user specifies a region.
- The "next_question" text MUST use plain numbered list format — do NOT use markdown formatting (no **bold**, no `code fences`, no # headings).
- Be consultative: ask about the workload purpose first, then recommend the most suitable module and configuration. For example: "What will this server be used for?" before jumping to VM details.
- The "existing_resources" field should contain resources the AI discovers from the conversation context — if the user mentions existing resources, list them here so the frontend can display them as choices.
- The "recommendations" field should contain smart workload-based recommendations. If the user mentions a workload like Docker, suggest appropriate VM sizes.
- For workload-based requests (Docker, Nginx, etc.), set workload_cloud_init to the matching workload key so the system can generate cloud-init.
- Always return STRICT VALID JSON only — no markdown fences around the JSON, no commentary.
"""


def _safe_json(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception as e:
        logger.warning("JSON parse failed: %s", e)
        return None


def _catalog_summary_for_ai() -> List[Dict[str, Any]]:
    out = []
    for m in CATALOG:
        out.append({
            "key": m["key"],
            "label": m["label"],
            "category": m["category"],
            "description": m["description"],
            "required_vars": [
                {"name": v["name"], "label": v["label"], "type": v["type"],
                 "optional": v.get("optional", False), "example": v.get("example", None)}
                for v in m["required_vars"]
            ],
        })
    return out


async def ai_classify_and_collect(
    user_message: str,
    current_vars: Dict[str, Any],
    module_key: Optional[str],
    session_id: str,
    ai_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Single round of the conversation. Returns the structured next-step dict."""
    payload = {
        "user_message": user_message,
        "currently_collected": current_vars or {},
        "current_module_key": module_key,
        "catalog": _catalog_summary_for_ai(),
        "dependency_graph": DEPENDENCY_GRAPH,
        "supported_workloads": list(CLOUD_INIT_WORKLOADS.keys()),
        "workload_descriptions": CLOUD_INIT_WORKLOADS,
    }
    parsed = await chat_json(ai_config, SYS_INTENT, json.dumps(payload))
    parsed.setdefault("module_key", module_key)
    parsed.setdefault("confidence", "low")
    parsed.setdefault("extracted_vars", {})
    parsed.setdefault("missing_vars", [])
    parsed.setdefault("next_question", "What would you like to provision?")
    parsed.setdefault("existing_resources", {})
    parsed.setdefault("recommendations", {})
    return parsed


# ----------------------------------------------------------------------
# Demo-mode Terraform runtime
# ----------------------------------------------------------------------
def _runtime_path(workspace_id: str, deployment_id: str) -> Path:
    p = RUNTIME_DIR / workspace_id / deployment_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _format_tfvars_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_format_tfvars_value(x) for x in v) + "]"
    if isinstance(v, dict):
        inner = ", ".join(f'{k} = {_format_tfvars_value(val)}' for k, val in v.items())
        return "{ " + inner + " }"
    s = str(v).replace('"', '\\"')
    return f'"{s}"'


def render_tfvars(vars_map: Dict[str, Any]) -> str:
    lines = []
    for k, v in vars_map.items():
        if v in (None, ""):
            continue
        lines.append(f"{k} = {_format_tfvars_value(v)}")
    return "\n".join(lines) + "\n"


def stage_runtime_folder(
    workspace_id: str,
    deployment_id: str,
    module_key: str,
    tfvars: Dict[str, Any],
) -> Path:
    """Copy module to runtime folder and write tfvars + backend.tf + providers.tf."""
    src = MODULES_DIR / module_key
    dst = _runtime_path(workspace_id, deployment_id)
    if src.exists():
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)
    (dst / "terraform.tfvars").write_text(render_tfvars(tfvars), encoding="utf-8")
    (dst / "backend.tf").write_text(_render_backend_tf(workspace_id, deployment_id), encoding="utf-8")
    (dst / "providers.tf").write_text(_render_providers_tf(), encoding="utf-8")
    return dst


def _render_backend_tf(workspace_id: str, deployment_id: str) -> str:
    return f"""# Auto-generated by InfraGenie — DO NOT EDIT
terraform {{
  backend "azurerm" {{
    key = "{workspace_id}/{deployment_id}/terraform.tfstate"
  }}
}}
"""


def _render_providers_tf() -> str:
    return """# Auto-generated by InfraGenie
terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 3.100" }
    random  = { source = "hashicorp/random",  version = "~> 3.6" }
  }
  required_version = ">= 1.5.0"
}

provider "azurerm" {
  features {}
}
"""


# ----------------------------------------------------------------------
# AI-generated plan with REAL cost estimation
# ----------------------------------------------------------------------
SYS_PLAN = """You are InfraGenie's Terraform simulator.
Given a Terraform module key and tfvars, generate a REALISTIC simulated `terraform plan` summary
PLUS security and compliance insights. Cost estimation is handled separately via Azure Retail Pricing API so do NOT generate cost data.

Output STRICT JSON with this shape:
{
  "summary": "Plan: N to add, M to change, K to destroy.",
  "actions": [
    {
      "action": "create|update|destroy",
      "resource_type": "azurerm_xxx",
      "resource_name": "xxx",
      "details": ["key=value", ...]
    }
  ],
  "outputs": [
    { "name": "xxx", "value_preview": "..." }
  ],
  "security": {
    "score": <0-100>,
    "warnings": ["..."],
    "compliance": ["..."]
  },
  "duration_estimate_seconds": <integer>
}
Be realistic and specific about the Azure resource types, their configuration, and what Terraform will create.
Include relevant security warnings and compliance checks based on the deployed resources.
Return ONLY the JSON object, no markdown, no commentary.
"""


async def ai_generate_plan(
    module_key: str,
    tfvars: Dict[str, Any],
    session_id: str,
    ai_config: Dict[str, Any],
    runtime_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Generate a plan with real cost data from Azure Retail Pricing API (or Infracost if available)."""
    user = json.dumps({"module_key": module_key, "tfvars": tfvars, "region": tfvars.get("location", "centralindia")})
    parsed = await chat_json(ai_config, SYS_PLAN, user)
    parsed.setdefault("summary", "Plan: 1 to add, 0 to change, 0 to destroy.")
    parsed.setdefault("actions", [])
    parsed.setdefault("outputs", [])
    parsed.setdefault("security", {"score": 80, "warnings": [], "compliance": []})
    parsed.setdefault("duration_estimate_seconds", 90)

    # Attach REAL cost data from Infracost or Azure Retail Pricing API
    try:
        cost_data = await estimate_deployment_cost(module_key, tfvars, runtime_path=runtime_path)
        parsed["cost"] = cost_data
    except Exception as e:
        logger.warning("Real cost estimation failed, using fallback: %s", e)
        parsed["cost"] = {
            "monthly_total": 0.0,
            "currency": "USD",
            "breakdown": [{"label": "Cost estimate unavailable", "monthly": 0.0, "note": str(e)}],
            "one_time": 0.0,
            "optimization_suggestions": [],
        }
    return parsed


# ----------------------------------------------------------------------
# AI-generated apply simulation
# ----------------------------------------------------------------------
SYS_APPLY = """You are InfraGenie's Terraform apply simulator.
Given the plan and tfvars, produce REALISTIC simulated apply OUTPUT logs + final outputs.
Output STRICT JSON:
{
  "logs": [ "<log line 1>", "<log line 2>", ... 10-20 lines, with timestamps and azurerm_xxx: Creation complete..." ],
  "outputs": { "<name>": "<value>", ... },
  "elapsed_seconds": <integer>,
  "status": "completed"
}
Return ONLY JSON.
"""


async def ai_generate_apply(
    module_key: str,
    tfvars: Dict[str, Any],
    plan: Dict[str, Any],
    session_id: str,
    ai_config: Dict[str, Any],
) -> Dict[str, Any]:
    user = json.dumps({"module_key": module_key, "tfvars": tfvars, "plan_actions": plan.get("actions", [])})
    parsed = await chat_json(ai_config, SYS_APPLY, user)
    parsed.setdefault("logs", [f"azurerm_{module_key.replace('-','_')}.this: Creation complete after 90s"])
    parsed.setdefault("outputs", {})
    parsed.setdefault("elapsed_seconds", random.randint(60, 180))
    parsed.setdefault("status", "completed")
    return parsed


# ----------------------------------------------------------------------
# Ticket helpers (numbering)
# ----------------------------------------------------------------------
def new_ticket_number() -> str:
    return "INC" + datetime.now(timezone.utc).strftime("%Y%m%d") + uuid.uuid4().hex[:6].upper()
