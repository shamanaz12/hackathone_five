
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
_project_root = str(Path(__file__).resolve().parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Setup minimal logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("Demonstration")

from production.agent.customer_success_agent import AgentPipeline
from production.agent.tools import _ticket_store, _customer_store

async def demonstrate_gmail_integration():
    print("\n" + "="*60)
    print("DEMO 1: GMAIL INTEGRATION")
    print("="*60)
    
    pipeline = AgentPipeline(channel="email")
    
    # Simulating data that would come from GmailHandler.process_webhook
    customer_name = "John Doe"
    email = "john@example.com"
    subject = "Help with password reset"
    message = "I forgot my password and the link I received has already expired. Can you help?"
    
    print(f"Incoming Email from: {customer_name} ({email})")
    print(f"Subject: {subject}")
    print(f"Message: {message}\n")
    
    print("--- Processing via AgentPipeline ---")
    result = await pipeline.process_inquiry(
        customer_name=customer_name,
        message=message,
        email=email,
        subject=subject
    )
    
    print("\n--- Pipeline Steps Taken (MCP Tools Called) ---")
    for step_name, step_result in result.get("steps", {}).items():
        print(f"Tool: {step_name}")
        # print(f"Result: {json.dumps(step_result, indent=2)[:200]}...")
    
    print(f"\nCreated Ticket ID: {result.get('ticket_id')}")
    print(f"Sentiment Detected: {result.get('steps', {}).get('sentiment', {}).get('label')}")
    
    print("\n--- Final Response to be sent via GmailHandler ---")
    print("-" * 40)
    print(result.get("response"))
    print("-" * 40)

async def demonstrate_whatsapp_integration():
    print("\n" + "="*60)
    print("DEMO 2: WHATSAPP INTEGRATION")
    print("="*60)
    
    pipeline = AgentPipeline(channel="whatsapp")
    
    # Simulating data that would come from WhatsAppHandler.process_webhook
    customer_name = "Jane Smith"
    phone = "+1234567890"
    message = "Hi, how much does the Starter plan cost per month?"
    
    print(f"Incoming WhatsApp from: {customer_name} ({phone})")
    print(f"Message: {message}\n")
    
    print("--- Processing via AgentPipeline ---")
    result = await pipeline.process_inquiry(
        customer_name=customer_name,
        message=message,
        phone=phone
    )
    
    print("\n--- Pipeline Steps Taken (MCP Tools Called) ---")
    for step_name, step_result in result.get("steps", {}).items():
        print(f"Tool: {step_name}")
    
    print(f"\nCreated Ticket ID: {result.get('ticket_id')}")
    print(f"Sentiment Detected: {result.get('steps', {}).get('sentiment', {}).get('label')}")
    
    print("\n--- Final Response to be sent via WhatsAppHandler ---")
    print("-" * 40)
    print(result.get("response"))
    print("-" * 40)

async def main():
    print("Starting TaskFlow Integration Demonstration...")
    print("Note: Running in Mock/Rule-based mode (No OpenAI Key set)")
    
    await demonstrate_gmail_integration()
    await demonstrate_whatsapp_integration()
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
