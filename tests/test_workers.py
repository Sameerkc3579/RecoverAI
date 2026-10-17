"""Shared security store internals and the email ingester worker."""
import asyncio
import time

import pytest

import app.core.security as security
import app.workers.email_ingester as ingester


# ── Shared security store ─────────────────────────────────────────────────────

async def test_concurrent_failures_counted_atomically(db):
    ip = "198.51.100.77"
    await asyncio.gather(*(security.rate_limit_check(ip) for _ in range(5)))
    doc = await db.get_collection("auth_rate_limits").find_one({"_id": f"login:{ip}"})
    assert doc["count"] == 5


async def test_expired_revocation_not_enforced(db):
    await security.revoke_token("jti-expired", time.time() - 5)
    security._REVOKED_TOKENS.clear()
    assert await security.is_token_revoked_async("jti-expired") is False


async def test_unreachable_redis_backs_off_and_retries(db, monkeypatch):
    """A failing Redis is paused with backoff, never dropped for the process lifetime."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1")  # nothing listens here
    monkeypatch.setattr(security, "_redis_client", None)
    monkeypatch.setattr(security, "_redis_unusable", False)
    monkeypatch.setattr(security, "_redis_retry_at", 0.0)
    monkeypatch.setattr(security, "_redis_backoff", 30.0)

    await security.rate_limit_check("198.51.100.78")          # Redis fails → MongoDB
    assert security._redis_client is None and not security._redis_unusable
    assert 25 < security._redis_retry_at - time.time() <= 30
    security._redis_retry_at = 0.0                             # cooldown elapsed
    await security.rate_limit_check("198.51.100.78")          # retried, fails again
    assert security._redis_backoff == 120.0


# ── Email ingester ────────────────────────────────────────────────────────────

FIELDS = {"debtor_name": "Wayne Enterprises", "amount": 145000, "invoice_no": "INV-2026-999",
          "due_date": "2026-10-31", "issue_date": "2026-10-01"}


async def test_ingested_invoice_is_linked_and_idempotent(db):
    """Regression: the worker never initialised the shared DB client, so customer
    linking crashed after insert and the idempotency log was never written."""
    from app.core.config import settings
    await db.close_db()  # start like the standalone worker: no shared client yet
    orch = ingester.EmailIngesterOrchestrator()
    await orch._init_mongo()
    mdb = orch._mongo_client[settings.db_name]
    owner = (await mdb.users.insert_one({"email": "vendor@recoverai-test.com"})).inserted_id

    invoice = ingester.GeminiExtractionAgent._fields_to_invoice_create(FIELDS, "Vendor <v@x.test>", "Invoice", "inv.pdf")
    inserted = await orch._mongo_agent.insert_invoice(invoice, "<msg-1@test>", "inv.pdf", "Vendor", "Invoice",
                                                      owner_id=str(owner), status="success")
    assert inserted
    saved = await mdb.invoices.find_one({"owner_id": owner})
    assert saved["company"] == "Wayne Enterprises" and saved["amount"] == 145000
    assert saved.get("customer_id"), "invoice was not linked to a customer"
    assert await orch._mongo_agent.is_duplicate("<msg-1@test>", "inv.pdf")
    await orch._close_mongo()


async def test_dry_run_never_touches_the_mailbox(monkeypatch):
    monkeypatch.setattr(ingester, "DRY_RUN", True)
    agent = ingester.IMAPParserAgent()

    def must_not_connect():
        raise AssertionError("dry run must not open a write connection")

    monkeypatch.setattr(agent, "_connect", must_not_connect)
    await agent.mark_processed(b"42")  # returns without connecting


def test_single_run_lock():
    first = ingester._acquire_run_lock()
    try:
        assert first is not None
        assert ingester._acquire_run_lock() is None  # same lock file, already held
    finally:
        first.close()
    again = ingester._acquire_run_lock()
    assert again is not None
    again.close()
