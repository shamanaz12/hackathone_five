import asyncio
import httpx
import json

async def test_whatsapp_webhook():
    url = "http://localhost:8000/webhooks/whatsapp"
    
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550000000",
                                "phone_number_id": "123456789012345"
                            },
                            "contacts": [
                                {
                                    "profile": {
                                        "name": "Test User"
                                    },
                                    "wa_id": "1234567890"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "1234567890",
                                    "id": "wamid.HBgLMTIzNDU2Nzg5MBUCABIYFEYzOUI0RTU2N0E4OTAxMjM0NQA=",
                                    "timestamp": "1670000000",
                                    "text": {
                                        "body": "How do I reset my password?"
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

    print(f"Sending mock WhatsApp webhook to {url}...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_whatsapp_webhook())
