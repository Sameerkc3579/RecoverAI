# 🤖 RecoverAI - Comprehensive Project Summary

This document serves as a complete record of the architecture, features, security remediations, and enhancements implemented in the **RecoverAI** project.

## 1. 🔒 Security Hardening & Vulnerability Remediations
A comprehensive security audit of the FastAPI backend was conducted, resulting in several critical patches to ensure production-grade security.

### A. Authentication & Access Control (`app/api/auth.py`)
*   **Brute Force Protection:** IP-based limiter that locks out an IP after 5 failed login attempts within a 15-minute window. Counters live in MongoDB (Redis if configured), so the lockout holds across every serverless instance.
*   **IP Spoofing Prevention:** Hardened the client IP extraction logic to safely parse the `X-Forwarded-For` header by resolving the rightmost public IP, mitigating proxy IP spoofing.
*   **No User Enumeration:** Standardized authentication error messages to prevent attackers from determining if an email exists in the system.
*   **Strong Password Policy:** Enforced strict password strength requirements (min 8 chars, uppercase, lowercase, numbers, special characters) via `app/core/security.py`.
*   **Secure Logout & Token Revocation:** JWT ID (`jti`) blacklist stored in MongoDB with a TTL index, so a logged-out token is rejected by every instance immediately.
*   **Endpoint Protection:** Secured previously open AI and Webhook endpoints (`/api/generate-message`, `/api/bulk-generate`, `/api/debtor-reply`) by enforcing strict JWT authentication (`get_current_user`).

### B. NoSQL Injection Prevention (`app/api/invoices.py`, `app/api/admin.py`)
*   **Payload Sanitization:** Implemented recursive payload sanitization to strip all MongoDB operators (keys starting with `$`) from user inputs during `PATCH`/`PUT` operations.
*   **Protected Fields:** Explicitly blocked client-side modifications to protected fields like `_id`, `owner_id`, and `hashed_password` to prevent privilege escalation.
*   **Safe Sorting:** Restricted query sort parameters in the Admin API to a hardcoded allowlist, preventing NoSQL injection via arbitrary field probing.

### C. Server-Side Request Forgery (SSRF) Protection (`app/api/enrich.py`)
*   **Network Layer Blocking:** Rewrote the contact enrichment web scraper to parse URLs, resolve hostnames to IP addresses, and aggressively block requests targeting private, link-local, loopback, or cloud metadata IP ranges (RFC 1918, RFC 3927).
*   **SSL Verification:** Re-enabled strict SSL verification for outbound scraping requests to mitigate Man-in-the-Middle (MITM) attacks.

### D. Secure File Uploads (`app/api/invoices.py`)
*   **MIME & Extension Validation:** Enforced a strict allowlist for file extensions (`.pdf`, `.png`, `.jpg`, `.jpeg`) and verified the `Content-Type` header for proof-of-delivery uploads.
*   **Filename Sanitization:** Eliminated Path Traversal risks by stripping the original user-provided filename and saving files using auto-generated UUIDs.
*   **Payload Size Limiting:** Implemented chunk-based file reading with a strict 10MB limit.

### E. Security Middleware Stack (`app/core/middleware.py`)
*   **Raw ASGI Implementation:** Deployed raw ASGI middleware to avoid Python 3.11+ `ExceptionGroup` crashes associated with `BaseHTTPMiddleware`.
*   **Security Headers:** Injected robust HTTP security headers (`HSTS`, `CSP`, `X-Frame-Options`, `X-XSS-Protection`) and stripped server fingerprinting (`Server`, `X-Powered-By`).
*   **Audit Logging:** Implemented structured access logging to capture HTTP method, path, IP, duration, and status code for all requests.
*   **Request Size Limits:** Blocked excessively large payload bodies globally to mitigate Denial of Service (DoS) attacks.

---

## 2. 🧠 AI/ML & Natural Language Processing
The platform utilizes Google Gemini models for automated intent analysis and response generation (`app/services/nlp_service.py`, `app/services/ai_service.py`).

*   **Agentic NLP Pipeline:** 
    1.  **Translation:** Converts Hindi, Hinglish, and regional Indian languages into professional English.
    2.  **Intent Classification:** Categorizes debtor responses into `promise_to_pay`, `dispute`, `stall`, or `unknown`.
    3.  **Action Suggestion:** Recommends precise follow-up actions based on intent.
*   **Resilience & Heuristic Fallback:** Engineered a keyword-based fallback classifier. If the Gemini API hits a quota limit (HTTP 429) or overloads (HTTP 503), the system gracefully falls back to local Hindi/Hinglish keyword matching (e.g., "kal", "payment", "galat", "baad mein"), ensuring zero downtime.
*   **Model Cascading:** The AI service tries `gemini-2.5-flash`, retries once on transient errors, cascades to `gemini-3.5-flash-lite`, and finally to the `gemini-flash-latest` alias as a last resort.
*   **Bulk Generation:** Added features to concurrently draft context-aware WhatsApp messages for multiple invoices.

---

## 3. ⚖️ Financial Engine & MSMED Act Compliance
Designed specifically for Indian MSMEs to legally enforce debt recovery (`app/services/recovery_logic.py`).

*   **Statutory Interest Calculator:** Hardcoded logic to apply Sections 15–17 of the MSMED Act 2006.
*   **Compound Interest:** Calculates accrued penalty interest at **3x the RBI Bank Rate** with monthly rests for any invoice past its due date.
*   **Legal Notice Generator:** Generates professional, court-ready PDF Legal Notices dynamically on the frontend using `html2pdf.js`, automatically embedding the exact MSMED compound interest calculation and a 15-day ultimatum.

---

## 4. 💻 Frontend & UI/UX Enhancements
The frontend relies on a zero-build React MVP architecture (loaded via CDN & Babel) for extreme portability (`static/js/`, `static/css/`).

*   **Dark Mode Integration:** Built a global Dark Mode toggle utilizing CSS variables (`var(--surface)`, `var(--text)`, etc.) across all components to deliver a premium user experience.
*   **Dashboard Visualizations:** Integrated `Chart.js` for dynamic analytics:
    *   6-month Outstanding vs. Recovered bar chart.
    *   Pipeline by Stage doughnut chart with automatic calculations.
*   **Bulk CSV Import:** Developed a drag-and-drop CSV importer allowing users to instantly onboard up to 500 invoices with automatic column mapping.
*   **Admin Dashboard (God Mode):** Refined the platform-wide God Mode, giving administrators insights into total platform volume, active users, system-wide recovery rates, and the ability to manage or suspend accounts.
*   **Modern Aesthetics:** Applied modern UI paradigms like pill-shaped status badges, glassmorphism hints, Plus Jakarta Sans typography, and smooth micro-animations.

---

## 5. ☁️ Deployment Architecture
*   **Serverless Ready:** The application contains a `vercel.json` routing matrix, making the FastAPI backend immediately deployable to Vercel Serverless Functions.
*   **MongoDB Atlas:** Fully async data layer utilizing `motor` and `$facet` aggregation pipelines for high-performance dashboard analytics.
