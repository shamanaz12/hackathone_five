
import requests
import base64
import json

def trigger_real_world_run():
    print("="*60)
    print("RUNNING REAL-WORLD INTEGRATION TEST")
    print("="*60)

    url = "http://localhost:8000/webhooks/gmail"
    
    # Mock Gmail RFC822 email
    raw_email = (
        "From: Alice <alice@example.com>\n"
        "To: support@techcorp.com\n"
        "Subject: Kanban Board Issue\n\n"
        "Hi, my Kanban board is loading very slowly today. Is there an outage?"
    )
    
    # Encode as base64 (matching Pub/Sub format)
    encoded_data = base64.b64encode(raw_email.encode()).decode()
    
    payload = {
        "data": encoded_data,
        "attributes": {
            "emailAddress": "support@techcorp.com",
            "historyId": "99999"
        }
    }

    print(f"\n[1] Sending Mock Gmail Webhook to {url}...")
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Server Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n[2] Agent & MCP Tool Execution Result:")
            print(f" - Ticket ID: {result.get('ticket_id')}")
            print(f" - Status: {result.get('status')}")
            
            print("\n[3] AI Generated Response (sent back to channel):")
            print("-" * 40)
            print(result.get("ai_response"))
            print("-" * 40)
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Failed to connect to server: {e}")

    print("\n" + "="*60)
    print("RUN COMPLETE")
    print("="*60)

if __name__ == "__main__":
    trigger_real_world_run()
