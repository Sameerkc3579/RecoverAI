"""Drip campaign engine and the Vercel Cron endpoint."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import app.workers.drip_scheduler as drip
from app.services.whatsapp_service import _normalize_phone, _validate_phone


@pytest.mark.parametrize("days, step", [(6, None), (7, 7), (9, 7), (10, None), (21, 21), (47, 45), (48, None)])
def test_due_step_with_grace_window(days, step):
    assert drip._due_step(days) == step


@pytest.mark.parametrize("raw, expected", [
    ("+91 98765 43210", "919876543210"), ("+91-98765-43210", "919876543210"),
    ("9876543210", "919876543210"),       # bare 10 digits: WhatsApp needs the 91
    ("09876543210", "919876543210"),      # trunk-prefixed
    ("919876543210", "919876543210"), ("+1 (415) 555-0100", "14155550100"),
    ("abc", None), ("", None),
])
def test_phones_normalise_to_international_format(raw, expected):
    """Regressions: formatted numbers were rejected; 10-digit numbers lacked the country code."""
    normalised = _normalize_phone(raw)
    assert _validate_phone(normalised) is (expected is not None)
    if expected:
        assert normalised == expected


def _due(days):
    return (datetime.now(drip.IST).date() - timedelta(days=days)).strftime("%Y-%m-%d")


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

    async def capture(prompt, invoice_data, tone, channel=None):
        seen.append((prompt, invoice_data, tone, channel))
        return "msg"

    monkeypatch.setattr(drip, "generate_message", capture)
    await _invoice(db, drip_user, "Dated", 21)
    await drip.run_daily_drips()
    prompt, ctx, tone, channel = seen[0]
    assert ctx["due_date"] == _due(21) and _due(21) in prompt and tone == "Firm Warning"
    assert channel == "whatsapp"


async def test_days_overdue_counted_on_ist_date(db, drip_user, monkeypatch):
    """Regression: at 00:15 IST (18:45 UTC the day before) steps fired a day late."""
    real_now = datetime.now(drip.IST)
    fixed = real_now.replace(hour=0, minute=15, second=0, microsecond=0)  # 00:15 IST

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)

    monkeypatch.setattr(drip, "datetime", FrozenDatetime)
    due = (fixed.date() - timedelta(days=7)).strftime("%Y-%m-%d")  # 7 days overdue in IST, 6 in UTC
    await db.get_collection("invoices").insert_one({
        "owner_id": drip_user, "company": "Midnight", "amount": 1000, "invoice_no": "M1",
        "phone": "9876500002", "recovered": False, "due_date": due})
    await drip.run_daily_drips()
    drafts = await _drafts(db, drip_user)
    assert [d["drip_day"] for d in drafts] == [7]
    assert drafts[0]["contact_phone"] == "919876500002"  # country code added


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


CRON_AUTH = {"Authorization": "Bearer s3cret-value"}


@pytest.fixture
def cron_secret(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "cron_secret", "s3cret-value")


async def test_cron_endpoint_runs_once_per_day(db, drip_user, new_client, cron_secret):
    await _invoice(db, drip_user, "Cron", 7)
    c = new_client()
    first = (await c.get("/api/cron/drips", headers=CRON_AUTH)).json()
    second = (await c.get("/api/cron/drips", headers=CRON_AUTH)).json()
    assert first["status"] == "ok" and first["drafted"] == 1
    assert second == {"status": "skipped", "reason": "already ran today"}


async def test_cron_requires_the_secret(db, new_client, cron_secret):
    c = new_client()
    assert (await c.get("/api/cron/drips")).status_code == 401
    assert (await c.get("/api/cron/drips", headers={"Authorization": "Bearer wrong"})).status_code == 401


async def test_cron_disabled_without_a_configured_secret(db, new_client, monkeypatch):
    """Regression: with CRON_SECRET unset the endpoint used to be open to anyone."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "cron_secret", "")
    assert (await new_client().get("/api/cron/drips")).status_code == 401


