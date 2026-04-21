import asyncio
import sys

print("Starting test...", flush=True)

async def main():
    print("Inside async main...", flush=True)
    from sqlalchemy import text
    from production.database.session import get_engine
    print("Imports OK", flush=True)
    
    engine = get_engine()
    print("Engine created", flush=True)
    
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))
        print(f"SELECT 1 = {result.scalar()}", flush=True)
    
    print("Connection OK", flush=True)

try:
    asyncio.run(main())
    print("Done", flush=True)
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Error: {e}", flush=True)
