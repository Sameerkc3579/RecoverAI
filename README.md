<div align="center">
  <img src="https://raw.githubusercontent.com/Sameerkc3579/RecoverAI/main/uploads/logo.png" alt="RecoverAI Logo" width="120" style="border-radius: 12px; margin-bottom: 20px;" onerror="this.src='https://placehold.co/120x120/8B0000/FFFFFF?text=R&font=Montserrat'"/>

  # 🤖 RecoverAI
  **Autonomous Agentic System for MSME Debt Recovery**
  
  [![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
  [![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
  [![MongoDB](https://img.shields.io/badge/MongoDB-4EA94B?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
  [![Google Gemini](https://img.shields.io/badge/Google%20Gemini-8E75B2?style=for-the-badge&logo=googlebard&logoColor=white)](https://ai.google.dev/)
  [![Security](https://img.shields.io/badge/Security-Hardened-success)](https://github.com/Sameerkc3579/RecoverAI)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

  <p align="center">
    An intelligent, automated pipeline designed to bridge the gap in B2B collections. Powered by Google Gemini, RecoverAI negotiates, drafts legal notices, and manages multi-channel communications (WhatsApp & Email) to help MSMEs recover pending invoices efficiently and legally.
  </p>
</div>

---

## ✨ Key Features

- **🧠 Agentic AI Negotiation**: Employs Google Gemini 2.5 Flash to automatically interpret debtor intents (Promise to Pay, Stall, Dispute) and autonomously draft highly tailored, context-aware responses.
- **🛡️ 3-Layer Active Firewall**: Enterprise-grade security featuring IP Rate Limiting, Signature-based attack blocking (SQLi, XSS, Path Traversal), and Honeypot Traps to instantly ban automated vulnerability scanners.
- **📱 WhatsApp & Email Integration**: Full bidirectional support. Features a Meta-compliant webhook architecture for WhatsApp messaging and an automated IMAP background worker for digesting inbound email replies.
- **⚖️ MSMED Act Compliance**: Hardcoded logic implementing Section 15 of the MSME Act, automatically computing compound interest with monthly rests at three times the RBI bank rate.
- **🌐 Public Debtor Portal**: Standalone, magic-link protected public portal (`portal.html`) allowing debtors to securely view their specific invoices, ledgers, and overdue interest breakdowns without needing an account.
- **📄 One-Click Legal Notices**: Generates formal, court-ready PDF Legal Notices using Indian numbering syntax, complete with dynamic financial breakdowns.
- **🔐 Enterprise-Grade RBAC**: Secure multi-tenant architecture employing JWT Bearer tokens, Bcrypt password hashing, and a highly gated "God Mode" dashboard reserved exclusively for platform administrators.
- **🔗 Google Identity Services**: Low-friction onboarding utilizing Google OAuth 2.0 Sign-In workflows.

---

## 🏗️ Architecture Stack

### Backend (The Brain)
- **Framework**: `FastAPI` (Python 3.10+) 
- **Database**: `Motor` (Asynchronous MongoDB driver)
- **AI Engine**: `google-genai` (Native Gemini SDK)
- **Security**: `passlib[bcrypt]`, `PyJWT` (JSON Web Tokens), `google-auth`

### Frontend (The Interface)
- **Library**: `React 18` (via CDN for zero-build MVP deployment)
- **Styling**: Vanilla CSS + `TailwindCSS` (Scoped JIT mode)
- **Data Viz**: `Chart.js`
- **PDF Engine**: `html2pdf.js`

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10+
- MongoDB Cloud Cluster (Atlas)
- Google AI Studio API Key (Gemini)
- Google Cloud Platform OAuth2 Client ID

### 2. Installation
Clone the repository and jump into the directory:
```bash
git clone https://github.com/Sameerkc3579/RecoverAI.git
cd RecoverAI
```

Create a virtual environment and load the dependencies:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Secrets
Create a `.env` file in the root directory mapping the following parameters:
```env
# ── Server Config ──────────────────────
DEBUG=true
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
ADMIN_EMAILS=admin@example.com,backup-admin@example.com

# ── Gemini ─────────────────────────────
GEMINI_API_KEY=your_gemini_api_key_here

# ── MongoDB ────────────────────────────
MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net
DB_NAME=recovery_agent

# ── Google OAuth ───────────────────────
GOOGLE_CLIENT_ID=your_google_cloud_client_id.apps.googleusercontent.com

# ── JWT Security ───────────────────────
SECRET_KEY=generate_a_cryptographically_secure_random_string_here
ALGORITHM=HS256

# ── Webhooks & Workers (Optional) ──────
WHATSAPP_VERIFY_TOKEN=my_secure_token
IMAP_HOST=imap.gmail.com
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_app_password
```

### 4. Ignition
Launch the FastAPI uvicorn worker:
```bash
uvicorn app.main:app --reload --port 8000
```
Browse to `http://localhost:8000` to access the main interface.

---

## 👁️ God Mode (Admin Architecture)

The system features a hidden administration plane ("God Mode") that conducts data aggregation across the entire user base using optimized MongoDB `$facet` pipelines.

**To access God Mode:**
1. Ensure your authentication `.env` contains your specific administrative email under `ADMIN_EMAILS`.
2. The core system statically verifies your identity token against this list.
3. Upon identifying the master record, the React interface dynamically unlocks the God Mode GUI, exposing the master users table and platform-wide financial telemetry.

---

## ☁️ Deployment (Vercel)

This application is structurally prepared for instant Serverless deployment via Vercel.

1. Import the GitHub repository into your Vercel Dashboard.
2. Define the exact environmental variables mapped in the local `.env`.
3. Vercel utilizes the predefined `vercel.json` routing matrix, funneling all traffic through `app/main.py`.

---

<div align="center">
  <b>Built with execution by Sameer Choudhary</b><br>
  RecoverAI is engineering the financial baseline for Micro, Small and Medium Enterprises.
</div>
