
import asyncio
from production.database.session import init_db

if __name__ == "__main__":
    print("Initializating Local SQLite Database...")
    init_db()
    print("Database 'taskflow.db' created successfully with all tables.")
