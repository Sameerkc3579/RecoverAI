# RecoverAI — Bug Report

A consolidated list of bugs found during a code review of the FastAPI backend (`app/`)
and the zero-build React frontend (`static/js/`). Ordered by severity.

Legend: 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low

---

## Status (2026-10-17) — pre-push health check

Verified with an end-to-end API suite (105 checks) and a headless-browser pass over every
dashboard page, on both the local venv and a fresh install of `requirements.txt` (Python 3.12).

- ✅ Fresh deploy broke password auth — `passlib 1.7.4` crashes with `bcrypt>=4.1`; pinned `bcrypt==4.0.1`.
- ✅ Firewall shared one per-IP counter across all paths, so normal browsing tripped the 15/min
  auth limit (429 on login/logout, then a 15-min IP ban) — each tier now has its own counter.
- ✅ Login limiter counted every failure twice and registrations used the login budget —
  pre-check is read-only; register has its own scope.
- ✅ Logout ignored the HttpOnly cookie (header-only) so tokens were never revoked or cleared;
  refresh-token revoke was missing `audience`/`issuer`. `/refresh` now also accepts the cookie.
- ✅ `whatsapp_webhook` router was never mounted — Debtor Inbox `/api/whatsapp/{messages,status,send}`
  and Meta's `/api/webhooks/whatsapp` returned 404.
- ✅ WhatsApp send read only `WHATSAPP_ACCESS_TOKEN`; now falls back to `WHATSAPP_API_TOKEN`.
- ✅ Upload-proof accepted any bytes when magic bytes were unrecognised — now rejected.
- ✅ Admin activity feed 500'd on invoices without `issueDate` (None in sort).
- ✅ Drip skipped every formatted phone ("+91 98765 43210"); prompt lacked the due date (AI wrote a placeholder).
- ✅ Drip: atomic per-(invoice, step) claim + unique index (no duplicates across workers) and a
  3-day grace window for missed midnights. Email ingester: single-run OS lock.
- ✅ Google login "Rate limit exceeded" — landing `/assets/*` loads counted toward the (shared)
  firewall budget; `/assets/` + favicon now exempt, and on Vercel the real client IP from
  `X-Forwarded-For` is used (`settings.proxy_headers_trusted`) so visitors don't share one bucket.
- ✅ Drip on Vercel — `GET /api/cron/drips` + `crons` in `vercel.json` (00:00 IST). Once-per-day
  Mongo lock, optional `CRON_SECRET`, 50 s time budget, stale-claim recovery after 30 min.
- ✅ Email ingester never initialised the shared DB client, so every emailed invoice was saved but
  not linked to a customer, not idempotency-logged, and reported as failed. Added `--dry-run`
  (read-only mailbox, no inserts) for safe testing against a live inbox.
- ✅ Security state now shared across instances (was bug #14): revocations live in MongoDB
  (`revoked_tokens`, TTL-indexed) as the single source of truth; the login/register limiter uses
  Redis if reachable, else MongoDB (`auth_rate_limits`), else memory. `deps.py` now checks the
  shared blacklist (it only checked local memory). A failing Redis is retried with backoff
  (30 s → 10 min) rather than dropped; a localhost `REDIS_URL` is ignored on Vercel.
  The firewall's general throttle stays per-instance by design (per-request DB hits; Vercel has
  platform DDoS protection).
- ✅ Login with an unknown email returned 500 (malformed dummy bcrypt hash) — also leaked which
  emails exist. Replaced with a valid hash; now a uniform 401.
- ✅ Landing bundle stored the access + refresh tokens in localStorage. Patched the built bundle
  (source not in repo) to store only an `"active"` flag; renamed to `index-Ave8lZIs.js` for
  cache-busting. Auth uses the HttpOnly cookie; logout reads the cookie first; the dashboard
  fetches the identity from `/api/users/me` once per session (replacing cached details) and keeps
  the email in memory only — localStorage holds just the display name.
