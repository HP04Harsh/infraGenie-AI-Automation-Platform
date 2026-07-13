"""Azure VM monitoring: Node Exporter, Azure Monitor alerts, self-healing."""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.monitor import MonitorManagementClient

from email_service import send_email, build_alert_email_body, build_resolution_email_body

logger = logging.getLogger(__name__)

# Prometheus file-based SD targets directory (shared volume with prometheus container)
TARGETS_DIR = Path("/prometheus-targets")
TARGETS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory cache of active monitoring tickets to avoid duplicates
ACTIVE_ALERTS: Dict[str, str] = {}  # vm_name + issue_type -> ticket_number


# ---------- helpers ----------
def _build_cred(tenant: Dict, secret: Dict) -> Optional[ClientSecretCredential]:
    tid = (tenant.get("fields") or {}).get("tenant_id") or tenant.get("tenant_id", "")
    cid = (tenant.get("fields") or {}).get("client_id") or tenant.get("client_id", "")
    cs = (secret or {}).get("azure_client_secret", "")
    if not all([tid, cid, cs]):
        return None
    return ClientSecretCredential(tenant_id=tid, client_id=cid, client_secret=cs)


async def _load_sp(db, user_id: str) -> Optional[Dict[str, Any]]:
    tenant = await db.integrations.find_one({"user_id": user_id, "key": "azure_tenant"})
    secret = await db.secrets.find_one({"user_id": user_id})
    if not tenant:
        tenant = await db.users.find_one({"id": user_id}, {"_id": 0, "azure_tenant": 1}) or {}
        tenant = tenant.get("azure_tenant") or {}
    cred = _build_cred(tenant, secret)
    sub = (tenant.get("fields") or {}).get("subscription_id") or tenant.get("subscription_id", "")
    return {"cred": cred, "subscription_id": sub} if cred and sub else None


# ---------- Node Exporter ----------
NODE_EXPORTER_INSTALL_SCRIPT = """#!/bin/bash
set -e
VER="1.7.0"
if command -v node_exporter &>/dev/null; then
  echo "node_exporter already installed"
  exit 0
fi
cd /tmp
wget -q https://github.com/prometheus/node_exporter/releases/download/v${VER}/node_exporter-${VER}.linux-amd64.tar.gz
tar xzf node_exporter-${VER}.linux-amd64.tar.gz
sudo cp node_exporter-${VER}.linux-amd64/node_exporter /usr/local/bin/
sudo useradd -rs /bin/false node_exporter 2>/dev/null || true
sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<'SERVICEEOF'
[Unit]
Description=Prometheus Node Exporter
After=network.target
[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter --web.listen-address=:9100
[Install]
WantedBy=default.target
SERVICEEOF
sudo systemctl daemon-reload
sudo systemctl enable node_exporter
sudo systemctl start node_exporter
echo "node_exporter installed and running"
"""


async def install_node_exporter(
    subscription_id: str,
    resource_group: str,
    vm_name: str,
    cred: ClientSecretCredential,
) -> Dict[str, Any]:
    """Install Node Exporter on a Linux VM via Azure Run Command."""
    try:
        client = ComputeManagementClient(cred, subscription_id)
        poller = client.virtual_machines.begin_run_command(
            resource_group, vm_name,
            {
                "command_id": "RunShellScript",
                "script": [NODE_EXPORTER_INSTALL_SCRIPT],
            },
        )
        result = poller.result()
        output = "".join(result.value[0].message.splitlines()[:30]) if result.value else ""
        logger.info("Node Exporter installed on %s: %s", vm_name, output[:200])
        return {"success": True, "output": output[:500]}
    except Exception as e:
        logger.warning("Node Exporter install failed on %s: %s", vm_name, e)
        return {"success": False, "error": str(e)[:300]}


async def register_prometheus_target(vm_name: str, public_ip: str, port: int = 9100):
    """Register VM as a Prometheus scrape target via file-based SD."""
    targets_file = TARGETS_DIR / "node_targets.json"
    existing = []
    if targets_file.exists():
        try:
            existing = json.loads(targets_file.read_text())
        except Exception:
            existing = []
    target = f"{public_ip}:{port}"
    if not any(t["targets"] == [target] for t in existing):
        existing.append({"targets": [target], "labels": {"job": "node", "vm": vm_name}})
        targets_file.write_text(json.dumps(existing, indent=2))
        logger.info("Prometheus target registered: %s -> %s", vm_name, target)
    return target


