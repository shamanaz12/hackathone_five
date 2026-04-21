import asyncio
import sys
import traceback

print("Starting create_all test...", flush=True)

async def main():
    from sqlalchemy import text
    from production.database.session import get_engine, init_db
    from production.database.models import Base
    
    print("Imports OK", flush=True)
    
    # Check tables before
    engine = get_engine()
    async with engine.begin() as conn:
        tables = await conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' ORDER BY tablename
        """))
        table_names = [r[0] for r in tables]
        print(f"Tables before: {len(table_names)} -> {table_names}", flush=True)
    
    # Run init_db
    print("Running init_db...", flush=True)
    await init_db()
    print("init_db done", flush=True)
    
    # Check tables after
    async with engine.begin() as conn:
        tables = await conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' ORDER BY tablename
        """))
        table_names = [r[0] for r in tables]
        print(f"Tables after: {len(table_names)} -> {table_names}", flush=True)

try:
    asyncio.run(main())
    print("Done", flush=True)
except Exception as e:
    traceback.print_exc()
    print(f"Error: {e}", flush=True)