- Open (external): inbound WhatsApp needs `WHATSAPP_WEBHOOK_SECRET` once Meta approves the app —
  the webhook fails closed until then.

---

## Status (2026-06-10)

**Major bugs (Critical + High) — FIXED:**
- ✅ #1 JWT audience mismatch — `security.py` (constants), `deps.py`, `auth.py` (3 decode sites now pass `audience`/`issuer`). Verified round-trip.
- ✅ #2 Enrichment HTTPS broken — `enrich.py` `_fetch_html` now fetches the hostname URL (correct TLS) and runs off the event loop via `run_in_threadpool`.
- ✅ #3 Enrichment fabricated data — `enrich.py` no longer invents `accounts@<domain>` / fake phone; returns null when not found.
- ✅ #4 Settings wipe — `users.py` now merges via dotted `settings.<key>` keys.
- ✅ #5 CSV import corruption — `Invoices.js` uses a proper `splitCSVLine` parser; cache-buster bumped to `?v=21`. Verified.
- ✅ #6 Email `From` spoofing — `email_ingester.py` adds an SPF/DKIM/DMARC alignment gate (`REQUIRE_SENDER_AUTH`, fail-closed).
- ✅ #7 X-Forwarded-For spoofing — `auth.py` + `firewall.py` gated behind new `trust_proxy_headers` setting (default False).
- ✅ #16 (folded into #7) firewall `172.x` misclassification — fixed by switching to `ipaddress` CIDR checks.

**Medium + Low (#8–#26, except #16) — FIXED:**
- ✅ #8 Audit middleware order — `main.py` middleware add-order reversed so runtime order
  is AuditLog → SecurityHeaders → CORS → Firewall → RequestSizeLimit → app; blocked/oversized
  requests are now audit-logged and get security headers.
- ✅ #9 FirewallMiddleware → raw ASGI — `firewall.py` rewritten from `BaseHTTPMiddleware` to
  `__init__(app)` / `async def __call__(scope, receive, send)`, all 3 layers and
  `trust_proxy_headers`-gated `_get_client_ip` preserved.
- ✅ #10 Admin "last 6 months" — `admin.py` `monthly_recovered` facet now sorts desc, limits 6,
  re-sorts asc; comment notes it groups by `issueDate` (known limitation).
- ✅ #11 Portal magic links — `invoices.py` `generate_portal_link` now persists a
  `portal_tokens` doc (token, invoice_id, owner_id, created_at, expires_at = +7d); new
  `GET /api/invoices/portal/{token}` (no auth) returns a minimal owner-data-safe view
  (company, amount, invoiceNo, dueDate, daysOverdue, status, interestAccrued, totalPayable)
  or 404. **Frontend page now implemented:** `portal.html` (standalone, vanilla JS, XSS-safe
  via textContent) served at `/portal` (route in `main.py`, added to `vercel.json`). Also
  fixed an alias bug — the endpoint read `invoice_no`/`due_date` but invoices are stored as
  `invoiceNo`/`dueDate`, so those fields had been returning null.
- ✅ #12 Invoice PATCH typed — added `InvoiceUpdate` model in `schemas.py` (all-Optional,
  `populate_by_name=True`); `update_invoice` uses `model_dump(by_alias=True, exclude_unset=True)`
  then still runs `_sanitize_update_payload`. `recovery_logic.calculate_msme_interest` now
  coerces `principal` to float and returns zero result if non-numeric.
- ✅ #13 `is_active` default — `deps.py` now defaults to `True`, matching `auth.py`.
- ✅ #14 In-memory security state — documented only (no Redis). `main.py` `startup_event`
  now logs a warning on Vercel/multi-worker that the JWT blacklist, login rate limiter, and
  firewall bans are per-process and recommends Redis. Status: documented, needs infra.
