"""End-to-end test: Create a ticket via POST /api/tickets and verify DB persistence."""
import json
import time
import urllib.request

BASE = "http://localhost:8000"

def wait_for_server(timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = urllib.request.urlopen(f"{BASE}/health")
            if r.status == 200:
                print("Server is up!", flush=True)
                return True
        except Exception:
            pass
        time.sleep(1)
    print("Server not ready", flush=True)
    return False

def test_create_ticket():
    payload = json.dumps({
        "customer_name": "Shama Naz",
        "email": "shama@test.com",
        "channel": "web_form",
        "subject": "Cannot reset my password",
        "message": "I've been trying to reset my password for the last hour. The reset link keeps saying it's expired even though I just requested it. This is really frustrating!",
        "category": "password_reset",
        "priority": "P3"
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE}/api/tickets",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req)
        print(f"Status: {resp.status}", flush=True)
        body = json.loads(resp.read())
        print(json.dumps(body, indent=2), flush=True)
        return body
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}", flush=True)
        print(e.read().decode(), flush=True)
        return None

def test_get_ticket(ticket_id):
    try:
        resp = urllib.request.urlopen(f"{BASE}/api/tickets/{ticket_id}")
        body = json.loads(resp.read())
        print(f"\nGET /api/tickets/{ticket_id}:", flush=True)
        print(json.dumps(body, indent=2), flush=True)
    except urllib.error.HTTPError as e:
        print(f"GET ticket error: {e.code}", flush=True)
        print(e.read().decode(), flush=True)

def test_get_customer(email):
    try:
        resp = urllib.request.urlopen(f"{BASE}/api/customers?email={email}")
        body = json.loads(resp.read())
        print(f"\nGET /api/customers?email={email}:", flush=True)
        print(json.dumps(body, indent=2), flush=True)
    except urllib.error.HTTPError as e:
        print(f"GET customer error: {e.code}", flush=True)
        print(e.read().decode(), flush=True)

if __name__ == "__main__":
    print("=" * 60)
    print("E2E Test: Ticket Creation with Real PostgreSQL")
    print("=" * 60)

    if not wait_for_server():
        exit(1)

    print("\n--- POST /api/tickets ---", flush=True)
    result = test_create_ticket()

    if result and result.get("ticket_id"):
        ticket_id = result["ticket_id"]
        print(f"\n--- GET /api/tickets/{ticket_id} ---", flush=True)
        test_get_ticket(ticket_id)

        print(f"\n--- GET /api/customers ---", flush=True)
        test_get_customer("shama@test.com")

    print("\n" + "=" * 60)
    print("Tests complete", flush=True)
