#!/usr/bin/env python3
"""
InfraGenie Provisioning Agent — Backend E2E Test Suite
Tests the async refactor with polling for status transitions.
"""
import os
import sys
import time
import requests
from typing import Optional, Dict, Any

# Load backend URL from frontend .env
BACKEND_URL = None
env_path = "/app/frontend/.env"
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BACKEND_URL = line.split("=", 1)[1].strip()
                break

if not BACKEND_URL:
    print("❌ REACT_APP_BACKEND_URL not found in /app/frontend/.env")
    sys.exit(1)

BASE_URL = f"{BACKEND_URL}/api"
print(f"🔗 Testing backend at: {BASE_URL}\n")

# Test credentials
TEST_EMAIL = "guest@infragenie.io"
TEST_PASSWORD = "Guest@321"

# Global session
session = requests.Session()
session.headers.update({"Content-Type": "application/json"})

# Test results
results = {
    "passed": [],
    "failed": [],
    "warnings": [],
}


def log_pass(test_name: str, detail: str = ""):
    msg = f"✅ {test_name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results["passed"].append(test_name)


def log_fail(test_name: str, detail: str):
    msg = f"❌ {test_name} — {detail}"
    print(msg)
    results["failed"].append(f"{test_name}: {detail}")


def log_warn(test_name: str, detail: str):
    msg = f"⚠️  {test_name} — {detail}"
    print(msg)
    results["warnings"].append(f"{test_name}: {detail}")


def poll_session(session_id: str, target_statuses: list, timeout: int = 90, interval: int = 2) -> Optional[Dict[str, Any]]:
    """Poll GET /api/provisioning/sessions/{id} until status is in target_statuses or timeout."""
    start = time.time()
    last_status = None
    while time.time() - start < timeout:
        try:
            resp = session.get(f"{BASE_URL}/provisioning/sessions/{session_id}", timeout=10)
            if resp.status_code != 200:
                log_warn("poll_session", f"GET session returned {resp.status_code}")
                time.sleep(interval)
                continue
            data = resp.json()
            current_status = data.get("status")
            if current_status != last_status:
                print(f"   📊 Session status: {current_status}")
                last_status = current_status
            if current_status in target_statuses:
                return data
            time.sleep(interval)
        except Exception as e:
            log_warn("poll_session", f"Exception during poll: {e}")
            time.sleep(interval)
    log_fail("poll_session", f"Timeout waiting for status in {target_statuses} (last: {last_status})")
    return None


