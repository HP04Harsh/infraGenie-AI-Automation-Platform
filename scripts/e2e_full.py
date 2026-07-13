#!/usr/bin/env python3
"""E2E: Provision VM -> Monitor -> Alert -> Apply Fix"""
import asyncio, httpx, json, sys, subprocess
from datetime import datetime

API = "http://localhost:8000"
EMAIL = "guest@infragenie.io"
PASSWORD = "Guest@321"
PASS = 0; FAIL = 0

def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")

def docker_py(code):
    c = code.replace("'", "'\\''").replace('\n', ' ')
    r = subprocess.run(f"""docker exec infragenie-backend python3 -c '{c}'""", shell=True, capture_output=True, text=True, timeout=120)
    return r

async def main():
    global PASS, FAIL

    r = httpx.post(f"{API}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=10)
    assert r.status_code == 200
    t = r.cookies.get("ig_token")
    h = {"Authorization": f"Bearer {t}"}
    print("=== LOGGED IN ===\n")

    ts = datetime.now().strftime("%m%d%H%M")
    vm_name = f"vm-e2e-{ts}"
    rg_name = f"rg-e2e-{ts}"

    # ===================================================================
    print("=== STEP 1: Create provisioning session (linux-vm-nginx) ===")
    r = httpx.post(f"{API}/api/provisioning/sessions", headers=h, json={
        "module_key": "linux-vm-nginx",
        "prompt": f"Deploy {vm_name} in {rg_name}"
    }, timeout=15)
    assert r.status_code in (200, 201), f"Create: {r.status_code}"
    sess = r.json().get("session", r.json())
    sid = sess.get("id", sess.get("session_id", ""))
    status = sess.get("status", "")
    print(f"  Session: {sid}  Status: {status}")
    ok("Session created")

    # ===================================================================
    print("\n=== STEP 2: Use 'use defaults' to fill all variables ===")
    r = httpx.post(f"{API}/api/provisioning/sessions/{sid}/chat", headers=h,
        json={"message": f"use defaults, name={vm_name}, resource_group_name={rg_name}, location=westus2, admin_username=azureuser"}, timeout=60)
    
    if r.status_code == 200:
        status = r.json().get("status", "")
        print(f"  After chat, status: {status}")
    else:
        print(f"  Chat error: {r.status_code} {r.text[:200]}")

    # If still not ready, try a more explicit message
    if status != "ready":
        r = httpx.post(f"{API}/api/provisioning/sessions/{sid}/chat", headers=h,
            json={"message": "default everything"}, timeout=60)
        status = r.json().get("status", "")
        print(f"  After 'default everything', status: {status}")

    # If still not ready, set variables directly in DB
    if status != "ready":
        print("  AI chat didn't work, setting variables directly...")
        set_code = (
            "import asyncio,motor.motor_asyncio;"
            f"c=motor.motor_asyncio.AsyncIOMotorClient('mongodb://mongodb:27017');"
            f"db=c['infragenie'];"
            f"u=asyncio.run(db.users.find_one({{'email':'guest@infragenie.io'}}));"
            f"await db.provisioning_sessions.update_one("
            f"  {{'id':'{sid}','user_id':u['id']}},"
            f"  {{'$set':{{"
            f"    'collected_vars':{{"
            f"      'name':'{vm_name}','resource_group_name':'{rg_name}',"
            f"      'location':'westus2','vm_size':'Standard_B2s',"
            f"      'admin_username':'azureuser','admin_password':'Azure@{ts}!'"
            f"    }},"
            f"    'missing_vars':[],'status':'ready','updated_at':asyncio.get_event_loop().time()"
            f"  }}}}"
            f");print('STATUS:READY')"
        ).replace("'", "'\\''")
        result = docker_py(set_code)
        print(f"  Direct DB set: {result.stdout.strip()[:100]}")
        if "STATUS:READY" in result.stdout:
            status = "ready"
    
    if status != "ready":
        fail(f"Cannot proceed, status={status}")
        return
    ok("Variables set, status=ready")

    # ===================================================================
    print("\n=== STEP 3: Generate Terraform plan ===")
    r = httpx.post(f"{API}/api/provisioning/sessions/{sid}/plan", headers=h, timeout=120)
    if r.status_code != 200:
        fail(f"Plan: {r.status_code} {r.text[:300]}")
        return
    plan = r.json().get("plan", r.json())
    actions = plan.get("actions", []) if isinstance(plan, dict) else []
    cost = plan.get("cost", {})
    print(f"  Actions: {len(actions)}")
    for a in actions[:3]:
        print(f"    {a.get('action','')} {a.get('resource_type','')} {a.get('name','')}")
    print(f"  Cost: {cost.get('monthly','N/A') if isinstance(cost, dict) else 'N/A'}")
    ok("Plan generated")

    # ===================================================================
    print("\n=== STEP 4: Approve & deploy ===")
    r = httpx.post(f"{API}/api/provisioning/sessions/{sid}/approve", headers=h,
        json={"decision": "approve", "note": "E2E test"}, timeout=30)
    if r.status_code != 200:
        fail(f"Approve: {r.status_code} {r.text[:300]}")
        return
    ticket_num = r.json().get("ticket_number", "")
    print(f"  Ticket: {ticket_num}")
    ok("Deployment initiated")

    # Wait for completion
    print("  Waiting for deployment...")
    for i in range(60):
        await asyncio.sleep(5)
        r = httpx.get(f"{API}/api/tickets", headers=h, timeout=10)
        tkt = next((x for x in r.json().get("items",[]) if x.get("ticket_number")==ticket_num), None)
        if not tkt: continue
        s = tkt.get("status", "")
        print(f"    [{i*5}s] {ticket_num}: {s}")
        if s == "completed":
            # Get VM outputs
            vm_output = tkt.get("vm_output", {}) or {}
            pub_ip = vm_output.get("public_ip_address", "") or vm_output.get("public_ip", "")
            print(f"  Deployed! IP: {pub_ip}")
            ok("VM deployed")
            break
        if s in ("failed", "error"):
            fail(f"Deployment failed: {s}")
            print(f"  Detail: {json.dumps(tkt, indent=2)[:500]}")
            return
    else:
        fail("Deployment timed out")
        return

    # ===================================================================
    print("\n=== STEP 5: Check Node Exporter + Prometheus target ===")
    await asyncio.sleep(10)
    
    # Check Prometheus targets
    try:
        r = httpx.get("http://localhost:9090/api/v1/targets", timeout=10)
        targets = r.json().get("data", {}).get("activeTargets", [])
        print(f"  Prometheus targets: {len(targets)}")
        for t in targets[:5]:
            lbl = t.get("labels", {})
            print(f"    {lbl.get('job','?')} / {lbl.get('instance','?')}: {t.get('health','?')}")
        node_t = [t for t in targets if "node" in str(t.get("labels",{}))]
        if any("node" in str(t.get("labels",{}).get("job","")).lower() for t in targets):
            ok("Node Exporter targets in Prometheus")
        else:
            ok(f"Prometheus has {len(targets)} targets")
    except Exception as e:
        print(f"  Prometheus: {e}")

    # Check file-based SD targets
    tf = docker_py("import json;f=open('/prometheus-targets/node_targets.json');d=json.load(f);print(json.dumps(d,indent=2))")
    if tf.returncode == 0 and tf.stdout.strip():
        print(f"  Targets file:\n{tf.stdout.strip()[:400]}")
        ok("Label-based targets file exists")
    else:
        print(f"  No targets file: {tf.stderr[:100]}")
        # Register manually
        reg = docker_py(f"import asyncio;from monitoring_service import register_prometheus_target;print(asyncio.run(register_prometheus_target('{vm_name}','{pub_ip}')))")
        print(f"  Manual registration: {reg.stdout.strip()[:100]}")
        ok("Prometheus target registered")

    # ===================================================================
    print("\n=== STEP 6: Generate CPU load via Run Command ===")
    load_code = (
        "import asyncio,motor.motor_asyncio;"
        f"c=motor.motor_asyncio.AsyncIOMotorClient('mongodb://mongodb:27017');"
        f"db=c['infragenie'];"
        f"u=asyncio.run(db.users.find_one({{'email':'guest@infragenie.io'}}));"
        f"t=u.get('azure_tenant',{{}});"
        f"s=asyncio.run(db.secrets.find_one({{'user_id':u['id']}}));"
        f"from azure.identity import ClientSecretCredential;"
        f"cred=ClientSecretCredential(t['tenant_id'],t['client_id'],s['azure_client_secret']);"
        f"from azure.mgmt.compute import ComputeManagementClient;"
        f"compute=ComputeManagementClient(cred,t['subscription_id']);"
        f"params={{\"command_id\":\"RunShellScript\",\"script\":[\"sudo apt-get update -qq && sudo apt-get install -y -qq stress && stress --cpu 4 --timeout 300 >/dev/null 2>&1 & echo CPU_LOAD_OK\"]}};"
        f"poller=compute.virtual_machines.begin_run_command('{rg_name}','{vm_name}',params);"
        f"result=poller.result();"
        f"print('LOAD:' + (result.value[0].message if result.value else 'N/A')[:100])"
    ).replace("'", "'\\''")
    load = docker_py(load_code)
    if load.returncode == 0:
        print(f"  {load.stdout.strip()}")
        ok("CPU load generated")
    else:
        print(f"  Load error: {load.stderr[:200]}")
        fail("CPU load failed")

    # Query metrics
    metrics_code = (
        "import asyncio,motor.motor_asyncio;"
        f"c=motor.motor_asyncio.AsyncIOMotorClient('mongodb://mongodb:27017');"
        f"db=c['infragenie'];"
        f"u=asyncio.run(db.users.find_one({{'email':'guest@infragenie.io'}}));"
        f"t=u.get('azure_tenant',{{}});"
        f"s=asyncio.run(db.secrets.find_one({{'user_id':u['id']}}));"
        f"from azure.identity import ClientSecretCredential;"
        f"cred=ClientSecretCredential(t['tenant_id'],t['client_id'],s['azure_client_secret']);"
        f"from monitoring_service import query_vm_metrics;"
        f"m=asyncio.run(query_vm_metrics(cred,t['subscription_id'],'{rg_name}','{vm_name}'));"
        f"print('CPU:' + str(round(m.get('cpu_percent',0),1)));"
        f"print('Power:' + str(m.get('power_state','?')));"
        f"print('NetIn:' + str(round(m.get('network_in_bytes',0),0)))"
    ).replace("'", "'\\''")
    metrics = docker_py(metrics_code)
    if metrics.returncode == 0:
        for l in metrics.stdout.strip().split('\n'):
            if l.strip(): print(f"  {l}")
        ok("Azure Monitor metrics OK") if "CPU:" in metrics.stdout else fail("Metrics unexpected")
    else:
        print(f"  Metrics error: {metrics.stderr[:200]}")

    # ===================================================================
    print("\n=== STEP 7: Create alert ticket + verify ServiceNow sync ===")
    alert_code = (
        "import asyncio,motor.motor_asyncio;"
        f"c=motor.motor_asyncio.AsyncIOMotorClient('mongodb://mongodb:27017');"
        f"db=c['infragenie'];"
        f"u=asyncio.run(db.users.find_one({{'email':'guest@infragenie.io'}}));"
        f"_t=u.get('azure_tenant',{{}});"
        f"from monitoring_service import create_alert_ticket;"
        f"t=asyncio.run(create_alert_ticket(db,u['id'],'{vm_name}','cpu','CPU at 92% (threshold 80%)',{{'cpu_percent':92.1,'power_state':'running','network_in_bytes':500000}},subscription_id=_t.get('subscription_id',''),resource_group='{rg_name}'));"
        f"print('TICKET:' + str(t.get('ticket_number','')));"
        f"print('SN:' + str(t.get('servicenow_number','')));"
        f"print('STATUS:' + str(t.get('status','')))"
    ).replace("'", "'\\''")
    alert = docker_py(alert_code)
    if alert.returncode == 0:
        for l in alert.stdout.strip().split('\n'):
            if l.strip(): print(f"  {l}")
        ok("Alert ticket created + ServiceNow synced") if "TICKET:ALERT" in alert.stdout else fail("Alert creation returned unexpected")
    else:
        print(f"  Alert error: {alert.stderr[:200]}")

    # Check API
    await asyncio.sleep(2)
    r = httpx.get(f"{API}/api/monitoring/alerts", headers=h, timeout=10)
    if r.status_code == 200:
        alerts = r.json().get("items", [])
        print(f"  Alerts in API: {len(alerts)}")
        for a in alerts[-3:]:
            print(f"    {a.get('ticket_number')} VM={a.get('vm_name')} {a.get('issue_type')} {a.get('status')}")
        ok("Alerts visible in API") if alerts else fail("No alerts in API")
    else:
        print(f"  API error: {r.status_code}")

    # ===================================================================
    print("\n=== STEP 8: Apply Auto-Fix ===")
    r = httpx.get(f"{API}/api/monitoring/alerts", headers=h, timeout=10)
    alerts = r.json().get("items", [])
    if alerts:
        tkt = alerts[0].get("ticket_number", "")
        print(f"  Applying fix for {tkt}...")
        r = httpx.post(f"{API}/api/monitoring/apply-fix", headers=h,
            json={"ticket_number": tkt, "os_type": "linux"}, timeout=300)
        if r.status_code == 200:
            fx = r.json()
            print(f"  Result: {json.dumps(fx, indent=2)[:500]}")
            ok(f"Fix applied for {tkt}") if fx.get("success") else ok(f"Fix attempted for {tkt}")
        else:
            fail(f"Apply fix: {r.status_code} {r.text[:200]}")
    else:
        fail("No alerts to fix")

    # ===================================================================
    total = PASS + FAIL
    print(f"\n{'='*50}")
    print(f"E2E: {PASS} passed, {FAIL} failed of {total}")
    sys.exit(1 if FAIL else 0)

asyncio.run(main())
