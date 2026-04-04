import asyncio
import httpx
import uuid

API_BASE_URL = "http://localhost:8000/api"

MOCK_INVOICES = [
    {
        "company": "Tech Solutions Ltd",
        "contact": "Rahul Sharma",
        "phone": "+91 9876543210",
        "email": "rahul@techsolutions.com",
        "amount": 50000.0,
        "invoiceNo": "INV-1001",
        "dueDate": "2026-01-15",
        "daysOverdue": 80,
        "status": "escalated",
        "industry": "IT Services",
        "city": "Bengaluru"
    },
    {
        "company": "Global Logistics",
        "contact": "Anjali Gupta",
        "phone": "+91 9123456789",
        "email": "anjali@globallogistics.in",
        "amount": 120000.0,
        "invoiceNo": "INV-1002",
        "dueDate": "2026-03-01",
        "daysOverdue": 34,
        "status": "legal",
        "industry": "Logistics",
        "city": "Mumbai"
    },
    {
        "company": "Green Energy Inc",
        "contact": "Vikrant Singh",
        "phone": "+91 9988776655",
        "email": "vsingh@greenenergy.co.in",
        "amount": 75000.0,
        "invoiceNo": "INV-1003",
        "dueDate": "2026-02-20",
        "daysOverdue": 45,
        "status": "reminded",
        "industry": "Energy",
        "city": "Delhi"
    },
    {
        "company": "Sunrise Retails",
        "contact": "Pooja Verma",
        "phone": "+91 9876509876",
        "email": "pooja.v@sunriseretails.com",
        "amount": 15000.0,
        "invoiceNo": "INV-1004",
        "dueDate": "2026-03-25",
        "daysOverdue": 10,
        "status": "sent",
        "industry": "Retail",
        "city": "Pune"
    },
    {
        "company": "Apex Manufacturing",
        "contact": "Karan Malhotra",
        "phone": "+91 9012345678",
        "email": "karan@apexmf.in",
        "amount": 250000.0,
        "invoiceNo": "INV-1005",
        "dueDate": "2025-11-10",
        "daysOverdue": 145,
        "status": "escalated",
        "industry": "Manufacturing",
        "city": "Chennai"
    }
]

async def run_tests():
    # Setup dynamic test credentials so tests always run isolated
    test_user = f"test_crud_{uuid.uuid4().hex[:6]}@example.com"
    test_pass = "securepass123"
    
    async with httpx.AsyncClient() as client:
        print("=== STAGE 1: Authentication Setup ===")
        # Register User
        print(f"Registering dynamic test user: {test_user}...")
        resp = await client.post(f"{API_BASE_URL}/auth/register", json={
            "business_name": "Test CRUD Validation Corp",
            "email": test_user,
            "password": test_pass
        })
        if resp.status_code != 201:
            print(f"FAILED to register test user: {resp.text}")
            return
        
        # Login User
        print("Logging in...")
        resp = await client.post(f"{API_BASE_URL}/auth/login", data={
            "username": test_user,
            "password": test_pass
        })
        if resp.status_code != 200:
            print(f"FAILED to login: {resp.text}")
            return
        
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("SUCCESS: Authenticated.\n")

        print("=== STAGE 2: CRUD Tests ===")
        
        # ADD / CREATE
        print("Task: Add (Create 5 mock invoices)")
        inserted_ids = []
        for inv in MOCK_INVOICES:
            resp = await client.post(f"{API_BASE_URL}/invoices", json=inv, headers=headers)
            if resp.status_code != 201:
                print(f"FAILED to insert invoice {inv['invoiceNo']}: {resp.text}")
                return
            data = resp.json()
            inserted_ids.append(data["id"])
        print(f"SUCCESS: Created 5 invoices. IDs: {inserted_ids}\n")

        # READ
        print("Task: Read (Fetch invoices)")
        resp = await client.get(f"{API_BASE_URL}/invoices", headers=headers)
        if resp.status_code != 200:
            print(f"FAILED to read invoices: {resp.text}")
            return
        fetched = resp.json()
        if len(fetched) == 5:
            print("SUCCESS: Fetched exactly 5 invoices.\n")
        else:
            print(f"FAILED: Expected 5 invoices, got {len(fetched)}.\n")
            return

        # UPDATE
        first_id = inserted_ids[0]
        print(f"Task: Update (Mark invoice {first_id} as recovered)")
        resp = await client.patch(f"{API_BASE_URL}/invoices/{first_id}", json={
            "status": "recovered",
            "recovered": True
        }, headers=headers)
        
        if resp.status_code != 200:
            print(f"FAILED to update invoice: {resp.text}")
            return
        
        updated_data = resp.json()
        if updated_data["status"] == "recovered" and updated_data["recovered"] is True:
            print("SUCCESS: Invoice updated to 'recovered' correctly.\n")
        else:
            print("FAILED: Invoice update response didn't match expected fields.\n")
            return
            
        # DELETE
        last_id = inserted_ids[-1]
        print(f"Task: Delete (Remove invoice {last_id})")
        resp = await client.delete(f"{API_BASE_URL}/invoices/{last_id}", headers=headers)
        if resp.status_code != 204:
            print(f"FAILED to delete invoice: {resp.text}")
            return
            
        # Verify deletion
        resp = await client.get(f"{API_BASE_URL}/invoices", headers=headers)
        if resp.status_code == 200 and len(resp.json()) == 4:
            print("SUCCESS: Invoice deleted successfully and list now has 4 items.\n")
        else:
            print("FAILED: Integrity check after deletion failed.\n")
            return
            
        print("=== ALL CRUD VALIDATION TESTS PASSED ===")

if __name__ == "__main__":
    asyncio.run(run_tests())