- ✅ #15 Gemini service — `FALLBACK_MODEL` changed to `gemini-2.0-flash` (genuinely tiered
  vs. `LEGACY_MODEL=gemini-1.5-flash`); retry sleeps reduced to 1s/2s constants
  (`_RETRY_DELAY_1`/`_RETRY_DELAY_2`); `_call` now raises on `None`/empty `response.text`
  (treated as transient, cascades through retries/fallback) instead of returning null.
- ✅ #17 JPEG upload — `invoices.py` now treats `image/jpg`/`image/jpeg` as equivalent before
  the magic-byte mismatch check.
- ✅ #18 Global body limit — `main.py` `RequestSizeLimitMiddleware` now uses
  `max_upload_size_mb + 2` for headroom; comment notes the per-endpoint chunked read in
  `upload-proof` still enforces the true cap.
- ✅ #19 WhatsApp send regex — `whatsapp_webhook.py` now computes digits-only, takes the last
  10, and wraps with `re.escape(...)` (mirrors `_find_invoice_by_phone`).
- ✅ #20 Unreachable RuntimeError branch — `webhook.py` now calls `process_debtor_reply`
  directly with a comment explaining it never raises.
- ✅ #21 nlp_service lazy client — `nlp_service.py` converted module-level `_client` to a
  lazy `_get_client()` getter, mirroring `ai_service.py`.
- ✅ #22 Startup diagnostic — `main.py` import-health check now probes `jwt` instead of `jose`.
- ✅ #23 Admin user-edit — `UserUpdateRequest.email` is now `EmailStr`; `update_user` checks
  no other user already has the new email (409 if so).
- ✅ #24 Duplicate `/index.html` — removed the duplicate decorator from the `dashboard()`
  group, kept the one on `serve_app_shell`.
- ✅ #25 Dead duplicate frontend files — confirmed `app.js`/`components/Dashboard.js` are
  unreferenced in any HTML; `git rm`'d both.
- ✅ #26 Committed cruft — `git rm --cached temp_settings.json` and added it to
  `.gitignore`. `test_*.py` files left as-is (read keys from env, low risk).

---

## 🔴 Critical

### 1. JWT audience mismatch breaks ALL authentication
**Files:** `app/core/security.py:121-122,141-142`, `app/api/deps.py:46`, `app/api/auth.py:405,444`

Tokens are *created* with `aud: "recoverai-api"` and `iss: "recoverai"` claims (added in
commit `d196c1e` during the `python-jose` → `PyJWT` migration), but every `jwt.decode()`
call site decodes **without** passing `audience=`. PyJWT 2.10.1 (the pinned version) raises
`InvalidAudienceError` whenever a token contains an `aud` claim and no audience is supplied.
Verified empirically:

```
DECODE FAILS: InvalidAudienceError Invalid audience
```

**Impact:**
- `get_current_user` (`deps.py:46`) always returns 401 → **every authenticated endpoint is
  unusable** (invoices, customers, admin, chat, settings, WhatsApp management). Login issues
  a token, then nothing accepts it.
- `/api/auth/refresh` (`auth.py:444`) always 401s → frontend auto-refresh force-logs-out users.
- `/api/auth/logout` (`auth.py:405`) swallows the error and **never revokes** the token, yet
  still returns "Logged out successfully".

**Fix:** Pass `audience="recoverai-api", issuer="recoverai"` to all three `jwt.decode()` calls
(or stop emitting the `aud`/`iss` claims).

---

## 🟠 High

### 2. Contact enrichment is broken by its own SSRF fix (HTTPS never works)
**File:** `app/api/enrich.py:172-198`

The anti-DNS-rebinding fix connects to `https://{resolved_ip}:443/...` with SSL verification
enabled. TLS then validates the certificate against the IP literal (and sends no/wrong SNI),
so the handshake fails for essentially every real HTTPS site → caught → generic 400
("Could not connect to the website"). The original hostname must be used for SNI + cert
validation while connecting to the pinned IP.

