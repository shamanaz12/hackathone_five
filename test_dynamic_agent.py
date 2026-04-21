import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path
_project_root = str(Path(__file__).resolve().parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from production.agent.customer_success_agent import AgentPipeline

async def test_agent():
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Dynamic Agent Pipeline...")
    pipeline = AgentPipeline(channel="whatsapp")
    
    # Simulate a pricing inquiry
    result = await pipeline.process_inquiry(
        customer_name="John Doe",
        message="What are your pricing plans? I'm interested in the Professional tier.",
        phone="1234567890"
    )
    
    print("\n--- Result ---")
    print(f"Status: {result.get('status')}")
    print(f"Response: {result.get('response')}")
    print("\nSteps taken:")
    for step, val in result.get("steps", {}).items():
        print(f"- {step}")

if __name__ == "__main__":
    asyncio.run(test_agent())
