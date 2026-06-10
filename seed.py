"""
RecoveryAgent — MongoDB data seeder.

Populates the 'invoices' collection with 15 realistic Indian MSME invoices.
All dates are computed dynamically relative to today.

Distribution:
  - 3 recovered invoices   (status: "recovered", recovered: True)
  - 4 legal invoices       (status: "legal", >45 days overdue)
  - 3 escalated invoices   (status: "escalated", 35-44 days overdue)
  - 3 reminded invoices    (status: "reminded", 15-34 days overdue)
  - 2 sent invoices        (status: "sent", <15 days overdue)

Usage:
    python seed.py
"""
import asyncio
import os
import sys
from datetime import date, timedelta
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load .env from the project root
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "recovery_agent")
COLLECTION = "invoices"

if not MONGO_URI:
    print("❌  MONGO_URI not found in .env — aborting.")
    sys.exit(1)


def _date_str(d: date) -> str:
    """Format a date as YYYY-MM-DD string."""
    return d.strftime("%Y-%m-%d")


def _build_invoices() -> list[dict]:
    """
    Generate 15 realistic Indian MSME invoices with dynamic dates.
    All dates are relative to today so the data never goes stale.
    """
    today = date.today()

    # Helper: given days_overdue, compute issueDate and dueDate
    def make_dates(days_overdue: int, payment_terms_days: int = 30):
        due = today - timedelta(days=days_overdue)
        issued = due - timedelta(days=payment_terms_days)
        return _date_str(issued), _date_str(due)

    invoices = []

    # ── 4 × LEGAL (>45 days overdue) ──────────────────────────────────────────
    legal = [
        {
            "company": "Sharma Traders",
            "contact": "Rajesh Sharma",
            "phone": "+91 98765 43210",
            "email": "rajesh@sharmatraders.in",
            "gstin": "27AABCS1429B1Z1",
            "amount": 85000,
            "invoiceNo": "INV-2025-041",
            "channel": "WhatsApp",
            "industry": "Manufacturing",
            "city": "Mumbai",
            "notes": "Owner claims cash flow issues. Legal notice drafted.",
            "days_overdue": 134,
            "reminders": 4,
        },
        {
            "company": "Navi Mumbai Exports",
            "contact": "Suresh Nair",
            "phone": "+91 76543 21098",
            "email": "suresh@nmexports.in",
            "gstin": "27AABCS7777B1Z3",
            "amount": 120000,
            "invoiceNo": "INV-2025-007",
            "channel": "WhatsApp",
            "industry": "Trade",
            "city": "Navi Mumbai",
            "notes": "Legal notice sent via registered post. Awaiting response.",
            "days_overdue": 99,
            "reminders": 4,
        },
        {
            "company": "Indore Steel Solutions",
            "contact": "Manoj Tiwari",
            "phone": "+91 93456 78901",
            "email": "manoj@indoresteel.co.in",
            "gstin": "23AABCI2222B1Z5",
            "amount": 245000,
            "invoiceNo": "INV-2024-098",
            "channel": "Email",
            "industry": "Manufacturing",
            "city": "Indore",
            "notes": "MSME Samadhaan filing initiated. High priority.",
            "days_overdue": 180,
            "reminders": 4,
        },
        {
            "company": "Gurugram Hardware Hub",
            "contact": "Deepak Yadav",
            "phone": "+91 81234 56789",
            "email": "deepak@ghardware.in",
            "gstin": "06AABCG3333B1Z9",
            "amount": 67500,
            "invoiceNo": "INV-2025-022",
            "channel": "WhatsApp",
            "industry": "Retail",
            "city": "Gurugram",
            "notes": "Debtor unresponsive for 3 weeks. Escalated to legal.",
            "days_overdue": 62,
            "reminders": 4,
        },
    ]
    for inv in legal:
        issue, due = make_dates(inv["days_overdue"])
        inv["issueDate"] = issue
        inv["dueDate"] = due
        inv["status"] = "legal"
        inv["recovered"] = False
        inv["daysOverdue"] = inv.pop("days_overdue")
        invoices.append(inv)

    # ── 3 × RECOVERED ────────────────────────────────────────────────────────
    recovered = [
        {
            "company": "Thane IT Solutions",
            "contact": "Vikram Mehta",
            "phone": "+91 88776 65544",
            "email": "vikram@thaneit.in",
            "gstin": "27AABCS1111B1Z6",
            "amount": 67000,
            "invoiceNo": "INV-2024-089",
            "channel": "WhatsApp",
            "industry": "IT",
            "city": "Thane",
            "notes": "Recovered after legal notice sent. Payment via NEFT.",
            "days_overdue": 174,
            "reminders": 4,
        },
        {
            "company": "Nagpur Steel Works",
            "contact": "Ramesh Gupta",
            "phone": "+91 77665 54433",
            "email": "ramesh@nagpursteel.in",
            "gstin": "27AABCS2222B1Z7",
            "amount": 195000,
            "invoiceNo": "INV-2024-055",
            "channel": "WhatsApp",
            "industry": "Manufacturing",
            "city": "Nagpur",
            "notes": "Full payment received after 3-month recovery process.",
            "days_overdue": 210,
            "reminders": 4,
        },
        {
            "company": "Jaipur Textiles Pvt Ltd",
            "contact": "Sunita Mehra",
            "phone": "+91 94567 12345",
            "email": "sunita@jaipurtex.in",
            "gstin": "08AABCJ5555B1Z2",
            "amount": 38000,
            "invoiceNo": "INV-2025-033",
            "channel": "Email",
            "industry": "Textiles",
            "city": "Jaipur",
            "notes": "Paid after second reminder. Smooth recovery.",
            "days_overdue": 45,
            "reminders": 2,
        },
    ]
    for inv in recovered:
        issue, due = make_dates(inv["days_overdue"])
        inv["issueDate"] = issue
        inv["dueDate"] = due
        inv["status"] = "recovered"
        inv["recovered"] = True
        inv["daysOverdue"] = inv.pop("days_overdue")
        invoices.append(inv)

    # ── 3 × ESCALATED (35–44 days overdue) ────────────────────────────────────
    escalated = [
        {
            "company": "Pune Digital Agency",
            "contact": "Priya Joshi",
            "phone": "+91 87654 32109",
            "email": "priya@punedigital.in",
            "gstin": "27AABCS9999B1Z2",
            "amount": 42000,
            "invoiceNo": "INV-2025-018",
            "channel": "Email",
            "industry": "Services",
            "city": "Pune",
            "notes": "Third reminder sent. Disputes service quality.",
            "days_overdue": 42,
            "reminders": 3,
        },
        {
            "company": "Deccan Pharma Dist.",
            "contact": "Kavita Rao",
            "phone": "+91 66554 43322",
            "email": "kavita@deccanpharma.in",
            "gstin": "36AABCS8888B1Z8",
            "amount": 55000,
            "invoiceNo": "INV-2025-052",
            "channel": "Email",
            "industry": "Pharma",
            "city": "Hyderabad",
            "notes": "Final notice sent. Contact person changed.",
            "days_overdue": 38,
            "reminders": 3,
        },
        {
            "company": "TechNova Solutions",
            "contact": "Arjun Kapoor",
            "phone": "+91 99112 33445",
            "email": "arjun@technova.co.in",
            "gstin": "29AABCT4444B1Z1",
            "amount": 91000,
            "invoiceNo": "INV-2025-061",
            "channel": "WhatsApp",
            "industry": "IT",
            "city": "Bangalore",
            "notes": "CFO promised payment by month-end. Monitoring.",
            "days_overdue": 40,
            "reminders": 3,
        },
    ]
    for inv in escalated:
        issue, due = make_dates(inv["days_overdue"])
        inv["issueDate"] = issue
        inv["dueDate"] = due
        inv["status"] = "escalated"
        inv["recovered"] = False
        inv["daysOverdue"] = inv.pop("days_overdue")
        invoices.append(inv)

    # ── 3 × REMINDED (15–34 days overdue) ─────────────────────────────────────
    reminded = [
        {
            "company": "Koregaon Textiles",
            "contact": "Anita Patil",
            "phone": "+91 65432 10987",
            "email": "anita@koregtex.in",
            "gstin": "27AABCS5555B1Z4",
            "amount": 28500,
            "invoiceNo": "INV-2025-031",
            "channel": "WhatsApp",
            "industry": "Textiles",
            "city": "Pune",
            "notes": "Second WhatsApp sent. Read but no reply yet.",
            "days_overdue": 28,
            "reminders": 2,
        },
        {
            "company": "Chennai Auto Parts",
            "contact": "Karthik Raman",
            "phone": "+91 98234 56710",
            "email": "karthik@chennaiap.co.in",
            "gstin": "33AABCC6666B1Z3",
            "amount": 34500,
            "invoiceNo": "INV-2025-068",
            "channel": "WhatsApp",
            "industry": "Automotive",
            "city": "Chennai",
            "notes": "Acknowledged but asked for 2-week extension.",
            "days_overdue": 22,
            "reminders": 2,
        },
        {
            "company": "Lucknow Sweets Co.",
            "contact": "Neha Srivastava",
            "phone": "+91 85678 90123",
            "email": "neha@lucknowsweets.in",
            "gstin": "09AABCL7777B1Z6",
            "amount": 18000,
            "invoiceNo": "INV-2025-075",
            "channel": "Email",
            "industry": "F&B",
            "city": "Lucknow",
            "notes": "",
            "days_overdue": 18,
            "reminders": 2,
        },
    ]
    for inv in reminded:
        issue, due = make_dates(inv["days_overdue"])
        inv["issueDate"] = issue
        inv["dueDate"] = due
        inv["status"] = "reminded"
        inv["recovered"] = False
        inv["daysOverdue"] = inv.pop("days_overdue")
        invoices.append(inv)

    # ── 2 × SENT (<15 days overdue) ───────────────────────────────────────────
    sent = [
        {
            "company": "Bandra Café Co.",
            "contact": "Farhan Sheikh",
            "phone": "+91 99887 76655",
            "email": "farhan@bandracafe.in",
            "gstin": "27AABCS3333B1Z5",
            "amount": 15000,
            "invoiceNo": "INV-2025-044",
            "channel": "Email",
            "industry": "F&B",
            "city": "Mumbai",
            "notes": "First reminder sent. New client.",
            "days_overdue": 10,
            "reminders": 1,
        },
        {
            "company": "Ahmedabad Packaging",
            "contact": "Pooja Shah",
            "phone": "+91 70123 45678",
            "email": "pooja@ahmpkg.in",
            "gstin": "24AABCA8888B1Z4",
            "amount": 22000,
            "invoiceNo": "INV-2025-079",
            "channel": "WhatsApp",
            "industry": "Manufacturing",
            "city": "Ahmedabad",
            "notes": "",
            "days_overdue": 7,
            "reminders": 1,
        },
    ]
    for inv in sent:
        issue, due = make_dates(inv["days_overdue"])
        inv["issueDate"] = issue
        inv["dueDate"] = due
        inv["status"] = "sent"
        inv["recovered"] = False
        inv["daysOverdue"] = inv.pop("days_overdue")
        invoices.append(inv)

    return invoices


