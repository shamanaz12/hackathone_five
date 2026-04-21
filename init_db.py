"""
TaskFlow AI Support Agent — Database Initialization Script
CRM Digital FTE Factory Final Hackathon 5

Usage:
    python init_db.py

This script:
1. Creates all database tables via SQLAlchemy
2. Runs schema.sql for enums, triggers, views, and seed data
3. Verifies the setup
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from production.database.session import init_db, get_engine, close_db
from production.config.settings import get_settings

settings = get_settings()


async def main():
    print("=" * 70)
    print("TaskFlow AI Support Agent — Database Initialization")
    print("=" * 70)
    print(f"\nDatabase: {settings.postgres_db}")
    print(f"Host: {settings.postgres_host}:{settings.postgres_port}")
    print(f"User: {settings.postgres_user}")
    
    try:
        print("\n[1/2] Creating database tables via SQLAlchemy...")
        await init_db()
        print("  ✓ Tables created successfully")
        
        print("\n[2/2] Verifying setup...")
        engine = get_engine()
        async with engine.connect() as conn:
            from sqlalchemy import text
            result = await conn.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
            ))
            tables = [row[0] for row in result.fetchall()]
            print(f"  ✓ Found {len(tables)} tables:")
            for t in tables:
                print(f"    - {t}")
        
        await close_db()
        
        print("\n" + "=" * 70)
        print("✓ Database initialization complete!")
        print("=" * 70)
        print(f"\nConnection string: {settings.database_url}")
        print("\nNext steps:")
        print("  1. Start server: python -m uvicorn production.api.main:app --reload --port 8000")
        print("  2. Open API docs: http://localhost:8000/api/docs")
        print("  3. Test health: curl http://localhost:8000/health")
        print("  4. Create ticket: curl -X POST http://localhost:8000/api/tickets -H 'Content-Type: application/json' -d '{\"customer_name\":\"Test User\",\"email\":\"test@example.com\",\"subject\":\"Password reset\",\"message\":\"I forgot my password\"}'")
        
    except Exception as e:
        print(f"\n✗ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
