import httpx
import json
import time

def simulate_whatsapp_message():
    print("=======================================================")
    print("  RecoverAI - Local WhatsApp Simulator")
    print("=======================================================\n")
    print("Since Meta is blocking your account creation, we can bypass")
    print("them entirely for testing! This script pretends to be the")
    print("Meta server and sends an inbound message directly to your AI.\n")
    
    phone = input("Enter the debtor's phone number (from your Invoice list): ").strip()
    name = input("Enter the debtor's name: ").strip()
    message = input("Enter the message they are sending (e.g., 'kal payment bhej dunga'): ").strip()
    
    # Strip spaces from phone just like WhatsApp does
    phone = "".join(c for c in phone if c.isdigit() or c == "+")
    
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "1234567890",
                                "phone_number_id": "TEST_PHONE_ID"
                            },
                            "contacts": [
                                {
                                    "profile": {
                                        "name": name
                                    },
                                    "wa_id": phone
                                }
                            ],
                            "messages": [
                                {
                                    "from": phone,
                                    "id": f"wamid.simulated.{int(time.time())}",
                                    "timestamp": str(int(time.time())),
                                    "text": {
                                        "body": message
                                    },
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    print("\nSending payload to your local AI Agent webhook...")
    try:
        # Send to the local FastAPI server directly!
        response = httpx.post("http://127.0.0.1:8000/api/webhooks/whatsapp", json=payload)
        
        if response.status_code == 200:
            print("✅ Success! The AI Agent has received and processed the message.")
            print("Check your terminal running the FastAPI server to see the NLP Agent classifying the intent!")
            print("You can also refresh your dashboard to see the logged interaction.")
        else:
            print(f"❌ Error: Backend returned {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Failed to connect to backend: {e}")
        print("Make sure your FastAPI server is running! (.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000)")

if __name__ == "__main__":
    simulate_whatsapp_message()
