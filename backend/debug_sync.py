import asyncio
import os
import sys

# Add the current directory to sys.path so we can import backend modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.session import SessionLocal
from services.song_scanner import sync_songs
from core.logging_config import setup_logging
import logging

setup_logging("development")
logger = logging.getLogger("debug_sync")

async def debug_scan():
    logger.info("Connecting to Database...")
    db = SessionLocal()
    try:
        from models.album import Album
        from models.song import Song
        songs = db.query(Song).all()
        logger.info(f"Currently in Database: {len(songs)} songs")
        for s in songs:
            logger.info(f" - DB: {s.id} | {s.title} | {s.audio_path.split('/')[-1]}")
            
        logger.info("\n--- Starting Deep Scan ---")
        results = await sync_songs(db)
        
        logger.info("\n--- Scan Results ---")
        logger.info(results)
        
        logger.info("\n--- After Scan Database ---")
        songs_after = db.query(Song).all()
        logger.info(f"Currently in Database: {len(songs_after)} songs")
        for s in songs_after:
            logger.info(f" - DB: {s.id} | {s.title} | {s.audio_path.split('/')[-1]}")
            
    except Exception as e:
        logger.error(f"Debug script crashed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(debug_scan())
