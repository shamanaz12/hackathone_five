
import requests
import json

BASE_URL = "http://localhost:8000"

def send_whatsapp_message(text, name="User"):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "03161129505",
                        "id": "msg-12345",
                        "timestamp": "1714123456",
                        "type": "text",
                        "text": { "body": text }
                    }],
                    "contacts": [{"profile": {"name": name}}]
                }
            }]
        }]
    }
    r = requests.post(f"{BASE_URL}/webhooks/whatsapp", json=payload)
    return r.json()

if __name__ == "__main__":
    print("\n[1] Testing: 'Salam'")
    res1 = send_whatsapp_message("Salam")
    print(f"AI Response: {res1.get('results', [{}])[0].get('ai_response')}")

    print("\n[2] Testing: 'What is AI?'")
    res2 = send_whatsapp_message("What is AI?")
    print(f"AI Response: {res2.get('results', [{}])[0].get('ai_response')}")