def test_auth():
    """Test 1: Auth (login + me)"""
    print("\n🔐 Test 1: Auth (login + me)")
    try:
        resp = session.post(f"{BASE_URL}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}, timeout=10)
        if resp.status_code != 200:
            log_fail("Auth login", f"Status {resp.status_code}: {resp.text[:200]}")
            return False
        data = resp.json()
        if "user" not in data or data["user"]["email"] != TEST_EMAIL:
            log_fail("Auth login", "Response missing user or email mismatch")
            return False
        log_pass("Auth login", f"User: {data['user']['name']} ({data['user']['email']})")

        # Test /auth/me
        resp = session.get(f"{BASE_URL}/auth/me", timeout=10)
        if resp.status_code != 200:
            log_fail("Auth me", f"Status {resp.status_code}")
            return False
        me = resp.json()
        if me["email"] != TEST_EMAIL:
            log_fail("Auth me", "Email mismatch")
            return False
        log_pass("Auth me", f"Role: {me['role']}")
        return True
    except Exception as e:
        log_fail("Auth", str(e))
        return False


def test_catalog():
    """Test 2: Catalog"""
    print("\n📦 Test 2: Provisioning Catalog")
    try:
        resp = session.get(f"{BASE_URL}/provisioning/catalog", timeout=10)
        if resp.status_code != 200:
            log_fail("Catalog", f"Status {resp.status_code}")
            return False
        data = resp.json()
        items = data.get("items", [])
        if len(items) != 15:
            log_fail("Catalog", f"Expected 15 modules, got {len(items)}")
            return False
        module_keys = [m["key"] for m in items]
        expected = ["virtual-machine-linux", "storage-account", "sql-database"]
        for key in expected:
            if key not in module_keys:
                log_fail("Catalog", f"Missing module: {key}")
                return False
        log_pass("Catalog", f"15 modules returned: {', '.join(module_keys[:3])}...")
        return True
    except Exception as e:
        log_fail("Catalog", str(e))
        return False


def test_happy_path():
    """Test 3-9: Happy path (start → chat → plan → approve → completed)"""
    print("\n🚀 Test 3-9: Happy Path (start → chat → plan → approve → completed)")
    
    # Step 3: Start session with comprehensive prompt
    print("\n   Step 3: POST /api/provisioning/sessions (start)")
    try:
        prompt = (
            "Provision a Linux VM in Central India for prod-app, size Standard_B2s, "
            "admin user azureuser, name vm-prod-app-01, os Ubuntu 22.04 LTS, "
            "ssh key ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC test@example.com, "
            "resource group rg-prod-app, subnet /subscriptions/test-sub/resourceGroups/rg-prod-app/providers/Microsoft.Network/virtualNetworks/vnet-prod/subnets/default"
        )
        start_time = time.time()
        resp = session.post(f"{BASE_URL}/provisioning/sessions", json={"prompt": prompt}, timeout=10)
        elapsed = time.time() - start_time
        
        if resp.status_code != 200:
            log_fail("Start session", f"Status {resp.status_code}: {resp.text[:200]}")
            return None
        
        if elapsed > 5:
            log_warn("Start session", f"Took {elapsed:.1f}s (expected <5s)")
        else:
            log_pass("Start session response time", f"{elapsed:.2f}s")
        
        data = resp.json()
        session_id = data.get("id")
        if not session_id:
            log_fail("Start session", "No session ID returned")
            return None
        
        status = data.get("status")
        if status not in ["thinking", "collecting", "ready_for_plan"]:
            log_warn("Start session", f"Unexpected initial status: {status}")
        
        log_pass("Start session", f"Session {session_id[:8]}... created with status={status}")
        
        # Step 4: Poll until status leaves "thinking"
        print("\n   Step 4: Poll for AI classification")
        sess = poll_session(session_id, ["collecting", "ready_for_plan", "failed"], timeout=90)
        if not sess:
            return None
        
        final_status = sess.get("status")
        module_key = sess.get("module_key")
        collected_vars = sess.get("collected_vars", {})
        missing_vars = sess.get("missing_vars", [])
        
        if module_key != "virtual-machine-linux":
            log_fail("AI classification", f"Expected 'virtual-machine-linux', got '{module_key}'")
            return None
        
        log_pass("AI classification", f"Module: {module_key}, Status: {final_status}")
        log_pass("Variable extraction", f"Collected {len(collected_vars)} vars, Missing {len(missing_vars)}")
        
        # Step 5: If still collecting, do one chat round
        if final_status == "collecting" and missing_vars:
            print(f"\n   Step 5: POST /api/provisioning/sessions/{session_id[:8]}.../chat")
            # Provide missing vars
            chat_msg = "resource group is rg-prod-app"
            if "ssh_public_key" in missing_vars:
                chat_msg += ", ssh key is ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC test@example.com"
            
            start_time = time.time()
            resp = session.post(f"{BASE_URL}/provisioning/sessions/{session_id}/chat", 
                              json={"message": chat_msg}, timeout=10)
            elapsed = time.time() - start_time
            
            if resp.status_code != 200:
                log_fail("Chat", f"Status {resp.status_code}")
                return None
            
            if elapsed > 5:
                log_warn("Chat", f"Took {elapsed:.1f}s (expected <5s)")
            else:
                log_pass("Chat response time", f"{elapsed:.2f}s")
            
            # Poll again
            sess = poll_session(session_id, ["ready_for_plan", "collecting", "failed"], timeout=90)
            if not sess:
                return None
            final_status = sess.get("status")
            log_pass("Chat round", f"Status after chat: {final_status}")
        
        if final_status != "ready_for_plan":
            log_fail("Session readiness", f"Expected 'ready_for_plan', got '{final_status}'")
            return None
        
        # Step 6: Generate plan
        print(f"\n   Step 6: POST /api/provisioning/sessions/{session_id[:8]}.../plan")
        start_time = time.time()
        resp = session.post(f"{BASE_URL}/provisioning/sessions/{session_id}/plan", json={}, timeout=10)
        elapsed = time.time() - start_time
        
        if resp.status_code != 200:
            log_fail("Plan generation", f"Status {resp.status_code}: {resp.text[:200]}")
            return None
        
        if elapsed > 5:
            log_warn("Plan generation", f"Took {elapsed:.1f}s (expected <5s)")
        else:
            log_pass("Plan generation response time", f"{elapsed:.2f}s")
        
        plan_resp = resp.json()
        if plan_resp.get("status") != "planning":
            log_warn("Plan generation", f"Expected status='planning', got '{plan_resp.get('status')}'")
        
        log_pass("Plan generation", "Returned immediately with status=planning")
        
        # Step 7: Poll for plan completion
        print("\n   Step 7: Poll for plan completion (up to 90s)")
        sess = poll_session(session_id, ["awaiting_approval", "ready_for_plan", "failed"], timeout=90)
        if not sess:
            return None
        
        final_status = sess.get("status")
        if final_status == "ready_for_plan":
            plan_error = sess.get("plan_error")
            log_fail("Plan generation", f"AI plan failed: {plan_error}")
            return None
        
        if final_status != "awaiting_approval":
            log_fail("Plan generation", f"Expected 'awaiting_approval', got '{final_status}'")
            return None
        
        plan = sess.get("plan", {})
        ticket_id = sess.get("ticket_id")
        
        if not ticket_id:
            log_fail("Plan generation", "No ticket_id in session")
            return None
        
        summary = plan.get("summary", "")
        cost = plan.get("cost", {})
        monthly = cost.get("monthly_total", 0)
        currency = cost.get("currency", "USD")
        security_score = plan.get("security", {}).get("score", 0)
        
        log_pass("Plan generation", f"Plan ready: {summary}")
        log_pass("Cost estimation", f"{monthly} {currency}/month, Security score: {security_score}")
        log_pass("Ticket creation", f"Ticket {ticket_id[:8]}... created")
        
        # Step 8: Approve
        print(f"\n   Step 8: POST /api/provisioning/sessions/{session_id[:8]}.../approve")
        start_time = time.time()
        resp = session.post(f"{BASE_URL}/provisioning/sessions/{session_id}/approve", 
                          json={"decision": "approve"}, timeout=10)
        elapsed = time.time() - start_time
        
        if resp.status_code != 200:
            log_fail("Approval", f"Status {resp.status_code}")
            return None
        
        if elapsed > 5:
            log_warn("Approval", f"Took {elapsed:.1f}s (expected <5s)")
        else:
            log_pass("Approval response time", f"{elapsed:.2f}s")
        
        approve_resp = resp.json()
        if approve_resp.get("status") != "applying":
            log_warn("Approval", f"Expected status='applying', got '{approve_resp.get('status')}'")
        
        log_pass("Approval", "Returned immediately with status=applying")
        
        # Step 9: Poll for completion
        print("\n   Step 9: Poll for deployment completion (up to 90s)")
        sess = poll_session(session_id, ["completed", "failed"], timeout=90)
        if not sess:
            return None
        
        final_status = sess.get("status")
        if final_status != "completed":
            log_fail("Deployment", f"Expected 'completed', got '{final_status}'")
            return None
        
        apply_data = sess.get("apply", {})
        outputs = apply_data.get("outputs", {})
        elapsed_secs = apply_data.get("elapsed_seconds", 0)
        
        log_pass("Deployment", f"Completed in {elapsed_secs}s with {len(outputs)} outputs")
        
        return {"session_id": session_id, "ticket_id": ticket_id}
        
    except Exception as e:
        log_fail("Happy path", str(e))
        return None


def test_tickets(ticket_id: str):
    """Test 10-12: Tickets (list, detail, comment)"""
    print("\n🎫 Test 10-12: Tickets")
    
    # Test 10: List tickets
    print("\n   Test 10: GET /api/tickets")
    try:
        resp = session.get(f"{BASE_URL}/tickets", timeout=10)
        if resp.status_code != 200:
            log_fail("Tickets list", f"Status {resp.status_code}")
            return False
        data = resp.json()
        items = data.get("items", [])
        if len(items) == 0:
            log_fail("Tickets list", "No tickets returned")
            return False
        log_pass("Tickets list", f"{len(items)} tickets returned")
    except Exception as e:
        log_fail("Tickets list", str(e))
        return False
    
    # Test 11: Get ticket detail
    print(f"\n   Test 11: GET /api/tickets/{ticket_id[:8]}...")
    try:
        resp = session.get(f"{BASE_URL}/tickets/{ticket_id}", timeout=10)
        if resp.status_code != 200:
            log_fail("Ticket detail", f"Status {resp.status_code}")
            return False
        ticket = resp.json()
        
        # Verify structure
        required_fields = ["id", "ticket_number", "status", "timeline", "tfvars", "plan", "outputs", "logs"]
        for field in required_fields:
            if field not in ticket:
                log_fail("Ticket detail", f"Missing field: {field}")
                return False
        
        timeline = ticket.get("timeline", [])
        outputs = ticket.get("outputs", {})
        logs = ticket.get("logs", [])
        status = ticket.get("status")
        
        log_pass("Ticket detail", f"Status: {status}, Timeline: {len(timeline)} events, Outputs: {len(outputs)}, Logs: {len(logs)} lines")
        
        if status != "completed":
            log_warn("Ticket detail", f"Expected status='completed', got '{status}'")
        
    except Exception as e:
        log_fail("Ticket detail", str(e))
        return False
    
    # Test 12: Add comment
    print(f"\n   Test 12: POST /api/tickets/{ticket_id[:8]}.../comment")
    try:
        resp = session.post(f"{BASE_URL}/tickets/{ticket_id}/comment", 
                          json={"text": "Automated test comment - deployment looks good!"}, timeout=10)
        if resp.status_code != 200:
            log_fail("Ticket comment", f"Status {resp.status_code}")
            return False
        data = resp.json()
        if not data.get("ok"):
            log_fail("Ticket comment", "Response ok=false")
            return False
        log_pass("Ticket comment", "Comment added successfully")
    except Exception as e:
        log_fail("Ticket comment", str(e))
        return False
    
    return True


def test_jobs():
    """Test 13: Jobs list"""
    print("\n📋 Test 13: Provisioning Jobs")
    try:
        resp = session.get(f"{BASE_URL}/provisioning/jobs", timeout=10)
        if resp.status_code != 200:
            log_fail("Jobs list", f"Status {resp.status_code}")
            return False
        data = resp.json()
        items = data.get("items", [])
        if len(items) == 0:
            log_warn("Jobs list", "No jobs returned (expected at least 1 from happy path)")
        else:
            log_pass("Jobs list", f"{len(items)} jobs returned")
        return True
    except Exception as e:
        log_fail("Jobs list", str(e))
        return False


def test_terraform_storage():
    """Test 14-15: Terraform Storage settings"""
    print("\n🗄️  Test 14-15: Terraform Storage Settings")
    
    # Test 14: Save config
    print("\n   Test 14: POST /api/settings/terraform-storage")
    try:
        config = {
            "storage_account": "infrageniestg",
            "resource_group": "rg-infragenie-prod",
            "container": "tfstate",
            "access_key": "test-access-key-12345",
            "key_prefix": "infragenie"
        }
        resp = session.post(f"{BASE_URL}/settings/terraform-storage", json=config, timeout=10)
        if resp.status_code != 200:
            log_fail("TF Storage save", f"Status {resp.status_code}: {resp.text[:200]}")
            return False
        data = resp.json()
        if not data.get("ok") or data.get("status") != "connected":
            log_fail("TF Storage save", f"Expected ok=true and status=connected, got {data}")
            return False
        log_pass("TF Storage save", "Config saved with status=connected")
    except Exception as e:
        log_fail("TF Storage save", str(e))
        return False
    
    # Test 15: Get config
    print("\n   Test 15: GET /api/settings/terraform-storage")
    try:
        resp = session.get(f"{BASE_URL}/settings/terraform-storage", timeout=10)
        if resp.status_code != 200:
            log_fail("TF Storage get", f"Status {resp.status_code}")
            return False
        data = resp.json()
        if not data.get("has_access_key"):
            log_fail("TF Storage get", "has_access_key should be true")
            return False
        if "access_key" in data:
            log_fail("TF Storage get", "access_key should not be exposed")
            return False
        log_pass("TF Storage get", "Config retrieved with secrets masked")
    except Exception as e:
        log_fail("TF Storage get", str(e))
        return False
    
    return True


def test_ai_config():
    """Test 16-17: AI Config settings"""
    print("\n🤖 Test 16-17: AI Config Settings")
    
    # Test 16: Get config
    print("\n   Test 16: GET /api/settings/ai-config")
    try:
        resp = session.get(f"{BASE_URL}/settings/ai-config", timeout=10)
        if resp.status_code != 200:
            log_fail("AI Config get", f"Status {resp.status_code}")
            return False
        data = resp.json()
        if data.get("provider") != "azure_openai":
            log_warn("AI Config get", f"Expected provider=azure_openai, got {data.get('provider')}")
        if not data.get("has_api_key"):
            log_warn("AI Config get", "has_api_key is false")
        if "api_key" in data:
            log_fail("AI Config get", "api_key should not be exposed")
            return False
        log_pass("AI Config get", f"Provider: {data.get('provider')}, Deployment: {data.get('deployment')}")
    except Exception as e:
        log_fail("AI Config get", str(e))
        return False
    
    # Test 17: Update config (use existing values to avoid breaking)
    print("\n   Test 17: POST /api/settings/ai-config")
    try:
        # Get current config first
        resp = session.get(f"{BASE_URL}/settings/ai-config", timeout=10)
        current = resp.json()
        
        # Update with same values (idempotent)
        config = {
            "provider": current.get("provider", "azure_openai"),
            "endpoint": current.get("endpoint", "https://infragenie.openai.azure.com/openai/v1"),
            "deployment": current.get("deployment", "gpt-5"),
            "api_key": ""  # Empty means keep existing
        }
        resp = session.post(f"{BASE_URL}/settings/ai-config", json=config, timeout=10)
        if resp.status_code != 200:
            log_fail("AI Config save", f"Status {resp.status_code}: {resp.text[:200]}")
            return False
        data = resp.json()
        if not data.get("ok"):
            log_fail("AI Config save", "Expected ok=true")
            return False
        log_pass("AI Config save", f"Config updated for provider={config['provider']}")
    except Exception as e:
        log_fail("AI Config save", str(e))
        return False
    
    return True


def test_reject_path():
    """Test 18: Reject path"""
    print("\n🚫 Test 18: Reject Path")
    
    try:
        # Start a new session
        print("\n   Starting new session for reject test...")
        prompt = "Provision a storage account named teststore123 in Central India, resource group rg-test, Standard tier, LRS replication"
        resp = session.post(f"{BASE_URL}/provisioning/sessions", json={"prompt": prompt}, timeout=10)
        if resp.status_code != 200:
            log_fail("Reject path - start", f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        session_id = data.get("id")
        log_pass("Reject path - start", f"Session {session_id[:8]}... created")
        
        # Poll until ready_for_plan
        sess = poll_session(session_id, ["ready_for_plan", "collecting", "failed"], timeout=90)
        if not sess:
            return False
        
        if sess.get("status") == "collecting":
            # Do one chat round
            resp = session.post(f"{BASE_URL}/provisioning/sessions/{session_id}/chat", 
                              json={"message": "resource group is rg-test"}, timeout=10)
            sess = poll_session(session_id, ["ready_for_plan", "failed"], timeout=90)
            if not sess:
                return False
        
        if sess.get("status") != "ready_for_plan":
            log_fail("Reject path - readiness", f"Expected ready_for_plan, got {sess.get('status')}")
            return False
        
        # Generate plan
        print("\n   Generating plan...")
        resp = session.post(f"{BASE_URL}/provisioning/sessions/{session_id}/plan", json={}, timeout=10)
        if resp.status_code != 200:
            log_fail("Reject path - plan", f"Status {resp.status_code}")
            return False
        
        # Poll for awaiting_approval
        sess = poll_session(session_id, ["awaiting_approval", "ready_for_plan", "failed"], timeout=90)
        if not sess or sess.get("status") != "awaiting_approval":
            log_fail("Reject path - plan", "Plan did not reach awaiting_approval")
            return False
        
        ticket_id = sess.get("ticket_id")
        log_pass("Reject path - plan", f"Plan ready, ticket {ticket_id[:8]}...")
        
        # Reject
        print("\n   Rejecting deployment...")
        resp = session.post(f"{BASE_URL}/provisioning/sessions/{session_id}/approve", 
                          json={"decision": "reject", "note": "Test rejection"}, timeout=10)
        if resp.status_code != 200:
            log_fail("Reject path - reject", f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        if data.get("status") != "rejected":
            log_fail("Reject path - reject", f"Expected status=rejected, got {data.get('status')}")
            return False
        
        log_pass("Reject path - reject", "Deployment rejected successfully")
        
        # Verify ticket status
        resp = session.get(f"{BASE_URL}/tickets/{ticket_id}", timeout=10)
        if resp.status_code == 200:
            ticket = resp.json()
            if ticket.get("status") == "rejected":
                log_pass("Reject path - ticket", "Ticket status=rejected")
            else:
                log_warn("Reject path - ticket", f"Ticket status={ticket.get('status')}, expected rejected")
        
        return True
        
    except Exception as e:
        log_fail("Reject path", str(e))
        return False


def test_error_cases():
    """Test 19-20: Error cases"""
    print("\n⚠️  Test 19-20: Error Cases")
    
    # Test 19: Plan without module
    print("\n   Test 19: POST /api/provisioning/sessions/{id}/plan without module_key")
    try:
        # Create session without prompt (no module selected)
        resp = session.post(f"{BASE_URL}/provisioning/sessions", json={}, timeout=10)
        if resp.status_code != 200:
            log_fail("Error case - plan no module", f"Failed to create session: {resp.status_code}")
            return False
        
        session_id = resp.json().get("id")
        
        # Try to generate plan immediately (no module_key set)
        resp = session.post(f"{BASE_URL}/provisioning/sessions/{session_id}/plan", json={}, timeout=10)
        if resp.status_code == 400:
            log_pass("Error case - plan no module", "Correctly returned 400")
        else:
            log_fail("Error case - plan no module", f"Expected 400, got {resp.status_code}")
            return False
    except Exception as e:
        log_fail("Error case - plan no module", str(e))
        return False
    
    # Test 20: Approve without plan
    print("\n   Test 20: POST /api/provisioning/sessions/{id}/approve without plan")
    try:
        # Create new session
        resp = session.post(f"{BASE_URL}/provisioning/sessions", 
                          json={"prompt": "Linux VM"}, timeout=10)
        if resp.status_code != 200:
            log_fail("Error case - approve no plan", f"Failed to create session: {resp.status_code}")
            return False
        
        session_id = resp.json().get("id")
        
        # Try to approve immediately (no plan generated)
        resp = session.post(f"{BASE_URL}/provisioning/sessions/{session_id}/approve", 
                          json={"decision": "approve"}, timeout=10)
        if resp.status_code == 400:
            log_pass("Error case - approve no plan", "Correctly returned 400")
        else:
            log_fail("Error case - approve no plan", f"Expected 400, got {resp.status_code}")
            return False
    except Exception as e:
        log_fail("Error case - approve no plan", str(e))
        return False
    
    return True


def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    total = len(results["passed"]) + len(results["failed"])
    print(f"\n✅ Passed: {len(results['passed'])}/{total}")
    print(f"❌ Failed: {len(results['failed'])}/{total}")
    print(f"⚠️  Warnings: {len(results['warnings'])}")
    
    if results["failed"]:
        print("\n❌ FAILED TESTS:")
        for fail in results["failed"]:
            print(f"   • {fail}")
    
    if results["warnings"]:
        print("\n⚠️  WARNINGS:")
        for warn in results["warnings"]:
            print(f"   • {warn}")
    
    print("\n" + "="*80)
    
    if len(results["failed"]) == 0:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("💥 SOME TESTS FAILED")
        return 1


def main():
    print("="*80)
    print("InfraGenie Provisioning Agent — Backend E2E Test Suite")
    print("Testing async refactor with polling for status transitions")
    print("="*80)
    
    # Run tests in sequence
    if not test_auth():
        print("\n❌ Auth failed, cannot continue")
        return print_summary()
    
    if not test_catalog():
        print("\n⚠️  Catalog test failed, continuing...")
    
    # Happy path (most important)
    happy_result = test_happy_path()
    if not happy_result:
        print("\n❌ Happy path failed, continuing with other tests...")
        ticket_id = None
    else:
        ticket_id = happy_result.get("ticket_id")
    
    # Tickets (if we have a ticket_id from happy path)
    if ticket_id:
        test_tickets(ticket_id)
    else:
        print("\n⚠️  Skipping ticket tests (no ticket_id from happy path)")
    
    # Other endpoints
    test_jobs()
    test_terraform_storage()
    test_ai_config()
    
    # Reject path
    test_reject_path()
    
    # Error cases
    test_error_cases()
    
    return print_summary()


if __name__ == "__main__":
    sys.exit(main())
