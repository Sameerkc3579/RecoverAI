"""Firewall middleware: per-tier rate limits, static-asset exemption, client IP handling."""
import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.core import firewall
from app.core.firewall import FirewallMiddleware


async def _ok(request):
    return PlainTextResponse("ok")


def _client(ip="203.0.113.50"):
    inner = Starlette(routes=[Route("/{p:path}", _ok, methods=["GET", "POST"])])
    app = FirewallMiddleware(inner)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=(ip, 1234)),
                             base_url="http://t", headers={"user-agent": "Mozilla/5.0"})


async def test_browsing_does_not_block_google_login():
    """Regression: page + /assets loads shared a counter with the 15/min auth limit."""
    async with _client() as c:
        for path in ["/", "/login", "/register", "/dashboard"] * 5 + ["/assets/index-x.js"] * 30:
            await c.get(path)
        for _ in range(3):
            assert (await c.post("/api/auth/google")).status_code == 200


async def test_static_assets_are_never_rate_limited():
    async with _client() as c:
        statuses = {(await c.get(p)).status_code for p in ["/assets/a.js", "/static/b.css", "/favicon.ico"] * 80}
        assert statuses == {200}


async def test_auth_tier_limit_still_applies():
    async with _client() as c:
        codes = [(await c.post("/api/auth/login")).status_code for _ in range(firewall.AUTH_RATE_LIMIT + 1)]
        assert codes[:-1] == [200] * firewall.AUTH_RATE_LIMIT and codes[-1] == 429


async def test_honeypot_bans_scanner():
    async with _client() as c:
        await c.get("/wp-login.php")
        assert (await c.get("/dashboard")).status_code in (403, 429)


@pytest.mark.parametrize("on_vercel, visitor_b_status", [(False, 429), (True, 200)])
async def test_forwarded_ip_trusted_only_on_vercel(monkeypatch, on_vercel, visitor_b_status):
    """Off Vercel, X-Forwarded-For is spoofable and ignored; on Vercel it is the real client IP."""
    if on_vercel:
        monkeypatch.setenv("VERCEL", "1")
    else:
        monkeypatch.delenv("VERCEL", raising=False)
    async with _client(ip="10.0.0.1") as c:
        for _ in range(firewall.AUTH_RATE_LIMIT + 1):
            await c.post("/api/auth/login", headers={"x-forwarded-for": "49.36.1.10"})
        b = await c.post("/api/auth/login", headers={"x-forwarded-for": "103.21.5.77"})
        assert b.status_code == visitor_b_status
