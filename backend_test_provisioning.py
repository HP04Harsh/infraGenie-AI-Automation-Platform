#!/usr/bin/env python3
"""
InfraGenie Provisioning API Test Suite
Tests all provisioning endpoints, tickets, activity, and settings.
"""
import requests
import time
import sys
import os

# Backend URL from environment
BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://dep-resolver-4.preview.emergentagent.com")
BASE_URL = f"{BACKEND_URL}/api"

# Test credentials
TEST_EMAIL = "guest@infragenie.io"
TEST_PASSWORD = "Guest@321"

# Global session for cookies
session = requests.Session()

def log(msg, level="INFO"):
    """Print formatted log message"""
    print(f"[{level}] {msg}")

def test_login():
    """Test 1: Login to get session cookie"""
    log("Test 1: POST /api/auth/login")
    resp = session.post(f"{BASE_URL}/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if resp.status_code != 200:
        log(f"❌ Login failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    if "user" not in data:
        log(f"❌ Login response missing 'user': {data}", "ERROR")
        return False
    
    log(f"✅ Login successful: {data['user']['email']}")
    return True

def test_catalog():
    """Test 2: GET /api/provisioning/catalog - must return 15 modules"""
    log("Test 2: GET /api/provisioning/catalog")
    resp = session.get(f"{BASE_URL}/provisioning/catalog")
    
    if resp.status_code != 200:
        log(f"❌ Catalog failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    if "catalog" not in data:
        log(f"❌ Response missing 'catalog' key: {data}", "ERROR")
        return False
    
    catalog = data["catalog"]
    if not isinstance(catalog, list):
        log(f"❌ Catalog is not a list: {type(catalog)}", "ERROR")
        return False
    
    if len(catalog) != 15:
        log(f"❌ Expected 15 modules, got {len(catalog)}", "ERROR")
        return False
    
    # Verify each entry has required fields
    for idx, entry in enumerate(catalog):
        required_fields = ["key", "label", "category", "required_vars"]
        for field in required_fields:
            if field not in entry:
                log(f"❌ Module {idx} missing field '{field}': {entry}", "ERROR")
                return False
        
        # Verify required_vars is a list
        if not isinstance(entry["required_vars"], list):
            log(f"❌ Module {idx} required_vars is not a list", "ERROR")
            return False
        
        # Verify each var has name, label, type
        for var in entry["required_vars"]:
            if not all(k in var for k in ["name", "label", "type"]):
                log(f"❌ Module {idx} var missing required fields: {var}", "ERROR")
                return False
    
    log(f"✅ Catalog returned 15 modules with correct structure")
    return True

def test_create_session():
    """Test 3: POST /api/provisioning/sessions - create session with prompt"""
    log("Test 3: POST /api/provisioning/sessions")
    resp = session.post(f"{BASE_URL}/provisioning/sessions", json={
        "prompt": "Provision a Linux VM in Central India"
    })
    
    if resp.status_code != 200:
        log(f"❌ Create session failed: {resp.status_code} - {resp.text}", "ERROR")
        return None
    
    data = resp.json()
    
    # Verify required fields
    required_fields = ["id", "module_key", "status", "conversation", "workspace_id"]
    for field in required_fields:
        if field not in data:
            log(f"❌ Session response missing '{field}': {data}", "ERROR")
            return None
    
    # Verify module_key is virtual-machine-linux (heuristic classification)
    if data["module_key"] != "virtual-machine-linux":
        log(f"❌ Expected module_key 'virtual-machine-linux', got '{data['module_key']}'", "ERROR")
        return None
    
    # Verify status is collecting
    if data["status"] != "collecting":
        log(f"❌ Expected status 'collecting', got '{data['status']}'", "ERROR")
        return None
    
    # Verify conversation has at least 2 turns
    conversation = data.get("conversation", [])
    if len(conversation) < 2:
        log(f"❌ Expected at least 2 conversation turns, got {len(conversation)}", "ERROR")
        return None
    
    # Verify first turn is user, second is assistant
    if conversation[0].get("role") != "user":
        log(f"❌ First conversation turn should be 'user', got '{conversation[0].get('role')}'", "ERROR")
        return None
    
    if conversation[1].get("role") != "assistant":
        log(f"❌ Second conversation turn should be 'assistant', got '{conversation[1].get('role')}'", "ERROR")
        return None
    
    # Verify workspace_id is present
    if not data.get("workspace_id"):
        log(f"❌ workspace_id is missing or empty", "ERROR")
        return None
    
    log(f"✅ Session created: id={data['id']}, module_key={data['module_key']}, status={data['status']}, conversation_turns={len(conversation)}")
    return data["id"]

def test_get_session(session_id):
    """Test 4: GET /api/provisioning/sessions/{sid}"""
    log(f"Test 4: GET /api/provisioning/sessions/{session_id}")
    
    # Test with valid session ID
    resp = session.get(f"{BASE_URL}/provisioning/sessions/{session_id}")
    if resp.status_code != 200:
        log(f"❌ Get session failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    if data.get("id") != session_id:
        log(f"❌ Session ID mismatch: expected {session_id}, got {data.get('id')}", "ERROR")
        return False
    
    log(f"✅ Get session successful: {session_id}")
    
    # Test with random UUID (should return 404)
    import uuid
    random_id = str(uuid.uuid4())
    resp = session.get(f"{BASE_URL}/provisioning/sessions/{random_id}")
    if resp.status_code != 404:
        log(f"❌ Expected 404 for random UUID, got {resp.status_code}", "ERROR")
        return False
    
    log(f"✅ Get session with random UUID correctly returned 404")
    return True

def test_chat_session(session_id):
    """Test 5: POST /api/provisioning/sessions/{sid}/chat"""
    log(f"Test 5: POST /api/provisioning/sessions/{session_id}/chat")
    
    resp = session.post(f"{BASE_URL}/provisioning/sessions/{session_id}/chat", json={
        "message": "Standard_B2s"
    })
    
    if resp.status_code != 200:
        log(f"❌ Chat session failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    
    # Verify conversation has grown
    conversation = data.get("conversation", [])
    if len(conversation) < 3:  # Initial 2 + at least 1 new assistant turn
        log(f"❌ Expected at least 3 conversation turns after chat, got {len(conversation)}", "ERROR")
        return False
    
    # Verify last turn is assistant
    if conversation[-1].get("role") != "assistant":
        log(f"❌ Last conversation turn should be 'assistant', got '{conversation[-1].get('role')}'", "ERROR")
        return False
    
    log(f"✅ Chat session successful: conversation now has {len(conversation)} turns")
    return True

def test_generate_plan(session_id):
    """Test 6: POST /api/provisioning/sessions/{sid}/plan"""
    log(f"Test 6: POST /api/provisioning/sessions/{session_id}/plan")
    
    resp = session.post(f"{BASE_URL}/provisioning/sessions/{session_id}/plan")
    
    if resp.status_code != 200:
        log(f"❌ Generate plan failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    
    # Verify plan exists
    plan = data.get("plan")
    if not plan:
        log(f"❌ Plan is missing from response", "ERROR")
        return False
    
    # Verify plan structure
    required_plan_fields = ["summary", "actions", "cost"]
    for field in required_plan_fields:
        if field not in plan:
            log(f"❌ Plan missing '{field}': {plan}", "ERROR")
            return False
    
    # Verify cost structure
    cost = plan["cost"]
    if "monthly_total" not in cost:
        log(f"❌ Cost missing 'monthly_total': {cost}", "ERROR")
        return False
    
    if "currency" not in cost:
        log(f"❌ Cost missing 'currency': {cost}", "ERROR")
        return False
    
    if not isinstance(cost["monthly_total"], (int, float)):
        log(f"❌ monthly_total should be a number, got {type(cost['monthly_total'])}", "ERROR")
        return False
    
    if not isinstance(cost["currency"], str):
        log(f"❌ currency should be a string, got {type(cost['currency'])}", "ERROR")
        return False
    
    # Verify status is awaiting_approval
    if data.get("status") != "awaiting_approval":
        log(f"❌ Expected status 'awaiting_approval', got '{data.get('status')}'", "ERROR")
        return False
    
    # Verify runtime folder was created
    deployment_id = plan.get("deployment_id")
    workspace_id = data.get("workspace_id")
    if deployment_id and workspace_id:
        runtime_path = f"/app/terraform/runtime/{workspace_id}/{deployment_id}"
        if not os.path.exists(runtime_path):
            log(f"⚠️  Runtime folder not found at {runtime_path} (may be expected in demo mode)", "WARN")
        else:
            log(f"✅ Runtime folder created at {runtime_path}")
    
    log(f"✅ Plan generated: summary='{plan['summary']}', cost={cost['monthly_total']} {cost['currency']}, status={data['status']}")
    return True

def test_approve_session(session_id):
    """Test 7: POST /api/provisioning/sessions/{sid}/approve"""
    log(f"Test 7: POST /api/provisioning/sessions/{session_id}/approve")
    
    resp = session.post(f"{BASE_URL}/provisioning/sessions/{session_id}/approve", json={
        "decision": "approve",
        "note": "Test approval"
    })
    
    if resp.status_code != 200:
        log(f"❌ Approve session failed: {resp.status_code} - {resp.text}", "ERROR")
        return None
    
    data = resp.json()
    
    # Verify status is deploying
    if data.get("status") != "deploying":
        log(f"❌ Expected status 'deploying', got '{data.get('status')}'", "ERROR")
        return None
    
    # Verify ticket_id is present
    ticket_id = data.get("ticket_id")
    if not ticket_id:
        log(f"❌ ticket_id is missing from response", "ERROR")
        return None
    
    log(f"✅ Session approved: status={data['status']}, ticket_id={ticket_id}")
    return ticket_id

def test_ticket_completion(ticket_id, max_wait=15):
    """Test 8: Poll GET /api/tickets/{ticket_id} until status is 'completed'"""
    log(f"Test 8: Polling ticket {ticket_id} for completion (max {max_wait}s)")
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        resp = session.get(f"{BASE_URL}/tickets/{ticket_id}")
        
        if resp.status_code != 200:
            log(f"❌ Get ticket failed: {resp.status_code} - {resp.text}", "ERROR")
            return False
        
        data = resp.json()
        status = data.get("status")
        
        log(f"   Ticket status: {status} (elapsed: {int(time.time() - start_time)}s)")
        
        if status == "completed":
            log(f"✅ Ticket completed in {int(time.time() - start_time)}s")
            return True
        
        time.sleep(2)
    
    log(f"❌ Ticket did not complete within {max_wait}s", "ERROR")
    return False

def test_list_tickets():
    """Test 9: GET /api/tickets with various filters"""
    log("Test 9: GET /api/tickets")
    
    # Test basic list
    resp = session.get(f"{BASE_URL}/tickets")
    if resp.status_code != 200:
        log(f"❌ List tickets failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    if "items" not in data or "total" not in data:
        log(f"❌ Response missing 'items' or 'total': {data}", "ERROR")
        return False
    
    total_count = len(data["items"])
    log(f"✅ List tickets successful: {total_count} tickets")
    
    # Test status filter: deploying
    resp = session.get(f"{BASE_URL}/tickets?status=deploying")
    if resp.status_code != 200:
        log(f"❌ List tickets with status=deploying failed: {resp.status_code}", "ERROR")
        return False
    
    data = resp.json()
    deploying_count = len(data["items"])
    # Verify all items have status=deploying
    for item in data["items"]:
        if item.get("status") != "deploying":
            log(f"❌ Filter status=deploying returned item with status={item.get('status')}", "ERROR")
            return False
    
    log(f"✅ List tickets with status=deploying: {deploying_count} tickets")
    
    # Test status filter: completed
    resp = session.get(f"{BASE_URL}/tickets?status=completed")
    if resp.status_code != 200:
        log(f"❌ List tickets with status=completed failed: {resp.status_code}", "ERROR")
        return False
    
    data = resp.json()
    completed_count = len(data["items"])
    # Verify all items have status=completed
    for item in data["items"]:
        if item.get("status") != "completed":
            log(f"❌ Filter status=completed returned item with status={item.get('status')}", "ERROR")
            return False
    
    log(f"✅ List tickets with status=completed: {completed_count} tickets")
    
    # Test search filter: q=INC
    resp = session.get(f"{BASE_URL}/tickets?q=INC")
    if resp.status_code != 200:
        log(f"❌ List tickets with q=INC failed: {resp.status_code}", "ERROR")
        return False
    
    data = resp.json()
    search_count = len(data["items"])
    # Verify all items have ticket_number containing INC
    for item in data["items"]:
        ticket_number = item.get("ticket_number", "")
        if "INC" not in ticket_number:
            log(f"❌ Search q=INC returned item without INC in ticket_number: {ticket_number}", "ERROR")
            return False
    
    log(f"✅ List tickets with q=INC: {search_count} tickets")
    return True

def test_get_ticket(ticket_id):
    """Test 10: GET /api/tickets/{ticket_id}"""
    log(f"Test 10: GET /api/tickets/{ticket_id}")
    
    resp = session.get(f"{BASE_URL}/tickets/{ticket_id}")
    if resp.status_code != 200:
        log(f"❌ Get ticket failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    
    # Verify required fields
    required_fields = ["id", "ticket_number", "audit", "logs", "outputs", "plan", "apply_result", "comments"]
    for field in required_fields:
        if field not in data:
            log(f"❌ Ticket response missing '{field}': {list(data.keys())}", "ERROR")
            return False
    
    log(f"✅ Get ticket successful: {data['ticket_number']}, status={data.get('status')}")
    return True

def test_comment_ticket(ticket_id):
    """Test 11: POST /api/tickets/{ticket_id}/comment"""
    log(f"Test 11: POST /api/tickets/{ticket_id}/comment")
    
    resp = session.post(f"{BASE_URL}/tickets/{ticket_id}/comment", json={
        "text": "LGTM"
    })
    
    if resp.status_code != 200:
        log(f"❌ Comment ticket failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    
    # Verify comments array exists and has at least one comment
    comments = data.get("comments", [])
    if not comments:
        log(f"❌ Comments array is empty after adding comment", "ERROR")
        return False
    
    # Verify last comment has our text
    last_comment = comments[-1]
    if last_comment.get("text") != "LGTM":
        log(f"❌ Last comment text mismatch: expected 'LGTM', got '{last_comment.get('text')}'", "ERROR")
        return False
    
    log(f"✅ Comment added successfully: {len(comments)} total comments")
    return True

def test_activity_important():
    """Test 12: GET /api/activity?important=true"""
    log("Test 12: GET /api/activity?important=true")
    
    resp = session.get(f"{BASE_URL}/activity?important=true")
    if resp.status_code != 200:
        log(f"❌ Get activity failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    if "items" not in data:
        log(f"❌ Response missing 'items': {data}", "ERROR")
        return False
    
    items = data["items"]
    
    # Verify NONE of the items has type == "auth.login" or "chat.message"
    excluded_types = ["auth.login", "chat.message"]
    for item in items:
        event_type = item.get("type", "")
        if event_type in excluded_types:
            log(f"❌ Important filter returned excluded type '{event_type}'", "ERROR")
            return False
    
    # Verify all items are important types
    important_prefixes = ["onboarding.", "provisioning.", "ticket.", "resource.", "integration.", "settings.update", "auth.register"]
    for item in items:
        event_type = item.get("type", "")
        is_important = any(event_type.startswith(prefix) or event_type == prefix for prefix in important_prefixes)
        if not is_important:
            log(f"❌ Important filter returned non-important type '{event_type}'", "ERROR")
            return False
    
    log(f"✅ Activity important filter working: {len(items)} important events, no auth.login or chat.message")
    return True

def test_settings_terraform_storage():
    """Test 13: Settings endpoints - terraform-storage"""
    log("Test 13: Settings - terraform-storage")
    
    # GET initial state
    resp = session.get(f"{BASE_URL}/settings/terraform-storage")
    if resp.status_code != 200:
        log(f"❌ Get terraform-storage failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    if "config" not in data or "configured" not in data:
        log(f"❌ Response missing 'config' or 'configured': {data}", "ERROR")
        return False
    
    initial_configured = data["configured"]
    log(f"   Initial state: configured={initial_configured}")
    
    # POST configuration
    resp = session.post(f"{BASE_URL}/settings/terraform-storage", json={
        "storage_account": "stx",
        "container": "tfstate",
        "resource_group": "rg",
        "backend_prefix": "ig",
        "access_key": "secret123"
    })
    
    if resp.status_code != 200:
        log(f"❌ Post terraform-storage failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    if not data.get("ok") or not data.get("configured"):
        log(f"❌ Post response should have ok=true and configured=true: {data}", "ERROR")
        return False
    
    log(f"✅ Terraform storage configured")
    
    # GET again to verify configured=true and access_key is redacted
    resp = session.get(f"{BASE_URL}/settings/terraform-storage")
    if resp.status_code != 200:
        log(f"❌ Get terraform-storage after POST failed: {resp.status_code}", "ERROR")
        return False
    
    data = resp.json()
    if not data.get("configured"):
        log(f"❌ configured should be true after POST: {data}", "ERROR")
        return False
    
    config = data.get("config", {})
    if "access_key" in config:
        log(f"❌ access_key should be redacted in GET response: {config}", "ERROR")
        return False
    
    log(f"✅ Terraform storage GET after POST: configured=true, access_key redacted")
    return True

def test_settings_ai_config():
    """Test 14: Settings endpoints - ai-config"""
    log("Test 14: Settings - ai-config")
    
    # GET initial state
    resp = session.get(f"{BASE_URL}/settings/ai-config")
    if resp.status_code != 200:
        log(f"❌ Get ai-config failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    if "config" not in data or "configured" not in data:
        log(f"❌ Response missing 'config' or 'configured': {data}", "ERROR")
        return False
    
    log(f"   Initial state: configured={data['configured']}")
    
    # POST configuration
    resp = session.post(f"{BASE_URL}/settings/ai-config", json={
        "provider": "azure_openai",
        "endpoint": "https://test.openai.azure.com",
        "deployment": "gpt-4",
        "agent_name": "TestBot",
        "api_key": "secret_api_key"
    })
    
    if resp.status_code != 200:
        log(f"❌ Post ai-config failed: {resp.status_code} - {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    if not data.get("ok") or not data.get("configured"):
        log(f"❌ Post response should have ok=true and configured=true: {data}", "ERROR")
        return False
    
    log(f"✅ AI config saved")
    
    # GET again to verify api_key is redacted
    resp = session.get(f"{BASE_URL}/settings/ai-config")
    if resp.status_code != 200:
        log(f"❌ Get ai-config after POST failed: {resp.status_code}", "ERROR")
        return False
    
    data = resp.json()
    config = data.get("config", {})
    if "api_key" in config:
        log(f"❌ api_key should be redacted in GET response: {config}", "ERROR")
        return False
    
    log(f"✅ AI config GET after POST: api_key redacted")
    return True

def main():
    """Run all tests"""
    log("=" * 60)
    log("InfraGenie Provisioning API Test Suite")
    log("=" * 60)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Login
    if not test_login():
        log("FATAL: Login failed, cannot continue", "ERROR")
        sys.exit(1)
    tests_passed += 1
    
    # Test 2: Catalog
    if test_catalog():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 3: Create session
    session_id = test_create_session()
    if session_id:
        tests_passed += 1
    else:
        tests_failed += 1
        log("FATAL: Cannot continue without session_id", "ERROR")
        sys.exit(1)
    
    # Test 4: Get session
    if test_get_session(session_id):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 5: Chat session
    if test_chat_session(session_id):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 6: Generate plan
    if test_generate_plan(session_id):
        tests_passed += 1
    else:
        tests_failed += 1
        log("FATAL: Cannot continue without plan", "ERROR")
        sys.exit(1)
    
    # Test 7: Approve session
    ticket_id = test_approve_session(session_id)
    if ticket_id:
        tests_passed += 1
    else:
        tests_failed += 1
        log("FATAL: Cannot continue without ticket_id", "ERROR")
        sys.exit(1)
    
    # Test 8: Wait for ticket completion
    if test_ticket_completion(ticket_id):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 9: List tickets with filters
    if test_list_tickets():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 10: Get ticket details
    if test_get_ticket(ticket_id):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 11: Comment on ticket
    if test_comment_ticket(ticket_id):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 12: Activity important filter
    if test_activity_important():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 13: Terraform storage settings
    if test_settings_terraform_storage():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 14: AI config settings
    if test_settings_ai_config():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Summary
    log("=" * 60)
    log(f"RESULTS: {tests_passed} passed, {tests_failed} failed")
    log("=" * 60)
    
    if tests_failed > 0:
        sys.exit(1)
    else:
        log("✅ ALL TESTS PASSED", "SUCCESS")
        sys.exit(0)

if __name__ == "__main__":
    main()