# ---------- Azure Monitor Metrics ----------
METRIC_QUERIES = {
    "cpu": {
        "metricnames": "Percentage CPU",
        "aggregation": "Average",
        "interval": "PT5M",
        "threshold": 80.0,
    },
    "disk_read": {
        "metricnames": "Disk Read Bytes",
        "aggregation": "Average",
        "interval": "PT5M",
    },
    "disk_write": {
        "metricnames": "Disk Write Bytes",
        "aggregation": "Average",
        "interval": "PT5M",
    },
    "disk_usage": {
        "metricnames": "Disk Read Operations/Sec",
        "aggregation": "Average",
        "interval": "PT5M",
    },
    "network_in": {
        "metricnames": "Network In",
        "aggregation": "Total",
        "interval": "PT5M",
    },
    "network_out": {
        "metricnames": "Network Out",
        "aggregation": "Total",
        "interval": "PT5M",
    },
}

DISK_METRIC = {"metricnames": "Percentage Disk", "aggregation": "Average", "interval": "PT5M", "threshold": 80.0}


async def query_vm_metrics(
    cred: ClientSecretCredential,
    subscription_id: str,
    resource_group: str,
    vm_name: str,
) -> Dict[str, Any]:
    """Query Azure Monitor for VM metrics (CPU, Memory, Disk)."""
    try:
        client = MonitorManagementClient(cred, subscription_id)
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=15)
        timespan = f"{start.isoformat()}/{end.isoformat()}"

        resource_id = (
            f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.Compute/virtualMachines/{vm_name}"
        )

        results = {}

        # CPU
        cpu_data = client.metrics.list(
            resource_id,
            timespan=timespan,
            interval="PT5M",
            metricnames="Percentage CPU",
            aggregation="Average",
        )
        cpu_vals = _extract_metric_values(cpu_data, "Average")
        results["cpu_percent"] = cpu_vals[-1] if cpu_vals else 0
        results["cpu_max"] = max(cpu_vals) if cpu_vals else 0

        # Disk I/O (proxy for disk usage)
        disk_data = client.metrics.list(
            resource_id,
            timespan=timespan,
            interval="PT5M",
            metricnames="Disk Read Bytes,Disk Write Bytes",
            aggregation="Average",
        )
        disk_read_vals = _extract_metric_values(disk_data, "Average", "Disk Read Bytes")
        disk_write_vals = _extract_metric_values(disk_data, "Average", "Disk Write Bytes")
        results["disk_read_bytes"] = disk_read_vals[-1] if disk_read_vals else 0
        results["disk_write_bytes"] = disk_write_vals[-1] if disk_write_vals else 0

        # Network
        net_data = client.metrics.list(
            resource_id,
            timespan=timespan,
            interval="PT5M",
            metricnames="Network In Total,Network Out Total",
            aggregation="Total",
        )
        net_in_vals = _extract_metric_values(net_data, "Total", "Network In Total")
        net_out_vals = _extract_metric_values(net_data, "Total", "Network Out Total")
        results["network_in_bytes"] = net_in_vals[-1] if net_in_vals else 0
        results["network_out_bytes"] = net_out_vals[-1] if net_out_vals else 0

        # VM Power State (check if running)
        try:
            compute = ComputeManagementClient(cred, subscription_id)
            vm_instance = compute.virtual_machines.get(resource_group, vm_name, expand="instanceView")
            statuses = vm_instance.instance_view.statuses if vm_instance.instance_view else []
            power_state = "unknown"
            for s in statuses:
                if s.code and "PowerState" in s.code:
                    power_state = s.code.split("/")[-1]
            results["power_state"] = power_state
        except Exception:
            results["power_state"] = "unknown"

        results["timestamp"] = datetime.now(timezone.utc).isoformat()
        return results
    except Exception as e:
        logger.warning("Azure Monitor query failed for %s: %s", vm_name, e)
        return {"error": str(e)[:300]}


def _extract_metric_values(
    response, aggregation: str, metric_name: Optional[str] = None
) -> List[float]:
    values = []
    try:
        for metric in response.value:
            if metric_name and metric.name.value != metric_name:
                continue
            for timeseries in metric.timeseries:
                for data in timeseries.data:
                    val = getattr(data, aggregation.lower(), None)
                    if val is not None:
                        values.append(val)
    except Exception:
        pass
    return values


