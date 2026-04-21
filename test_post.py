import requests
import json

url = "http://localhost:8000/api/tickets"
payload = {
    "customer_name": "Sarah Johnson",
    "email": "sarah@startup.com",
    "subject": "Can't reset password",
    "message": "I forgot my password and the reset link says expired even though I just requested it!"
}
headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    print(f"Status Code: {response.status_code}")
    print("Response Body:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
