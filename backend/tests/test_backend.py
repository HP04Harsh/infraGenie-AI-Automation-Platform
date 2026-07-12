"""InfraGenie backend tests — auth, onboarding, metrics, activity, notifications."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://infra-premium-portal.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@chatops.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    assert "ig_token" in s.cookies, "httpOnly cookie ig_token should be set"
    return s


@pytest.fixture(scope="module")
def new_user_session():
    s = requests.Session()
    email = f"qa+{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "Test1234!", "name": "QA Test"})
    assert r.status_code == 200, r.text
    s.email = email
    return s


# --- Auth ---
class TestAuth:
    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_login_success_sets_cookie(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "admin"
        assert "ig_token" in s.cookies

    def test_login_invalid_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_register_duplicate_email(self):
        r = requests.post(f"{API}/auth/register", json={"email": ADMIN_EMAIL, "password": "anything123", "name": "X"})
        assert r.status_code == 409

    def test_register_new_user(self, new_user_session):
        r = new_user_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        u = r.json()
        assert u["email"] == new_user_session.email
        assert u["onboarding_complete"] is False

    def test_me_without_cookie_returns_401(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_metrics_without_cookie_returns_401(self):
        r = requests.get(f"{API}/metrics")
        assert r.status_code == 401

    def test_logout_clears_cookie(self, admin_session):
        # logout, then /me must return 401 using a fresh session that does not carry the cleared cookie
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert s.get(f"{API}/auth/me").status_code == 200
        s.post(f"{API}/auth/logout")
        # After logout, cookie should be cleared in session
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 401


# --- Onboarding ---
class TestOnboarding:
    def test_status_for_admin(self, admin_session):
        r = admin_session.get(f"{API}/onboarding/status")
        assert r.status_code == 200
        # admin was reset to onboarding_complete=False
        assert r.json()["onboarding_complete"] is False

    def test_submit_with_fake_creds_does_not_crash(self, new_user_session):
        payload = {
            "company": {"company_name": "QA Co", "industry": "tech", "company_size": "11-50", "website": "https://qa.test"},
            "azure_tenant": {
                "tenant_id": "00000000-0000-0000-0000-000000000001",
                "client_id": "00000000-0000-0000-0000-000000000002",
                "client_secret": "fakesecret",
                "subscription_id": "00000000-0000-0000-0000-000000000003",
            },
            "azure_ai": {
                "project_endpoint": "https://fake-ai.openai.azure.com",
                "api_key": "fake-key-1234",
                "agent_name": "OpsBot",
                "model_name": "gpt-4o",
            },
        }
        r = new_user_session.post(f"{API}/onboarding/submit", json=payload, timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        phases = data["metrics"]["phases"]
        assert "auth" in phases
        # ai should validate ok (config-only)
        assert phases.get("ai", {}).get("ok") is True
        assert "stats" in data
        for k in ["resources", "vms", "resource_groups", "security_score"]:
            assert k in data["stats"]

    def test_status_after_submit(self, new_user_session):
        r = new_user_session.get(f"{API}/onboarding/status")
        assert r.status_code == 200
        assert r.json()["onboarding_complete"] is True


# --- Metrics / activity / notifications ---
class TestDashboardData:
    def test_metrics_returns_5_cards(self, new_user_session):
        r = new_user_session.get(f"{API}/metrics")
        assert r.status_code == 200
        data = r.json()
        assert len(data["cards"]) == 5
        keys = [c["key"] for c in data["cards"]]
        assert keys == ["resources", "healthy", "incidents", "cost", "compliance"]
        # With fake creds → all should be 0 with helpful sub text
        for c in data["cards"]:
            assert "value" in c and "sub" in c

    def test_activity(self, new_user_session):
        r = new_user_session.get(f"{API}/activity")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        assert "title" in items[0]

    def test_notifications(self, new_user_session):
        r = new_user_session.get(f"{API}/notifications")
        assert r.status_code == 200
        data = r.json()
        assert data["unread"] >= 0
        assert isinstance(data["items"], list)
