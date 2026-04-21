
import requests
import json

BASE_URL = "http://localhost:8000"

def test_whatsapp():
    print("\n--- Testing WhatsApp Channel ---")
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "03161129505",
                        "text": { "body": "Hi, I need help with my account" }
                    }],
                    "contacts": [{"profile": {"name": "Test User"}}]
                }
            }]
        }]
    }
    r = requests.post(f"{BASE_URL}/webhooks/whatsapp", json=payload)
    print(f"Status: {r.status_code}")
    print(f"AI Response: {r.json().get('results', [{}])[0].get('ai_response')}")

def test_gmail():
    print("\n--- Testing Gmail Channel ---")
    # Simulating a Pub/Sub message from Google
    payload = {
        "data": "SGVsbG8sIEkgY2FuJ3QgYWNjZXNzIG15IHByb2plY3Q=", # Base64 for "Hello, I can't access my project"
        "attributes": {"email": "customer@example.com"}
    }
    r = requests.post(f"{BASE_URL}/webhooks/gmail", json=payload)
    print(f"Status: {r.status_code}")
    print(f"Processing Result: {r.json().get('status')}")

if __name__ == "__main__":
    try:
        test_whatsapp()
        test_gmail()
    except Exception as e:
        print(f"Error: {e}. Make sure backend is running on port 8000")
