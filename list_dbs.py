import asyncpg
import asyncio

async def test():
    try:
        conn = await asyncpg.connect(
            host="localhost", port=5432, user="postgres", password="balaj786", database="postgres"
        )
        dbs = await conn.fetch("SELECT datname FROM pg_database WHERE datistemplate = false;")
        print("Databases:")
        for db in dbs:
            print(f"  - {db['datname']}")
        await conn.close()
    except Exception as e:
        print(f"Failed to list databases: {e}")

asyncio.run(test())
