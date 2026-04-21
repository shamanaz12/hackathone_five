
import asyncio
import os
from production.agent.customer_success_agent import AgentPipeline
from dotenv import load_dotenv

load_dotenv()

async def test_agent():
    print("--- Testing Agent with Greeting ---")
    pipeline = AgentPipeline(channel="whatsapp")
    result = await pipeline.process_inquiry(
        customer_name="Test User",
        message="Salam! Kaise hain aap?",
        phone="1234567890"
    )
    print(f"Response: {result.get('response')}")
    print(f"Steps: {list(result.get('steps', {}).keys())}")

    print("\n--- Testing Agent with KB Query ---")
    result = await pipeline.process_inquiry(
        customer_name="Test User",
        message="How do I reset my password?",
        phone="1234567890"
    )
    print(f"Response: {result.get('response')}")
    print(f"Steps: {list(result.get('steps', {}).keys())}")

    print("\n--- Testing Agent with Out-of-Scope Query ---")
    result = await pipeline.process_inquiry(
        customer_name="Test User",
        message="Aaj ka musam kaisa hai?",
        phone="1234567890"
    )
    print(f"Response: {result.get('response')}")
    print(f"Steps: {list(result.get('steps', {}).keys())}")

if __name__ == "__main__":
    asyncio.run(test_agent())
