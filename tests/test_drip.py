"""Drip campaign engine and the Vercel Cron endpoint."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import app.workers.drip_scheduler as drip
from app.services.whatsapp_service import _normalize_phone, _validate_phone


@pytest.mark.parametrize("days, step", [(6, None), (7, 7), (9, 7), (10, None), (21, 21), (47, 45), (48, None)])
def test_due_step_with_grace_window(days, step):
    assert drip._due_step(days) == step


@pytest.mark.parametrize("raw, ok", [
    ("+91 98765 43210", True), ("+91-98765-43210", True), ("(022) 2345 6789", True),
    ("919876543210", True), ("abc", False), ("", False),
])
def test_formatted_phones_normalise(raw, ok):
    """Regression: '+91 98765 43210' (the UI's own placeholder) used to be rejected."""
    assert _validate_phone(_normalize_phone(raw)) is ok


def _due(days):
    return (datetime.now(timezone.utc).date() - timedelta(days=days)).strftime("%Y-%m-%d")


@pytest.fixture
async def drip_user(db):
    users = db.get_collection("users")
    uid = (await users.insert_one({
        "email": f"drip.{datetime.now().timestamp()}@recoverai-test.com",
        "drip_settings": {k: {"enabled": True, "channel": "whatsapp"} for k in ("7", "21", "35", "45")},
    })).inserted_id
    for name in ("invoices", "drip_log", "whatsapp_drafts", "cron_runs"):
        await db.get_collection(name).delete_many({})
    return uid


async def _invoice(db, uid, name, days, phone="+91 98765 00001"):
    return (await db.get_collection("invoices").insert_one({
        "owner_id": uid, "company": name, "amount": 1000, "invoice_no": name,
        "phone": phone, "recovered": False, "due_date": _due(days),
    })).inserted_id


async def _drafts(db, uid):
    return [d async for d in db.get_collection("whatsapp_drafts").find({"owner_id": uid})]


async def test_concurrent_runs_never_double_draft(db, drip_user):
    await _invoice(db, drip_user, "Day7", 7)
    await _invoice(db, drip_user, "Day8-missed-midnight", 8)
    await _invoice(db, drip_user, "Day12-between-steps", 12)
    await _invoice(db, drip_user, "NoPhone", 7, phone="")

    await asyncio.gather(drip.run_daily_drips(), drip.run_daily_drips())  # two workers at midnight
    drafts = await _drafts(db, drip_user)
    assert sorted(d["drip_day"] for d in drafts) == [7, 7]

    await drip.run_daily_drips()
    assert len(await _drafts(db, drip_user)) == 2


async def test_prompt_includes_due_date(db, drip_user, monkeypatch):
    seen = []

    async def capture(prompt, invoice_data, tone):
        seen.append((prompt, invoice_data, tone))
        return "msg"

    monkeypatch.setattr(drip, "generate_message", capture)
    await _invoice(db, drip_user, "Dated", 21)
    await drip.run_daily_drips()
    prompt, ctx, tone = seen[0]
    assert ctx["due_date"] == _due(21) and _due(21) in prompt and tone == "Firm Warning"


async def test_failed_generation_releases_claim(db, drip_user, monkeypatch):
    async def boom(*_a, **_k):
        raise RuntimeError("AI down")

    monkeypatch.setattr(drip, "generate_message", boom)
    inv = await _invoice(db, drip_user, "Retry", 7)
    await drip.run_daily_drips()
    assert await db.get_collection("drip_log").find_one({"invoice_id": inv}) is None


async def test_stale_claim_reclaimed_fresh_claim_respected(db, drip_user):
    log = db.get_collection("drip_log")
    stale = await _invoice(db, drip_user, "Stale", 21)
    fresh = await _invoice(db, drip_user, "Fresh", 21)
    now = datetime.now(timezone.utc)
    await log.insert_one({"invoice_id": stale, "days_overdue": 21, "status": "processing", "claimed_at": now - timedelta(hours=2)})
    await log.insert_one({"invoice_id": fresh, "days_overdue": 21, "status": "processing", "claimed_at": now})

    await drip.run_daily_drips()
    drafted = {d["invoice_id"] for d in await _drafts(db, drip_user)}
    assert stale in drafted and fresh not in drafted


async def test_time_budget_stops_new_work(db, drip_user):
    await _invoice(db, drip_user, "Later", 35)
    result = await drip.run_daily_drips(time_budget_seconds=1e-9)
    assert result["stopped_early"] and result["drafted"] == 0


async def test_cron_endpoint_runs_once_per_day(db, drip_user, new_client):
    await _invoice(db, drip_user, "Cron", 7)
    c = new_client()
    first = (await c.get("/api/cron/drips")).json()
    second = (await c.get("/api/cron/drips")).json()
    assert first["status"] == "ok" and first["drafted"] == 1
    assert second == {"status": "skipped", "reason": "already ran today"}


async def test_cron_secret_enforced_when_set(db, new_client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "cron_secret", "s3cret-value")
    c = new_client()
    assert (await c.get("/api/cron/drips")).status_code == 401
    assert (await c.get("/api/cron/drips", headers={"Authorization": "Bearer wrong"})).status_code == 401


async def test_drip_settings_api_rejects_injection(user_client):
    assert "7" in (await user_client.get("/api/drip-settings")).json()
    ok = await user_client.put("/api/drip-settings", json={"settings": {"7": {"enabled": False, "channel": "whatsapp"}}})
    assert ok.status_code == 200
    bad = await user_client.put("/api/drip-settings", json={"settings": {"$where": {"enabled": True}}})
    assert bad.status_code == 422
