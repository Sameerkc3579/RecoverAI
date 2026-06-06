import asyncio
import time
import sys

def print_color(text, color_code):
    print(f"[{color_code}m{text}[0m".replace("[", "\033["))

async def simulate():
    print_color("============================================================", "96")
    print_color("> STARTING EMAIL INGESTION SIMULATOR", "96")
    print_color("============================================================", "96")
    await asyncio.sleep(1)

    print_color("\n[1/4] Connecting to IMAP server...", "93")
    await asyncio.sleep(1.5)
    print_color("[OK] Connected to imap.gmail.com as billing@recoverai.com", "92")
    await asyncio.sleep(0.5)

    print_color("\n[2/4] Scanning Inbox for UNSEEN invoices...", "93")
    await asyncio.sleep(2)
    print_color("[+] Found 1 unread email from 'vendor@acmecorp.com'", "94")
    print_color("    Subject: 'Invoice INV-2026-991 - Payment Due'", "90")
    print_color("    Attachment: 'Acme_Invoice_991.pdf' (142 KB)", "90")
    await asyncio.sleep(1)

    print_color("\n[3/4] Passing PDF to Gemini 2.0 for Data Extraction...", "95")
    await asyncio.sleep(0.5)
    print_color("    Uploading PDF bytes to Gemini...", "90")
    await asyncio.sleep(2.5)
    print_color("[OK] Gemini Extraction Successful!", "92")
    
    extracted_data = {
        "debtor_name": "Acme Corp",
        "amount": 45000.0,
        "due_date": "2026-07-15",
        "invoice_no": "INV-2026-991",
        "email": "vendor@acmecorp.com"
    }
    
    for key, value in extracted_data.items():
        print_color(f"    -> {key}: {value}", "96")
        await asyncio.sleep(0.3)

    print_color("\n[4/4] Inserting into MongoDB...", "93")
    await asyncio.sleep(1)
    print_color("    Checking 'email_ingestion_log' for duplicates...", "90")
    await asyncio.sleep(0.8)
    print_color("[OK] No duplicates found. Inserting new invoice record...", "92")
    await asyncio.sleep(1)
    print_color("[OK] Document inserted with ID: 66a1b2c3d4e5f6a7b8c9d0e1", "92")
    
    print_color("\n[Cleanup] Marking email as READ in Gmail...", "93")
    await asyncio.sleep(1)
    print_color("[OK] Email marked as \\Seen", "92")

    print_color("\n============================================================", "96")
    print_color("[OK] SIMULATION COMPLETE. 1 Invoice processed.", "92")
    print_color("============================================================\n", "96")

if __name__ == "__main__":
    import os
    os.system("")
    asyncio.run(simulate())
