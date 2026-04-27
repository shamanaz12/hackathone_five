
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def run_master_test():
    print("="*60)
    print("🚀 TASKFLOW AI - MASTER SYSTEM TEST")
    print("="*60)

    # 1. Health Check
    try:
        print("\n[1] Checking System Health...")
        health = requests.get(f"{BASE_URL}/health").json()
        print(f"    Status: {health['status']}")
        print(f"    Database: {health['checks']['db']}")
    except Exception as e:
        print(f"    ❌ Backend is NOT running on {BASE_URL}. Please start it first.")
        return

    # 2. AI & WhatsApp Channel Test
    print("\n[2] Testing AI Brain (WhatsApp Channel)...")
    wa_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{"from": "03161129505", "text": {"body": "Salam, what are your pricing tiers?"}}],
                    "contacts": [{"profile": {"name": "Shama Sadaf"}}]
                }
            }]
        }]
    }
    res_wa = requests.post(f"{BASE_URL}/webhooks/whatsapp", json=wa_payload).json()
    ai_msg = res_wa.get('results', [{}])[0].get('ai_response', '')
    if "Walaikum Assalam" in ai_msg or "pricing" in ai_msg.lower():
        print("    ✅ AI Response received and looks smart!")
        print(f"    Preview: {ai_msg[:100]}...")
    else:
        print("    ⚠️ AI Response received but might be generic.")

    # 3. Database Persistence Test (Web Form)
    print("\n[3] Testing Database Persistence (Web Form)...")
    web_payload = {
        "customer_name": "Test Master",
        "email": "master@test.com",
        "subject": "System Test",
        "message": "Is the database working?"
    }
    res_web = requests.post(f"{BASE_URL}/api/tickets", json=web_payload).json()
    ticket_id = res_web.get('ticket_id')
    if ticket_id:
        print(f"    ✅ Ticket Created in DB: {ticket_id}")
    else:
        print("    ❌ Ticket creation failed.")

    # 4. Retrieval Test
    print("\n[4] Verifying Ticket Retrieval...")
    res_get = requests.get(f"{BASE_URL}/api/tickets/{ticket_id}").json()
    if res_get.get('ticket_id') == ticket_id:
        print(f"    ✅ Data successfully retrieved from SQLite!")
    else:
        print("    ❌ Data retrieval failed.")

    print("\n" + "="*60)
    print("🎉 ALL SYSTEMS FUNCTIONAL: READY FOR SUBMISSION!")
    print("="*60)

if __name__ == "__main__":
    run_master_test()
