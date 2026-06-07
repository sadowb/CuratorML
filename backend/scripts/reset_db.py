import asyncio
import os
import shutil
import sys
from pathlib import Path

# Add backend to sys.path so we can import app modules
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine

async def reset_database():
    print(f"Connecting to {settings.database_url}...")
    
    async with engine.begin() as conn:
        print("Dropping public schema...")
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        print("Recreating public schema...")
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO postgres;"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
    
    print("Database wiped.")

def reset_storage():
    storage_path = settings.storage_root_path
    print(f"Cleaning storage at {storage_path}...")
    
    if storage_path.exists():
        # Iterate through subdirectories and delete them
        for item in storage_path.iterdir():
            if item.is_dir():
                print(f"Deleting {item.name}...")
                shutil.rmtree(item)
            elif item.name != ".DS_Store" and item.is_file():
                print(f"Deleting file {item.name}...")
                os.remove(item)
    else:
        print("Storage path does not exist, skipping.")

async def run_migrations():
    print("Running migrations (alembic upgrade head)...")
    # We run alembic as a subprocess to keep things simple
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "alembic", "upgrade", "head",
        cwd=str(Path(__file__).resolve().parents[1]),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    if process.returncode == 0:
        print("Migrations successfully applied.")
    else:
        print(f"Error running migrations (exit code {process.returncode}):")
        print(stderr.decode())
        sys.exit(1)

async def main():
    print("WARNING: This will delete ALL data in the database and storage.")
    
    # reset_storage is synchronous
    reset_storage()
    
    # reset_database is async
    await reset_database()
    
    # run migrations
    await run_migrations()
    
    print("\nSUCCESS: All data has been wiped and schema re-initialized.")

if __name__ == "__main__":
    asyncio.run(main())
