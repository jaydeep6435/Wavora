import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.logging_config import setup_logging
from core.config import settings
import logging

setup_logging(settings.ENVIRONMENT)
logger = logging.getLogger("test_db")

def test_db_and_sync():
    from db.session import engine
    from db.base import Base
    
    # 1. Create tables properly
    logger.info("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    from services.youtube_sync import populate_album_queue, process_queue_item
    from services.queue_manager import get_queue
    
    logger.info("1. Populating Queue...")
    populate_album_queue()
    
    queue = get_queue()
    logger.info(f"2. Queue has {len(queue)} items")
    if len(queue) > 0:
        logger.info(f"First item: {queue[0]}")
        
    logger.info("3. Processing 1 item...")
    process_queue_item()
    
    queue_after = get_queue()
    logger.info(f"4. Queue has {len(queue_after)} items after processing")

if __name__ == "__main__":
    test_db_and_sync()
