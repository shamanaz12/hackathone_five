import asyncpg
import asyncio
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

async def test():
    try:
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="balaj786",
            database="taskflow"
        )
        version = await conn.fetchval("SELECT version();")
        tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public';")
        print("[OK] DB CONNECTED!")
        print(f"   PostgreSQL: {version[:30]}...")
        print(f"   Tables: {len(tables)}")
        for t in tables:
            print(f"     - {t['tablename']}")
        await conn.close()
    except Exception as e:
        print(f"[ERROR] DB CONNECTION FAILED: {e}")

asyncio.run(test())
