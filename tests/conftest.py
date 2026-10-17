"""
Shared pytest fixtures.

Tests run against a real MongoDB (a service container in CI) because several
guarantees depend on real Mongo behaviour — atomic pipeline updates, unique and
TTL indexes. Gemini and WhatsApp are never called: AI functions are mocked and
the Gemini clients are made to raise if anything tries to reach them.

Local run (needs a MongoDB you can write a throwaway database to):
    TEST_MONGO_URI=mongodb://localhost:27017 pytest
"""
import itertools
import os
import uuid

# ── Isolated settings — must be set before anything imports `app` ────────────
# Every setting the app reads is pinned here so values from a developer's
# local .env (real API keys, the production DB name) can never leak in.
_TEST_DB = os.environ.get("TEST_DB_NAME", "recoverai_test")
if "test" not in _TEST_DB:
    raise RuntimeError(f"Refusing to run tests against non-test database {_TEST_DB!r}")

os.environ.update({
    "MONGO_URI": os.environ.get("TEST_MONGO_URI", "mongodb://localhost:27017"),
    "DB_NAME": _TEST_DB,
    "SECRET_KEY": "test-secret-key-0123456789abcdef0123456789abcdef",
    "GEMINI_API_KEY": "test-gemini-key-not-real",
    "ADMIN_EMAILS": "admin@recoverai-test.com",
    "COOKIE_SECURE": "false",          # httpx test client talks plain http
    "DEBUG": "false",
    "TRUST_PROXY_HEADERS": "false",
    "GOOGLE_CLIENT_ID": "",
    "REDIS_URL": "",
    "CRON_SECRET": "",
    "WEBHOOK_SECRET": "",
    "WHATSAPP_API_TOKEN": "",
    "WHATSAPP_ACCESS_TOKEN": "",
    "WHATSAPP_PHONE_NUMBER_ID": "",
    "WHATSAPP_VERIFY_TOKEN": "test-verify-token",
    "WHATSAPP_WEBHOOK_SECRET": "",
    "WHATSAPP_AUTO_REPLY": "false",
    "IMAP_USER": "",
    "IMAP_PASSWORD": "",
})
os.environ.pop("VERCEL", None)

import httpx
import pytest
import pytest_asyncio
from pymongo import MongoClient

PASSWORD = "Test!Passw0rd#2026"
ADMIN_EMAIL = "admin@recoverai-test.com"


def pytest_sessionstart(session):
    """Start every run from an empty test database."""
    client = MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=10000)
    client.drop_database(_TEST_DB)
    client.close()


def pytest_sessionfinish(session, exitstatus):
    client = MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=10000)
    client.drop_database(_TEST_DB)
    client.close()


@pytest_asyncio.fixture
async def db():
    """Connect the app's shared Motor client for this test's event loop."""
    from app.core import database
    await database.connect_db()
    yield database
    await database.close_db()


@pytest.fixture(autouse=True)
def no_external_ai(monkeypatch):
    """Mock every AI entry point; make the real Gemini clients unusable."""
    async def fake_generate(prompt, invoice_data, tone, channel=None):
        return f"[{tone}] Reminder for {invoice_data.get('company', 'customer')}"

    async def fake_reply(text):
        return {"translated_text": text, "intent": "promise_to_pay", "confidence": "high",
                "suggested_action": "Follow up in 48h", "fallback_mode": None}

    def no_network(*_a, **_k):
        raise AssertionError("tests must not call Gemini")

    import app.api.chat as chat
    import app.api.webhook as webhook
    import app.api.whatsapp_webhook as wa
    import app.services.ai_service as ai
    import app.services.nlp_service as nlp
    import app.workers.drip_scheduler as drip

    monkeypatch.setattr(chat, "ai_generate_message", fake_generate)
    monkeypatch.setattr(drip, "generate_message", fake_generate)
    monkeypatch.setattr(webhook, "process_debtor_reply", fake_reply)
    monkeypatch.setattr(wa, "process_debtor_reply", fake_reply)
    monkeypatch.setattr(ai, "_get_client", no_network)
    monkeypatch.setattr(nlp, "_get_client", no_network)


_ip_counter = itertools.count(1)


@pytest.fixture
def new_client(db):
    """
    Factory for HTTP clients bound to the app. Each client gets its own source
    IP so the firewall and login limiters never leak state between tests.
    """
    from app.main import app
    clients = []

    def make(ip: str | None = None) -> httpx.AsyncClient:
        n = next(_ip_counter)
        transport = httpx.ASGITransport(app=app, client=(ip or f"10.{n // 65536 % 256}.{n // 256 % 256}.{n % 256}", 50000))
        c = httpx.AsyncClient(transport=transport, base_url="http://testserver",
                              headers={"user-agent": "pytest"})
        clients.append(c)
        return c

    yield make


_email_counter = itertools.count(1)
_RUN_ID = uuid.uuid4().hex[:8]


@pytest.fixture
def unique_email():
    """Emails unique across the whole session (a run id guards against leftover data)."""
    return lambda prefix="user": f"{prefix}.{_RUN_ID}.{next(_email_counter)}@recoverai-test.com"


async def register_and_login(client: httpx.AsyncClient, email: str, password: str = PASSWORD,
                             business: str = "Test Traders") -> httpx.Response:
    r = await client.post("/api/auth/register", json={"business_name": business, "email": email, "password": password})
    assert r.status_code in (201, 409), r.text
    r = await client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r


@pytest_asyncio.fixture
async def user_client(new_client, unique_email):
    """A logged-in regular user."""
    c = new_client()
    await register_and_login(c, unique_email())
    return c


@pytest_asyncio.fixture
async def admin_client(new_client):
    """A logged-in admin (ADMIN_EMAILS is pinned above)."""
    c = new_client()
    await register_and_login(c, ADMIN_EMAIL, business="Admin Co")
    return c


INVOICE = {
    "company": "Acme Debtor Ltd", "contact": "Ravi", "phone": "+91 98123 45678", "email": "ravi@acme.test",
    "amount": 125000, "invoiceNo": "INV-T-001", "issueDate": "2026-08-01", "dueDate": "2026-09-01",
    "daysOverdue": 46, "status": "sent",
}
