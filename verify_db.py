import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from production.database.session import get_session_factory
from production.database.models import Ticket

def verify():
    print("Verifying database state...")
    factory = get_session_factory()
    with factory() as session:
        # Check Tickets
        tickets = session.query(Ticket).order_by(Ticket.created_at.desc()).limit(5).all()
        print(f"\n--- Recent Tickets ({len(tickets)}) ---")
        if not tickets:
            print("No tickets found.")
        for t in tickets:
            print(f"[{t.ticket_id}] {t.subject or 'No Subject'} - Status: {t.status}, Channel: {t.channel}")
            print(f"    Message: {t.message[:50]}...")

        # Check Knowledge Base
        from production.database.models import KnowledgeBase
        kb_count = session.query(KnowledgeBase).count()
        print(f"\n--- Knowledge Base ({kb_count} articles) ---")
        kb_items = session.query(KnowledgeBase).limit(3).all()
        for kb in kb_items:
            print(f"- {kb.topic}: {kb.title}")

        # Check Customers
        from production.database.models import Customer
        cust_count = session.query(Customer).count()
        print(f"\n--- Customers ({cust_count}) ---")
        customers = session.query(Customer).limit(3).all()
        for c in customers:
            print(f"- {c.name} ({c.customer_id}) - Email: {c.email}, Phone: {c.phone}")

if __name__ == "__main__":
    verify()
