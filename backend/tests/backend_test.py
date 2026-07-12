"""Backend tests for InfraLift dashboard endpoints."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://infra-premium-portal.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---- Health ----
class TestHealth:
    def test_root(self, client):
        r = client.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        d = r.json()
        assert d.get("status") == "ok"


# ---- Overview ----
class TestOverview:
    def test_overview_shape(self, client):
        r = client.get(f"{BASE_URL}/api/tenant/overview")
        assert r.status_code == 200
        d = r.json()
        assert "user" in d and d["user"]["name"] == "Harsh Patel"
        assert d["user"]["initials"] == "HP"
        assert d["user"]["role"] == "Admin"
        assert d.get("greeting") in {"Working late", "Good morning", "Good afternoon", "Good evening"}
        assert isinstance(d.get("cards"), list)
        assert len(d["cards"]) == 5
        keys = {c["key"] for c in d["cards"]}
        assert keys == {"resources", "healthy", "incidents", "cost", "compliance"}
        for c in d["cards"]:
            for k in ("key", "label", "value", "raw", "sub", "sub_tone", "icon", "accent"):
                assert k in c, f"missing {k} in card {c}"

    def test_overview_value_formats(self, client):
        r = client.get(f"{BASE_URL}/api/tenant/overview")
        cards = {c["key"]: c for c in r.json()["cards"]}
        assert "," in cards["resources"]["value"]  # e.g. "1,284"
        assert cards["cost"]["value"].startswith("$") and cards["cost"]["value"].endswith("K")
        assert cards["compliance"]["value"].endswith("%")

    def test_overview_jitters(self, client):
        # Two consecutive calls should usually differ in at least one card value (jitter)
        r1 = client.get(f"{BASE_URL}/api/tenant/overview").json()["cards"]
        r2 = client.get(f"{BASE_URL}/api/tenant/overview").json()["cards"]
        diffs = [a["raw"] != b["raw"] for a, b in zip(r1, r2)]
        # Tolerate occasional equality but require at least one diff most of time
        assert any(diffs), "Expected jitter across requests but values were identical"


# ---- Activity ----
class TestActivity:
    def test_activity_shape(self, client):
        r = client.get(f"{BASE_URL}/api/tenant/activity")
        assert r.status_code == 200
        d = r.json()
        items = d.get("items")
        assert isinstance(items, list) and len(items) >= 5
        for it in items:
            for k in ("id", "title", "detail", "time_ago", "status", "status_tone", "icon", "accent"):
                assert k in it, f"missing {k} in {it}"
        ids = [it["id"] for it in items]
        assert ids[0] == "act_1"


# ---- Smart Assist ----
class TestAssist:
    def test_chat_returns_reply(self, client):
        r = client.post(f"{BASE_URL}/api/assist/chat", json={"message": "Provision a VM in Azure"})
        assert r.status_code == 200
        d = r.json()
        assert d["mocked"] is True
        assert isinstance(d["reply"], str) and len(d["reply"]) > 10
        assert d["thread_id"].startswith("thr_")

    def test_chat_empty_message(self, client):
        r = client.post(f"{BASE_URL}/api/assist/chat", json={"message": "  "})
        assert r.status_code == 400

    def test_chat_context_aware(self, client):
        r = client.post(f"{BASE_URL}/api/assist/chat", json={"message": "Show cost optimization opportunities"})
        d = r.json()
        assert "$3,840" in d["reply"] or "savings" in d["reply"].lower()

    def test_chat_thread_reuse(self, client):
        r1 = client.post(f"{BASE_URL}/api/assist/chat", json={"message": "hello"})
        tid = r1.json()["thread_id"]
        r2 = client.post(f"{BASE_URL}/api/assist/chat", json={"message": "again", "thread_id": tid})
        assert r2.json()["thread_id"] == tid


# ---- Onboarding ----
class TestOnboarding:
    def test_connect_tenant(self, client):
        payload = {"tenant_name": "TEST_acme", "cloud": "azure", "subscription_id": "sub-1", "region": "eastus"}
        r = client.post(f"{BASE_URL}/api/onboarding/connect", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "saved"
        assert "tenant_id" in d