Compounding issue: `_fetch_html` calls synchronous `session.get(...)` directly inside an
`async def` handler, blocking the event loop for up to 15 s per request.

### 3. Enrichment silently fabricates contact data
**File:** `app/api/enrich.py:265-270`

When scraping fails or finds nothing, the endpoint returns `accounts@{domain}` and the fake
phone `+91 99999 00000` as if they were discovered. Combined with bug #2, it returns made-up
contacts for nearly every request, with no flag indicating they're fabricated — dangerous in
a debt-collection workflow.

### 4. Settings save wipes all previously-saved settings
**File:** `app/api/users.py:65`

`update_settings` does `set_fields["settings"] = update_data`, replacing the entire nested
`settings` sub-document on every PUT. Updating just `phone` silently deletes `gstin`,
`reminderDays`, `commissionRate`, and everything else. Should use dotted `$set` keys
(`settings.phone`) or merge into the existing object.

### 5. CSV bulk import silently imports corrupted data
**File:** `static/js/components/Invoices.js:64`

The parser uses `line.match(/(?:"([^"]*)"|([^,]*))/g)`. The `[^,]*` alternative matches the
empty string at every comma boundary, so the global match returns twice as many elements as
columns, alternating real-value / empty-string. Verified:

```
input:  Acme Corp,Raj Kumar,raj@acme.com,9876543210,Mumbai
match:  ["Acme Corp","","Raj Kumar","","raj@acme.com","","9876543210","","Mumbai",""]
parsed: {company:"Acme Corp", contact:"", email:"Raj Kumar", phone:"", city:"raj@acme.com"}
```

Every field past the first shifts into the wrong column; `amount` misaligns and rows get
dropped by `.filter(r => r.company && r.amount > 0)` or imported with scrambled fields. Breaks
the flagship "onboard up to 500 invoices via CSV" feature — even the shipped
`downloadTemplate()` sample triggers it. Needs a real CSV parser, not this alternation regex.

### 6. Email ingester trusts the spoofable `From` header for tenant assignment
**File:** `app/workers/email_ingester.py:247-248,669-676`

"Zero-trust sender verification" matches the raw `From:` address to a registered user, then
files the extracted invoice into that user's account (`owner_id`). `From:` is trivially
forgeable (no SPF/DKIM/ARC check), so anyone who knows a customer's email can mail a PDF and
inject attacker-controlled invoices into that tenant's account.

### 7. Rate limiter & firewall trust `X-Forwarded-For` unconditionally
**Files:** `app/api/auth.py:109-143`, `app/core/firewall.py:84-93`

When the app isn't behind a trusted proxy (plain `uvicorn`), `X-Forwarded-For` is fully
attacker-controlled:
- Rotating spoofed public IPs bypasses the login brute-force limiter and firewall bans.
- Spoofing a victim's IP into a honeypot path (e.g. `/wp-admin`) bans that victim for 1 hour.

