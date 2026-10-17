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


async def test_whatsapp_send_adds_country_code(user_client, monkeypatch):
    """Regression: a 10-digit number was sent without 91, so WhatsApp couldn't deliver."""
    from app.api import whatsapp_webhook
    sent = []

    async def fake_send(to_number, text):
        sent.append(to_number)
        return True

    monkeypatch.setattr(whatsapp_webhook, "_send_whatsapp_reply", fake_send)
    await user_client.post("/api/invoices", json={**INVOICE, "phone": "98765 11122"})
    r = await user_client.post("/api/whatsapp/send", json={"to_number": "9876511122", "message": "hi"})
    assert r.status_code == 200 and sent == ["919876511122"]


async def test_inbound_reply_matches_formatted_stored_phone(db):
    """Regression: replies weren't matched when the invoice phone was stored with spaces/dashes."""
    from app.api.whatsapp_webhook import _find_invoice_by_phone, _normalise_phone
    inv_id = (await db.get_collection("invoices").insert_one(
        {"company": "Formatted Ltd", "phone": "+91 98765-22233", "recovered": False})).inserted_id
    found = await _find_invoice_by_phone(_normalise_phone("919876522233"))
    assert found and found["_id"] == inv_id


@pytest.mark.parametrize("prompt, channel", [
    ("WhatsApp message for Ravi at Acme", "whatsapp"),
    ("Professional follow-up email to Ravi", "email"),
    ("Draft a complete formal MSME Legal Notice / Letter Before Action", "legal"),
    ("Draft a formal Legal Notice for: ... Email: owner@acme.test", "legal"),
    ("Professional email to Ravi about the pending legal notice", "email"),  # format named first wins
    ("WhatsApp message for Ravi. Notice: payment overdue", "whatsapp"),
    ("Payment reminder", None),
])
def test_ai_channel_inferred_from_request(prompt, channel):
    from app.services.ai_service import _infer_channel
    assert _infer_channel(prompt) == channel


def test_whatsapp_drafts_have_no_subject_or_meta_lines():
    """Regression: WhatsApp drafts started with 'Subject:' / 'Channel:' lines."""
    from app.services.ai_service import _build_config, _clean_for_channel
    raw = "Subject: Payment reminder\n**Channel:** WhatsApp\n\nNamaste Ravi ji,\nInvoice INV-1 is overdue.\n- Team"
    assert _clean_for_channel(raw, "whatsapp") == "Namaste Ravi ji,\nInvoice INV-1 is overdue.\n- Team"
    assert _clean_for_channel(raw, "email") == raw  # emails keep their subject line
    instruction = _build_config("Friendly", "whatsapp").system_instruction
    assert "Do NOT include a subject line" in instruction and "Subject Line" not in instruction


async def test_generate_message_strips_meta_lines_for_whatsapp(monkeypatch):
    """End to end through generate_message with a fake Gemini that ignores the instruction."""
    from types import SimpleNamespace
    import app.services.ai_service as ai
    seen = {}

    async def fake_generate_content(model, contents, config):
        seen["instruction"] = config.system_instruction
        return SimpleNamespace(text="Subject: Overdue invoice\nChannel: WhatsApp\nNamaste ji, INV-1 is overdue.")

    fake_client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate_content)))
    monkeypatch.setattr(ai, "_get_client", lambda: fake_client)

    wa = await ai.generate_message("WhatsApp message for Ravi", {"invoice_no": "INV-1"}, "Friendly")
    assert wa == "Namaste ji, INV-1 is overdue."
    assert "Do NOT include a subject line" in seen["instruction"]

    email = await ai.generate_message("Professional follow-up email to Ravi", {}, "Friendly")
    assert email.startswith("Subject: Overdue invoice")


async def test_explicit_channel_overrides_inference(user_client, monkeypatch):
    import app.api.chat as chat
    seen = []

    async def capture(prompt, invoice_data, tone, channel=None):
        seen.append(channel)
        return "ok"

    monkeypatch.setattr(chat, "ai_generate_message", capture)
    r = await user_client.post("/api/generate-message", json={"prompt": "Legal notice summary", "channel": "email"})
    assert r.status_code == 200 and seen == ["email"]
    bad = await user_client.post("/api/generate-message", json={"prompt": "x", "channel": "sms"})
    assert bad.status_code == 422


async def test_send_blocked_for_same_suffix_in_another_country(user_client, monkeypatch):
    """A +44 number ending in the same 10 digits is a different recipient."""
    from app.api import whatsapp_webhook

    async def fake_send(to_number, text):
        return True

    monkeypatch.setattr(whatsapp_webhook, "_send_whatsapp_reply", fake_send)
    await user_client.post("/api/invoices", json={**INVOICE, "phone": "+44 71234-56789"})
    other = await user_client.post("/api/whatsapp/send", json={"to_number": "+91 7123456789", "message": "hi"})
    assert other.status_code == 403
    same = await user_client.post("/api/whatsapp/send", json={"to_number": "+44 7123456789", "message": "hi"})
    assert same.status_code == 200


async def test_send_blocked_for_indian_suffix_from_abroad(user_client, monkeypatch):
    """The reverse direction: an Indian debtor's 10 digits under +44 is someone else."""
    from app.api import whatsapp_webhook

    async def fake_send(to_number, text):
        return True

    monkeypatch.setattr(whatsapp_webhook, "_send_whatsapp_reply", fake_send)
    await user_client.post("/api/invoices", json={**INVOICE, "phone": "+91 70000 12345"})
    assert (await user_client.post("/api/whatsapp/send", json={"to_number": "+44 7000012345", "message": "hi"})).status_code == 403
    assert (await user_client.post("/api/whatsapp/send", json={"to_number": "7000012345", "message": "hi"})).status_code == 200


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
