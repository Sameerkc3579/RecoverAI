"""AI endpoints (mocked Gemini), enrichment SSRF guard, WhatsApp, admin and frontend routes."""
import pytest

from conftest import INVOICE, register_and_login


async def test_ai_generate_and_bulk(user_client):
    r = await user_client.post("/api/generate-message", json={"prompt": "Reminder", "invoice_data": INVOICE, "tone": "Friendly"})
    assert r.status_code == 200 and "Acme Debtor Ltd" in r.text
    bulk = await user_client.post("/api/bulk-generate", json=[{"prompt": "R", "invoice_data": INVOICE, "tone": "Final Notice"}] * 2)
    assert bulk.status_code == 200 and all(item["message"] for item in bulk.json())
    bad_tone = await user_client.post("/api/generate-message", json={"prompt": "R", "tone": "Rude"})
    assert bad_tone.status_code == 422


async def test_debtor_reply_classified(user_client):
    inv_id = (await user_client.post("/api/invoices", json=INVOICE)).json()["id"]
    r = await user_client.post("/api/debtor-reply", json={"invoice_id": inv_id, "message": "agle hafte payment kar dunga"})
    assert r.status_code == 200 and r.json()["intent"] == "promise_to_pay"


@pytest.mark.parametrize("url", ["http://127.0.0.1:8000/health", "http://localhost/", "http://169.254.169.254/latest/meta-data"])
async def test_enrich_blocks_internal_addresses(user_client, url):
    assert (await user_client.post("/api/enrich", json={"url": url})).status_code in (400, 403, 422)


async def test_whatsapp_router_is_mounted(user_client):
    """Regression: these Debtor Inbox endpoints all returned 404."""
    status = await user_client.get("/api/whatsapp/status")
    assert status.status_code == 200 and "fully_configured" in status.json()
    assert (await user_client.get("/api/whatsapp/messages?limit=5")).status_code == 200


async def test_whatsapp_send_only_to_own_debtors(user_client):
    r = await user_client.post("/api/whatsapp/send", json={"to_number": "+910000000001", "message": "hi"})
    assert r.status_code == 403


async def test_whatsapp_token_falls_back_to_legacy_name(monkeypatch):
    from app.api import whatsapp_webhook
    from app.core.config import settings
    monkeypatch.setattr(settings, "whatsapp_access_token", "")
    monkeypatch.setattr(settings, "whatsapp_api_token", "legacy-token")
    assert whatsapp_webhook._wa_access_token() == "legacy-token"


async def test_meta_webhook_rejects_bad_token_and_signature(new_client):
    c = new_client()
    verify = await c.get("/api/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"})
    assert verify.status_code == 403
    ok = await c.get("/api/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "test-verify-token", "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    post = await c.post("/api/webhooks/whatsapp", content=b'{"entry":[]}', headers={"X-Hub-Signature-256": "sha256=bad"})
    assert post.status_code == 200 and post.json()["status"] == "ignored"


async def test_admin_endpoints_require_admin(user_client):
    assert (await user_client.get("/api/admin/dashboard-stats")).status_code == 403


async def test_admin_flows(admin_client, new_client, unique_email):
    target = new_client()
    email = unique_email("managed")
    await register_and_login(target, email)

    assert (await admin_client.get("/api/admin/dashboard-stats")).status_code == 200
    users = (await admin_client.get("/api/admin/users")).json()
    users = users.get("users", users) if isinstance(users, dict) else users
    uid = next(u.get("id") or u.get("_id") for u in users if u["email"] == email)

    assert (await admin_client.put(f"/api/admin/users/{uid}", json={"city": "Delhi"})).status_code == 200
    assert (await admin_client.post(f"/api/admin/users/{uid}/change-plan", json={"plan": "Professional"})).status_code == 200
    assert (await admin_client.get("/api/admin/search", params={"q": "managed"})).status_code == 200
    assert (await admin_client.get("/api/admin/export/users")).status_code == 200
    assert (await admin_client.delete(f"/api/admin/users/{uid}")).status_code in (200, 204)


async def test_admin_activity_handles_missing_dates(admin_client, user_client):
    """Regression: invoices without issueDate made the activity feed 500."""
    no_date = {k: v for k, v in INVOICE.items() if k != "issueDate"}
    await user_client.post("/api/invoices", json={**no_date, "status": "recovered", "recovered": True})
    await user_client.post("/api/invoices", json={**INVOICE, "status": "recovered", "recovered": True})
    r = await admin_client.get("/api/admin/activity")
    assert r.status_code == 200 and any(a["type"] == "invoice_recovered" for a in r.json())


async def test_diagnostics_hidden(admin_client, new_client):
    assert (await new_client().get("/api/startup-check")).status_code == 401
    assert (await admin_client.get("/api/fs-debug")).status_code == 404  # DEBUG is off


@pytest.mark.parametrize("path", ["/", "/login", "/dashboard", "/invoices", "/admin", "/portal", "/health"])
async def test_pages_served(new_client, path):
    assert (await new_client().get(path)).status_code == 200