async def seed():
    """Connect to MongoDB, drop the old collection, and insert fresh data."""
    print(f"🔌  Connecting to MongoDB → {DB_NAME}...")
    client = AsyncIOMotorClient(MONGO_URI)

    # Verify connectivity
    await client.admin.command("ping")
    print("✅  Connected successfully.")

    db = client[DB_NAME]
    col = db[COLLECTION]

    # Drop the old collection
    await col.drop()
    print(f"🗑   Dropped existing '{COLLECTION}' collection.")

    # Generate invoices
    invoices = _build_invoices()
    result = await col.insert_many(invoices)
    print(f"📦  Inserted {len(result.inserted_ids)} invoices.")

    # Summary
    by_status = {}
    for inv in invoices:
        s = inv["status"]
        by_status[s] = by_status.get(s, 0) + 1

    print("\n── Summary ─────────────────────────")
    for status, count in sorted(by_status.items()):
        print(f"   {status:<12} → {count} invoices")

    total_outstanding = sum(i["amount"] for i in invoices if not i["recovered"])
    total_recovered = sum(i["amount"] for i in invoices if i["recovered"])
    print(f"\n   💰 Total outstanding : ₹{total_outstanding:,.0f}")
    print(f"   ✅ Total recovered   : ₹{total_recovered:,.0f}")
    print(f"   📊 Recovery rate     : {total_recovered / (total_outstanding + total_recovered) * 100:.1f}%")
    print("\n🎉  Seed complete! Start the server with:  uvicorn app.main:app --reload")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