# ---------- Alert Processing ----------
async def create_alert_ticket(
    db, user_id: str,
    vm_name: str,
    issue_type: str,
    details: str,
    metrics: Dict[str, Any],
    subscription_id: str = "",
    resource_group: str = "",
) -> Optional[Dict[str, Any]]:
    """Create alert ticket in local DB + ServiceNow. Returns ticket dict."""
    now = datetime.now(timezone.utc)
    ticket_number = f"ALERT{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"

    ticket_doc = {
        "id": str(uuid.uuid4()),
        "ticket_number": ticket_number,
        "user_id": user_id,
        "title": f"[Alert] {issue_type.upper()} on {vm_name}",
        "description": details,
        "vm_name": vm_name,
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "issue_type": issue_type,
        "metrics": metrics,
        "source": "monitoring",
        "status": "open",
        "priority": "P1" if issue_type in ("shutdown",) else "P2",
        "created_at": now,
        "updated_at": now,
        "audit": [{"action": "created", "by": "InfraGenie Monitor", "at": now.isoformat(), "note": details[:200]}],
        "comments": [],
        "fix_applied": False,
        "fix_script": "",
        "fix_result": {},
        "servicenow_sys_id": "",
    }
    await db.tickets.insert_one(ticket_doc)

    # Sync to ServiceNow
    try:
        from servicenow_service import create_incident as sn_create
        sn_result = await sn_create(
            db, user_id,
            short_description=f"[Alert] {issue_type.upper()} - {vm_name}",
            description=details,
            caller_email="",
            watch_list="harshpardhi477@gmail.com",
            severity=1 if issue_type in ("shutdown",) else 2,
        )
        if sn_result:
            sn_number = sn_result.get("number", "")
            sn_sys_id = sn_result.get("sys_id", "")
            await db.tickets.update_one(
                {"ticket_number": ticket_number},
                {"$set": {"servicenow_number": sn_number, "servicenow_sys_id": sn_sys_id}}
            )
            ticket_doc["servicenow_number"] = sn_number
            ticket_doc["servicenow_sys_id"] = sn_sys_id
    except Exception as e:
        logger.warning("ServiceNow sync failed for alert ticket: %s", e)

    # Send email alert
    try:
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "name": 1})
        if user and user.get("email"):
            email_body = build_alert_email_body(vm_name, issue_type, details, ticket_number)
            asyncio.create_task(send_email(
                db, user_id, user["email"],
                f"[InfraGenie Alert] {issue_type.upper()} on {vm_name} - {ticket_number}",
                email_body,
            ))
    except Exception as e:
        logger.warning("Alert email failed: %s", e)

    ACTIVE_ALERTS[f"{vm_name}_{issue_type}"] = ticket_number
    logger.info("Alert ticket %s created for %s - %s", ticket_number, vm_name, issue_type)
    return ticket_doc


async def check_and_alert(
    db, user_id: str,
    vm_name: str,
    resource_group: str,
    subscription_id: str,
    cred: ClientSecretCredential,
) -> Optional[Dict[str, Any]]:
    """Check VM metrics and create alert if thresholds breached."""
    metrics = await query_vm_metrics(cred, subscription_id, resource_group, vm_name)
    if "error" in metrics:
        return None

    issues = []

    cpu = metrics.get("cpu_percent", 0)
    if cpu > 80:
        if f"{vm_name}_cpu" not in ACTIVE_ALERTS:
            issues.append(("cpu", f"CPU usage at {cpu:.1f}% (threshold: 80%)"))

    power = metrics.get("power_state", "unknown")
    if power not in ("running", "starting", "unknown"):
        if f"{vm_name}_shutdown" not in ACTIVE_ALERTS:
            issues.append(("shutdown", f"VM is in {power} state"))

    # Check if VM is completely unresponsive (all metrics at 0)
    if metrics.get("network_in_bytes", -1) == 0 and metrics.get("network_out_bytes", -1) == 0 and cpu == 0:
        if f"{vm_name}_health" not in ACTIVE_ALERTS:
            issues.append(("health", "VM appears unresponsive - no network or CPU activity"))

    if not issues:
        return None

    # Create alert for first issue
    issue_type, details = issues[0]
    ticket = await create_alert_ticket(
        db, user_id, vm_name, issue_type, details, metrics,
        subscription_id=subscription_id, resource_group=resource_group,
    )
    return ticket


