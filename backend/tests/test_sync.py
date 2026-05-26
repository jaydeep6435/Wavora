import asyncio
import logging
import os
import sys

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.session import SessionLocal
from services.song_scanner import sync_songs

logging.basicConfig(level=logging.DEBUG)

async def main():
    db = SessionLocal()
    try:
        results = await sync_songs(db)
        print("SYNC RESULTS:", results)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
