import asyncpg
import asyncio

async def create_db():
    try:
        # Connect to postgres database to create the new one
        conn = await asyncpg.connect(
            host="localhost", port=5432, user="postgres", password="balaj786", database="postgres"
        )
        
        # Check if taskflow exists
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = 'taskflow'")
        if not exists:
            print("Creating database 'taskflow'...")
            # We can't use await conn.execute("CREATE DATABASE taskflow") because it cannot be run inside a transaction block.
            # asyncpg.connect() might start a transaction.
            # We use a separate connection for this.
            await conn.close()
            
            # Use another connection and run with autocommit (which asyncpg does by default if not specified otherwise, but CREATE DATABASE needs to be alone)
            conn = await asyncpg.connect(
                host="localhost", port=5432, user="postgres", password="balaj786", database="postgres"
            )
            await conn.execute('CREATE DATABASE taskflow')
            print("Database 'taskflow' created.")
        else:
            print("Database 'taskflow' already exists.")
            
        await conn.close()
    except Exception as e:
        print(f"Failed to create database: {e}")

asyncio.run(create_db())