There should be a "trusted proxy" toggle; with no proxy, only `request.client.host` is safe.
(See also #16 for the `172.x` range bug in the firewall's IP classification.)

---

## 🟡 Medium

### 8. Audit middleware does NOT log blocked requests (opposite of its stated purpose)
**Files:** `app/main.py:133-147`, `app/core/middleware.py:122`

`add_middleware` makes the *last*-added middleware outermost, so the real order is
CORS → Firewall → SecurityHeaders → RequestSizeLimit → **AuditLog (innermost)**. The comment
claims AuditLog is outermost and "logs every request including blocked ones," but
firewall-blocked and oversized requests never reach it — defeating the forensic purpose.
Security headers are likewise skipped on firewall-blocked responses.

### 9. FirewallMiddleware uses the exact base class the codebase warns against
**File:** `app/core/firewall.py:72`

`FirewallMiddleware` extends `BaseHTTPMiddleware` — the class `app/core/middleware.py`'s
header explicitly warns causes `ExceptionGroup` "Exception in ASGI application" crashes on
Python 3.11+ (which is why the other three middlewares are raw ASGI). Should be rewritten as
raw ASGI middleware.

### 10. Admin "last 6 months recovered" chart shows the *first* 6 months
**File:** `app/api/admin.py:118-127`

The `monthly_recovered` facet sorts ascending then `$limit: 6`, returning the oldest six
months ever recorded instead of the most recent. It also groups by `issueDate`, not the
recovery date.

### 11. Magic portal links are never persisted and have no route
**Files:** `app/api/invoices.py:329-355`, `app/main.py` (no `/portal` route),
`static/js/components/Settings.js:26-35`

`generate_portal_link` mints `tok_<uuid>` and returns a `/portal?token=...` URL but stores the
token nowhere, and there is no `/portal` backend route or SPA catch-all. The frontend shows
the link; anyone who opens it gets a 404, and the token validates nothing. Feature is
non-functional.

### 12. Invoice PATCH accepts an arbitrary untyped dict
**File:** `app/api/invoices.py:181`

The body is a raw `dict`; after stripping `$`/protected keys it's `$set` straight into Mongo.
A client can set `amount: "abc"` or inject arbitrary fields. A non-numeric `amount` later
crashes `calculate_msme_interest` multiplication (`recovery_logic.py:65`, only the date parse
is guarded) → `GET /api/invoices` 500s permanently for that user. Use a typed `Optional`-field
model like the admin endpoints. (Also `_DANGEROUS_MONGO_OPERATORS` at `invoices.py:51` is dead
code — the sanitizer strips all `$` keys regardless.)

### 13. `is_active` default is inconsistent between login and request validation
**Files:** `app/api/deps.py:75` vs `app/api/auth.py:283,369,468`

`deps.py` uses `user.get("is_active", False)` while auth uses default `True`. A user document
missing the field (e.g. seeded data) can log in and refresh tokens but gets 403 on every
actual API call.

### 14. In-memory security state is a no-op on serverless (Vercel)
**Files:** `app/core/security.py:68`, `app/api/auth.py:65`, `app/core/firewall.py:78`

The jti revocation blacklist, login rate limiter, and firewall ban store are all per-process
dicts. The repo ships `vercel.json` and deploys serverless, where each invocation may hit a
fresh instance — so logout revocation, brute-force lockouts, and bans silently don't work in
the advertised deployment. Comments say "replace with Redis," but nothing does.

### 15. Gemini "model cascade" is fictional + blocking sleeps + can return null
**File:** `app/services/ai_service.py:28-30,124,134`

`FALLBACK_MODEL` and `LEGACY_MODEL` are both `"gemini-1.5-flash"`, so the documented
2.0 → 2.5 → 1.5 cascade is really 2.5 → 2.5 → 1.5 → 1.5. The retry path also `await
asyncio.sleep(10)` + `sleep(20)` *inside the request handler* — on Vercel this exceeds the
function timeout. And `response.text` may be `None` (safety block) → returns `{"message": null}`.

---

## 🟢 Low / Minor

### 16. Firewall treats all of `172.x` as private
**File:** `app/core/firewall.py:90`

`ip.startswith("172.")` classifies all of `172.0.0.0/8` as private; only `172.16–31` are
RFC-1918. Public clients in `172.x` (e.g. Google `172.217.x.x`) get mis-bucketed during
rate-limit IP extraction.

### 17. JPEG uploads can be rejected incorrectly
**File:** `app/api/invoices.py:42,282-293`

`image/jpg` is in the allowed MIME list, but the magic-byte check maps JPEG bytes to
`image/jpeg` and compares strictly against the declared header. A real JPEG declared as
`image/jpg` fails with "File content does not match declared type."

### 18. Global body limit equals the upload limit
**File:** `app/core/middleware.py:84`, `app/main.py:140`

`RequestSizeLimitMiddleware` is set to `max_upload_size_mb` (10 MB), so a 10 MB proof file plus
multipart overhead is rejected with 413 before the upload handler runs. Chunked-encoding
requests (no `Content-Length`) bypass the check entirely.

### 19. WhatsApp send builds an unescaped regex from user input
**File:** `app/api/whatsapp_webhook.py:437-441`

`clean_number` keeps `+`, then `clean_number[-10:]` is used as an unanchored `$regex`. A short
or `+`-containing number produces an invalid/over-broad regex → Mongo error (500) or matches
unintended invoices.

### 20. `webhook.py` has an unreachable error branch
**File:** `app/api/webhook.py:82`

It catches `RuntimeError` from `process_debtor_reply`, but that function never raises — it
always returns a dict (with `fallback_mode: "error"` on failure). The 502 path is dead code.

### 21. `nlp_service` builds the Gemini client at import time
**File:** `app/services/nlp_service.py:39`

Client is constructed at module import, while `ai_service` does it lazily. Inconsistent, and
makes importing the module hard-depend on a valid `GEMINI_API_KEY`.

### 22. Startup diagnostic checks a removed dependency
**File:** `app/main.py:266`

The import-health check still probes `jose`, which was removed from `requirements.txt` in the
PyJWT migration, so it will always report `FAILED`.

### 23. Admin user-edit has no email validation or uniqueness check
**Files:** `app/api/admin.py:64,142-144,322-340`

`UserUpdateRequest.email` is a plain `str` (no `EmailStr`, no duplicate check), so an admin
edit can create two accounts sharing one login email. Also, users missing `is_active` are
counted as neither active nor inactive in `dashboard_stats`.

### 24. Duplicate `/index.html` route registration
**File:** `app/main.py:310,381`

`/index.html` is registered on two different handlers; the second registration is dead.

### 25. Dead duplicate frontend files tracked in git
**Files:** `static/js/app.js`, `static/js/components/Dashboard.js`

`dashboard.html` loads `app_v2.js` and `Dashboard_v2.js`. The older near-identical `app.js`
and `Dashboard.js` (~31 KB each) are unreferenced but still tracked — editing the wrong one is
a silent no-op.

### 26. Committed cruft
**Files:** `temp_settings.json`, `test_key.py`, `test_key_15.py`

Demo/test files tracked in the repo. No live secrets leaked (`temp_settings.json` is a UTF-16
demo profile; `test_key.py` reads the key from env), but they don't belong in version control.

---

## Verified as NOT bugs (false-positive guards)

- **Admin activity feed XSS** — `AdminDashboard.js:229` renders `{a.text}` as a normal
  (auto-escaped) React string, despite `/api/admin/activity` interpolating user-controlled
  `business_name`/`company`. Not exploitable. The `dangerouslySetInnerHTML` at
  `Dashboard_v2.js:448` runs only on the hardcoded `ACTIVITY_LOG` constant.
- **Secrets in git** — `.env` is gitignored and untracked; no credentials are committed.

---

## Coverage / scope note

Fully reviewed: the entire `app/` backend (27 files) and `static/js/config.js`, `Login.js`,
`Invoices.js` (CSV path), plus spot-checks of `AdminDashboard.js`.

**Not yet line-audited:** the ~250 KB inline-React HTML bundles (`dashboard.html`,
`RecoverAI_MVP.html`, `landing.html`), and most of the 18 frontend components
(`DebtorInbox.js`, `WhatsApp.js`, `Modals.js`, `Dashboard_v2` chart math, etc.). The CSV
finding suggests more functional breakage may remain in that layer.

## Suggested fix order

1. **#1 JWT `aud`** — nothing behind auth works until this is fixed.
2. **#5 CSV import** + **#4 settings wipe** — silent data corruption.
3. **#2/#3 enrichment** — broken + fabricates data.
4. **#6/#7 spoofing** — tenant injection and rate-limit bypass.
5. Remaining medium/low items.
