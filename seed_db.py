
import logging
from production.database.session import get_session_factory
from production.database.models import KnowledgeBase, Customer
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

def seed_db():
    session_factory = get_session_factory()
    with session_factory() as session:
        # Delete existing to re-seed clean
        session.query(KnowledgeBase).delete()
        
        print("Seeding Knowledge Base with all required topics...")
        kb_articles = [
            KnowledgeBase(
                topic="password_reset",
                title="How to reset your password",
                overview="Users can reset their password via the login page.",
                content={"steps": ["Go to login", "Click forgot password", "Check email"]},
                keywords=["password", "reset", "login", "forgot", "link", "expired"],
                is_active=True
            ),
            KnowledgeBase(
                topic="create_project",
                title="How to create a new project",
                overview="Log in -> click '+ New Project' (top right) -> fill details -> Create Project.",
                content={"steps": ["Login", "Click + New Project", "Fill details"]},
                keywords=["create", "project", "new", "add"],
                is_active=True
            ),
            KnowledgeBase(
                topic="pricing",
                title="Pricing Tiers",
                overview="We offer Free, Starter ($12/mo), and Professional ($25/mo) plans.",
                content={"tiers": ["Free", "Starter", "Professional"]},
                keywords=["pricing", "tiers", "cost", "plan", "subscription"],
                is_active=True
            ),
             KnowledgeBase(
                topic="kanban_board",
                title="Kanban Board Guide",
                overview="Manage your tasks using our visual Kanban board.",
                content={"columns": ["To Do", "In Progress", "Done"]},
                keywords=["kanban", "board", "tasks", "drag", "drop"],
                is_active=True
            )
        ]
        session.add_all(kb_articles)

        # Ensure test customer exists
        if not session.query(Customer).filter_by(customer_id="CUST-0001").first():
            print("Creating test customer...")
            customer = Customer(
                customer_id="CUST-0001",
                name="Test User",
                email="customer@example.com",
                phone="03161129505",
                tier="gold"
            )
            session.add(customer)
            
        session.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    seed_db()