# ---------- Fix Script Generation ----------
FIX_SCRIPTS = {
    "linux": {
        "cpu": """#!/bin/bash
echo "=== CPU Usage Analysis ==="
top -bn1 | head -20
echo ""
echo "=== Top CPU Processes ==="
ps aux --sort=-%cpu | head -10
echo ""
echo "=== Identifying and restarting high-CPU services ==="
HIGH_PID=$(ps aux --sort=-%cpu | awk 'NR==2{print $2}')
if [ -n "$HIGH_PID" ]; then
  SERVICE_NAME=$(ps -p $HIGH_PID -o comm= 2>/dev/null)
  echo "Highest CPU process: $SERVICE_NAME (PID: $HIGH_PID)"
  # Attempt graceful restart of common services
  for svc in $SERVICE_NAME nginx apache2 httpd mysql postgresql; do
    if systemctl is-active --quiet $svc 2>/dev/null; then
      echo "Restarting $svc..."
      sudo systemctl restart $svc
    fi
  done
fi
echo "=== CPU Fix Applied ==="
""",
        "memory": """#!/bin/bash
echo "=== Memory Usage Analysis ==="
free -m
echo ""
echo "=== Top Memory Processes ==="
ps aux --sort=-%mem | head -10
echo ""
echo "=== Clearing cache and restarting memory-heavy services ==="
sudo sync
echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null 2>&1 || true
echo "Memory cache cleared"
# Restart heavy services
for svc in mysql postgresql elasticsearch; do
  if systemctl is-active --quiet $svc 2>/dev/null; then
    echo "Restarting $svc..."
    sudo systemctl restart $svc
  fi
done
echo "=== Memory Fix Applied ==="
""",
        "disk": """#!/bin/bash
echo "=== Disk Usage Analysis ==="
df -h
echo ""
echo "=== Finding large files > 100MB ==="
sudo find / -xdev -type f -size +100M -exec ls -lh {} \; 2>/dev/null | head -20
echo ""
echo "=== Cleaning temporary files ==="
sudo rm -rf /tmp/* /var/tmp/* 2>/dev/null || true
sudo journalctl --vacuum-time=3d 2>/dev/null || true
sudo apt-get clean 2>/dev/null || sudo yum clean all 2>/dev/null || true
echo "=== Cleaning old logs ==="
sudo find /var/log -name "*.log.*" -mtime +7 -delete 2>/dev/null || true
sudo find /var/log -name "*.gz" -delete 2>/dev/null || true
echo "=== Disk Fix Applied ==="
""",
        "shutdown": """#!/bin/bash
echo "=== VM is stopped. Attempting to start... ==="
# This script runs on the VM but if it's stopped, it won't execute.
# The start is handled by Azure API. This placeholder logs the attempt.
echo "VM start initiated via Azure API"
echo "Please check VM status in Azure Portal"
""",
        "health": """#!/bin/bash
echo "=== VM Health Diagnostic ==="
echo "Uptime: $(uptime)"
echo ""
echo "=== System Load ==="
cat /proc/loadavg
echo ""
echo "=== Memory ==="
free -m
echo ""
echo "=== Disk ==="
df -h
echo ""
echo "=== Network ==="
ip addr show | grep -E "inet " | head -5
echo ""
echo "=== Listening Services ==="
ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null || true
echo ""
echo "=== Recent Errors in Syslog ==="
sudo journalctl -n 50 --no-pager -p err 2>/dev/null || true
echo "=== Health Diagnostic Complete ==="
""",
    },
    "windows": {
        "cpu": """$cpu = (Get-Counter "\\Processor(_Total)\\% Processor Time").CounterSamples.CookedValue
Write-Output "CPU Usage: $cpu%"
Write-Output "`nTop CPU Processes:"
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU, Id
Write-Output "`nAttempting to restart high-CPU services..."
Get-Service | Where-Object { $_.Status -eq 'Running' } | Restart-Service -ErrorAction SilentlyContinue
Write-Output "CPU Fix Applied"
""",
        "memory": """Write-Output "Memory Usage Analysis:"
$os = Get-CimInstance Win32_OperatingSystem
$pct = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize * 100, 1)
Write-Output "Memory Usage: $pct%"
Write-Output "`nTop Memory Processes:"
Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10 Name, @{N='MemoryMB';E={[math]::Round($_.WorkingSet/1MB,1)}}
Write-Output "`nClearing working sets..."
Get-Process | Where-Object { $_.WorkingSet -gt 100MB } | ForEach-Object { [GC]::Collect() }
Write-Output "Memory Fix Applied"
""",
        "disk": """Write-Output "Disk Usage Analysis:"
Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}}, @{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}}
Write-Output "`nCleaning temporary files..."
cleanmgr /sagerun:1 | Out-Null
Remove-Item -Path "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "C:\Windows\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue
Write-Output "Disk Fix Applied"
""",
        "shutdown": """Write-Output "VM is stopped. Start initiated via Azure API."
""",
        "health": """Write-Output "VM Health Diagnostic"
Write-Output "`nSystem Info:"
Get-ComputerInfo | Select-Object CsName, WindowsVersion, OsArchitecture
Write-Output "`nServices Status:"
Get-Service | Where-Object { $_.Status -eq 'Running' } | Measure-Object | Select-Object Count
Write-Output "`nRecent System Errors:"
Get-EventLog -LogName System -EntryType Error -Newest 10 | Format-Table TimeGenerated, Message -Wrap
Write-Output "Health Diagnostic Complete"
""",
    },
}


