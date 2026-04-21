import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from production.database.session import get_session_factory
from production.database.queries import search_tickets

async def verify():
    print("Verifying tickets in database...")
    factory = get_session_factory()
    async with factory() as db:
        tickets = await search_tickets(db, limit=5)
        print(f"Total tickets found: {len(tickets)}")
        for t in tickets:
            print(f"- {t['ticket_id']}: {t['subject']} (Customer: {t['customer_id']}, Status: {t['status']})")

if __name__ == "__main__":
    asyncio.run(verify())