async def test_crashed_cron_run_releases_the_day(db, drip_user, new_client, cron_secret, monkeypatch):
    """Regression: an exception left the daily lock in place, losing the whole day."""
    import app.api.drip as drip_api

    async def boom(**_kw):
        raise RuntimeError("database hiccup")

    monkeypatch.setattr(drip_api, "run_daily_drips", boom)
    c = new_client()
    assert (await c.get("/api/cron/drips", headers=CRON_AUTH)).status_code == 500
    monkeypatch.setattr(drip_api, "run_daily_drips", drip.run_daily_drips)
    assert (await c.get("/api/cron/drips", headers=CRON_AUTH)).json()["status"] == "ok"


async def test_failed_users_keep_the_day_retryable(db, drip_user, new_client, cron_secret, monkeypatch):
    """A user whose whole run fails must not let the day be marked finished."""
    async def user_fails(user, deadline=None):
        raise RuntimeError("cursor died")

    monkeypatch.setattr(drip, "process_drip_for_user", user_fails)
    c = new_client()
    first = (await c.get("/api/cron/drips", headers=CRON_AUTH)).json()
    assert first["status"] == "partial" and first["failed_users"] >= 1
    monkeypatch.undo()
    from app.core.config import settings
    monkeypatch.setattr(settings, "cron_secret", "s3cret-value")
    assert (await c.get("/api/cron/drips", headers=CRON_AUTH)).json()["status"] == "ok"


async def test_reclaimed_run_cannot_touch_the_new_lock(db, drip_user, new_client, cron_secret, monkeypatch):
    """If a slow run is reclaimed, finishing it must not complete the newer run's lock."""
    import app.api.drip as drip_api
    from app.api.drip import _IST
    runs = db.get_collection("cron_runs")
    run_id = f"drips:{datetime.now(_IST).date().isoformat()}"

    async def slow_run_that_gets_reclaimed(**_kw):
        await runs.replace_one({"_id": run_id}, {"_id": run_id, "token": "newer-run",
                                                 "started_at": datetime.now(timezone.utc)})
        return {"users": 0, "drafted": 0, "failed_users": 0, "stopped_early": False}

    monkeypatch.setattr(drip_api, "run_daily_drips", slow_run_that_gets_reclaimed)
    await new_client().get("/api/cron/drips", headers=CRON_AUTH)
    lock = await runs.find_one({"_id": run_id})
    assert lock["token"] == "newer-run" and "finished_at" not in lock


def test_cron_time_budget_must_be_positive():
    from pydantic import ValidationError
    from app.core.config import Settings
    with pytest.raises(ValidationError):
        Settings(cron_time_budget_seconds=0)


async def test_killed_cron_run_can_be_retried(db, drip_user, new_client, cron_secret):
    """A run killed by the platform timeout never finishes; after 15 min it may run again."""
    from app.api.drip import _IST
    run_id = f"drips:{datetime.now(_IST).date().isoformat()}"
    runs = db.get_collection("cron_runs")
    await runs.insert_one({"_id": run_id, "started_at": datetime.now(timezone.utc) - timedelta(hours=1)})
    assert (await new_client().get("/api/cron/drips", headers=CRON_AUTH)).json()["status"] == "ok"
    await runs.update_one({"_id": run_id}, {"$unset": {"finished_at": ""},
                                            "$set": {"started_at": datetime.now(timezone.utc)}})
    # a fresh, still-running lock is respected
    assert (await new_client().get("/api/cron/drips", headers=CRON_AUTH)).json()["status"] == "skipped"


async def test_drip_settings_api_rejects_injection(user_client):
    assert "7" in (await user_client.get("/api/drip-settings")).json()
    ok = await user_client.put("/api/drip-settings", json={"settings": {"7": {"enabled": False, "channel": "whatsapp"}}})
    assert ok.status_code == 200
    bad = await user_client.put("/api/drip-settings", json={"settings": {"$where": {"enabled": True}}})
    assert bad.status_code == 422