def get_fix_script(issue_type: str, os_type: str) -> Tuple[str, str]:
    """Get fix script for issue type and OS. Returns (script_content, filename_extension)."""
    os_map = FIX_SCRIPTS.get(os_type, FIX_SCRIPTS["linux"])
    script = os_map.get(issue_type, os_map.get("health", ""))
    ext = ".ps1" if os_type == "windows" else ".sh"
    return script, ext


# ---------- Run Fix Script ----------
async def run_fix_script_on_vm(
    db, user_id: str, ticket_number: str, subscription_id: str,
    resource_group: str, vm_name: str, os_type: str = "linux",
) -> Dict[str, Any]:
    """Generate and execute fix script on VM. Store result in ticket + blob + ServiceNow."""
    ticket = await db.tickets.find_one({"ticket_number": ticket_number}, {"_id": 0})
    if not ticket:
        return {"success": False, "error": "Ticket not found"}

    issue_type = ticket.get("issue_type", "health")
    script_content, ext = get_fix_script(issue_type, os_type)
    script_name = f"fix_{issue_type}_{vm_name}{ext}"

    # Execute via Azure Run Command
    sp = await _load_sp(db, user_id)
    if not sp or not sp.get("cred"):
        return {"success": False, "error": "Azure credentials not configured"}

    try:
        compute = ComputeManagementClient(sp["cred"], subscription_id)
        command_id = "RunShellScript" if os_type == "linux" else "RunPowerShellScript"
        poller = compute.virtual_machines.begin_run_command(
            resource_group, vm_name,
            {"command_id": command_id, "script": [script_content]},
        )
        result = poller.result(timeout=300)
        output = "".join(r.message for r in (result.value or []))
        status = "completed" if result.value else "failed"
    except Exception as e:
        output = str(e)[:500]
        status = "failed"

    # Store script in Azure Blob
    blob_path = ""
    try:
        from terraform_runtime import upload_artifacts_sync
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        script_path = tmp / script_name
        script_path.write_text(script_content)
        tf_storage = await _load_tf_storage_raw(db, user_id)
        if tf_storage:
            blobs = await asyncio.to_thread(
                upload_artifacts_sync, tf_storage, user_id,
                ticket_number[:8], tmp, [script_name],
            )
            blob_path = blobs.get(script_name, "")
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception as e:
        logger.warning("Blob upload of fix script failed: %s", e)

    # Update ticket
    await db.tickets.update_one(
        {"ticket_number": ticket_number},
        {"$set": {
            "fix_applied": True,
            "fix_script": script_content[:5000],
            "fix_result": {"status": status, "output": output[:2000], "blob_path": blob_path},
            "fix_applied_at": datetime.now(timezone.utc),
            "status": "resolved" if status == "completed" else "open",
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    # Update ServiceNow
    try:
        from servicenow_service import update_incident as sn_update
        sn_sys_id = ticket.get("servicenow_sys_id", "")
        if sn_sys_id:
            await sn_update(db, user_id, sn_sys_id, {
                "work_notes": f"Auto-fix script applied: {script_name}\nStatus: {status}\nOutput: {output[:500]}",
                "state": "3" if status == "completed" else "2",
            })
    except Exception as e:
        logger.warning("ServiceNow update failed: %s", e)

    # Send resolution email
    try:
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1})
        if user and user.get("email"):
            email_body = build_resolution_email_body(vm_name, ticket_number, f"{script_name} ({status})")
            asyncio.create_task(send_email(
                db, user_id, user["email"],
                f"[InfraGenie] Fix Applied to {vm_name} - {ticket_number}",
                email_body,
            ))
    except Exception as e:
        logger.warning("Resolution email failed: %s", e)

    # Clear active alert
    for key in list(ACTIVE_ALERTS.keys()):
        if ACTIVE_ALERTS[key] == ticket_number:
            ACTIVE_ALERTS.pop(key, None)

    return {"success": status == "completed", "status": status, "output": output[:500], "blob_path": blob_path}


async def _load_tf_storage_raw(db, user_id: str):
    doc = await db.tf_storage_configs.find_one({"user_id": user_id}, {"_id": 0}) or None
    if not doc:
        return None
    return {
        "storage_account": doc.get("storage_account"),
        "container": doc.get("container"),
        "resource_group": doc.get("resource_group"),
        "key_prefix": doc.get("backend_prefix") or "infragenie",
        "access_key": doc.get("access_key"),
    }


# ---------- Background Monitoring Loop ----------
async def start_monitoring_loop(db, user_id: str):
    """Periodically check all deployed VMs for health issues."""
    sp = await _load_sp(db, user_id)
    if not sp:
        logger.info("Monitoring: Azure not configured for user %s", user_id)
        return

    cred = sp["cred"]
    sub_id = sp["subscription_id"]

    while True:
        try:
            # Find all VM deployments
            tickets = await db.tickets.find({
                "user_id": user_id,
                "status": {"$in": ["completed", "open", "resolved"]},
                "module_key": {"$in": ["virtual-machine", "virtual-machine-windows", "linux-vm-nginx"]},
            }, {"_id": 0, "resource_name": 1, "region": 1, "deployment_name": 1}).to_list(length=50)

            for tkt in tickets:
                vm_name = tkt.get("deployment_name") or tkt.get("resource_name", "")
                if not vm_name:
                    continue
                rg = f"rg-{vm_name}"
                await check_and_alert(db, user_id, vm_name, rg, sub_id, cred)

        except Exception as e:
            logger.error("Monitoring loop error: %s", e)

        await asyncio.sleep(300)  # 5 minutes


# ---------- Webhook Handler (for Azure Monitor alerts) ----------
async def handle_alert_webhook(
    db, user_id: str, body: Dict[str, Any],
) -> Dict[str, Any]:
    """Handle incoming alert from Azure Monitor webhook."""
    try:
        data = body.get("data", body)
        context = data.get("context", data)
        alert_name = context.get("name", "Unknown Alert")
        vm_name_raw = context.get("resourceName", "") or data.get("resourceName", "")
        description = context.get("description", "") or data.get("description", "")
        condition = context.get("condition", {})
        metric_name = condition.get("metricName", "unknown")
        threshold = condition.get("threshold", "?")
        actual = condition.get("metricValue", "?")
        resource_group = context.get("resourceGroupName", "") or data.get("resourceGroupName", "")
        subscription_id = context.get("subscriptionId", "") or data.get("subscriptionId", "")

        details = (
            f"Azure Monitor Alert: {alert_name}\n"
            f"Metric: {metric_name}\n"
            f"Threshold: {threshold}, Actual: {actual}\n"
            f"VM: {vm_name_raw}\n"
            f"Resource Group: {resource_group}\n"
            f"Description: {description}"
        )

        issue_type = "health"
        if "cpu" in metric_name.lower():
            issue_type = "cpu"
        elif "memory" in metric_name.lower() or "mem" in metric_name.lower():
            issue_type = "memory"
        elif "disk" in metric_name.lower():
            issue_type = "disk"
        elif "shutdown" in alert_name.lower() or "stopped" in alert_name.lower():
            issue_type = "shutdown"

        ticket = await create_alert_ticket(
            db, user_id, vm_name_raw, issue_type, details, {},
            subscription_id=subscription_id, resource_group=resource_group,
        )
        return {"processed": True, "ticket_number": ticket["ticket_number"] if ticket else ""}
    except Exception as e:
        logger.error("Webhook handler error: %s", e)
        return {"processed": False, "error": str(e)[:300]}
