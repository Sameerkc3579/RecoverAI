"""Registration, login, session cookies, refresh, logout and brute-force limits."""
import app.core.security as security
from conftest import PASSWORD, register_and_login


async def test_register_login_and_me(new_client, unique_email):
    c = new_client()
    email = unique_email()
    r = await register_and_login(c, email)
    assert "access_token" in c.cookies and "refresh_token" in c.cookies
    assert r.json()["email"] == email

    me = await c.get("/api/users/me")
    assert me.status_code == 200 and me.json()["email"] == email
    assert "hashed_password" not in me.text


async def test_duplicate_and_weak_registration_rejected(new_client, unique_email):
    c = new_client()
    email = unique_email()
    await register_and_login(c, email)
    dup = await c.post("/api/auth/register", json={"business_name": "X", "email": email, "password": PASSWORD})
    assert dup.status_code == 409
    weak = await c.post("/api/auth/register", json={"business_name": "X", "email": unique_email(), "password": "password1"})
    assert weak.status_code == 422


async def test_wrong_password_and_unknown_email_both_401(new_client, unique_email):
    """Unknown emails used to 500 (malformed dummy bcrypt hash), revealing which emails exist."""
    c = new_client()
    email = unique_email()
    await register_and_login(c, email)
    wrong = await c.post("/api/auth/login", data={"username": email, "password": "Wrong!Pass123"})
    unknown = await c.post("/api/auth/login", data={"username": "nobody@recoverai-test.com", "password": "Any!Pass123"})
    assert wrong.status_code == 401
    assert unknown.status_code == 401
    assert wrong.json() == unknown.json()  # no user enumeration


async def test_protected_routes_require_auth(new_client):
    c = new_client()
    for path in ("/api/invoices", "/api/customers", "/api/users/me", "/api/drip-settings", "/api/whatsapp/status"):
        assert (await c.get(path)).status_code == 401, path


async def test_refresh_accepts_the_httponly_cookie(user_client):
    r = await user_client.post("/api/auth/refresh")
    assert r.status_code == 200
    assert (await user_client.get("/api/users/me")).status_code == 200


async def test_logout_via_cookie_revokes_session(user_client):
    """The browser sends only cookies; logout used to require an Authorization header."""
    old_token = user_client.cookies["access_token"]
    r = await user_client.post("/api/auth/logout")
    assert r.status_code == 200

    # Replaying the old token must fail even though the client still holds it
    user_client.cookies.set("access_token", old_token)
    assert (await user_client.get("/api/users/me")).status_code == 401


async def test_logout_prefers_cookie_over_placeholder_header(user_client):
    """The landing app sends 'Bearer active' (a flag, not a token) alongside the cookie."""
    token = user_client.cookies["access_token"]
    r = await user_client.post("/api/auth/logout", headers={"Authorization": "Bearer active"})
    assert r.status_code == 200
    user_client.cookies.set("access_token", token)
    assert (await user_client.get("/api/users/me")).status_code == 401


async def test_revocation_is_shared_across_instances(user_client):
    """Another worker/serverless instance (empty local cache) must still reject the token."""
    token = user_client.cookies["access_token"]
    await user_client.post("/api/auth/logout")
    security._REVOKED_TOKENS.clear()  # simulate a different instance
    user_client.cookies.set("access_token", token)
    assert (await user_client.get("/api/users/me")).status_code == 401


async def test_five_failed_logins_lock_the_ip(new_client, unique_email):
    """Each failure counts once (it used to count twice), and the lock holds across instances."""
    c = new_client()
    email = unique_email()
    await register_and_login(c, email)
    for i in range(5):
        r = await c.post("/api/auth/login", data={"username": email, "password": f"Wrong!Pass{i}"})
        assert r.status_code == 401, f"attempt {i + 1} should still be allowed"
    security._rate_limit_store.clear()  # different instance
    locked = await c.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert locked.status_code == 429


async def test_successful_login_resets_failures(new_client, unique_email):
    c = new_client()
    email = unique_email()
    await register_and_login(c, email)
    for i in range(4):
        await c.post("/api/auth/login", data={"username": email, "password": f"Wrong!Pass{i}"})
    assert (await c.post("/api/auth/login", data={"username": email, "password": PASSWORD})).status_code == 200
    for i in range(4):
        assert (await c.post("/api/auth/login", data={"username": email, "password": f"Wrong!Again{i}"})).status_code == 401


async def test_registrations_do_not_use_the_login_budget(new_client, unique_email):
    c = new_client()
    for _ in range(4):
        await c.post("/api/auth/register", json={"business_name": "X", "email": unique_email(), "password": PASSWORD})
    email = unique_email()
    await register_and_login(c, email)  # 5th registration, then login must work


async def test_settings_update_is_allowlisted(user_client):
    r = await user_client.put("/api/users/me/settings", json={"ownerName": "Owner One", "reminderDays": [7, 14]})
    assert r.status_code == 200
    me = (await user_client.get("/api/users/me")).json()
    assert me["settings"]["ownerName"] == "Owner One"
    bad = await user_client.put("/api/users/me/settings", json={"reminderDays": [0, 999]})
    assert bad.status_code == 422
