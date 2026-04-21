import asyncio
import asyncpg

async def test():
    try:
        conn = await asyncpg.connect('postgresql://taskflow:taskflow@localhost:5432/taskflow_support')
        val = await conn.fetchval('SELECT 1')
        print(f"DB OK — SELECT 1 = {val}")
        
        # Check if tables exist
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename
        """)
        print(f"Tables found: {len(tables)}")
        for t in tables:
            print(f"  - {t['tablename']}")
        
        await conn.close()
    except Exception as e:
        print(f"DB connection failed: {e}")

asyncio.run(test())
