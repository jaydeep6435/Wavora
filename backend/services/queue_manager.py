import logging
from typing import List, Dict
from db.session import SessionLocal
from models.sync_state import DownloadQueue, DownloadedAlbumTracker, DownloadedSongTracker

logger = logging.getLogger("wavora.queue")

def get_queue() -> List[Dict]:
    """Returns the current pending items in the download queue."""
    db = SessionLocal()
    try:
        queue_items = db.query(DownloadQueue).order_by(DownloadQueue.id.asc()).all()
        return [
            {
                "title": item.title,
                "artist": item.artist,
                "album_id": item.album_id,
                "thumbnail_url": item.thumbnail_url,
                "duration": item.duration
            }
            for item in queue_items
        ]
    except Exception as e:
        logger.error(f"Failed to get queue: {e}")
        return []
    finally:
        db.close()

def push_queue(items: List[Dict]):
    """Pushes a list of items to the download queue."""
    db = SessionLocal()
    try:
        for item in items:
            new_item = DownloadQueue(
                title=item["title"],
                artist=item["artist"],
                album_id=item.get("album_id"),
                thumbnail_url=item.get("thumbnail_url"),
                duration=item.get("duration", 0.0)
            )
            db.add(new_item)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to push to queue: {e}")
    finally:
        db.close()

def pop_queue() -> Dict | None:
    """Pops the oldest item from the download queue and returns it."""
    db = SessionLocal()
    try:
        # Get oldest item
        item = db.query(DownloadQueue).order_by(DownloadQueue.id.asc()).first()
        if not item:
            return None
        
        # Format result before deleting
        result = {
            "title": item.title,
            "artist": item.artist,
            "album_id": item.album_id,
            "thumbnail_url": item.thumbnail_url,
            "duration": item.duration
        }
        
        db.delete(item)
        db.commit()
        return result
    except Exception as e:
        logger.error(f"Failed to pop queue: {e}")
        return None
    finally:
        db.close()

def is_album_downloaded(collection_id: str) -> bool:
    """Checks if an album collection_id has already been processed."""
    db = SessionLocal()
    try:
        record = db.query(DownloadedAlbumTracker).filter(
            DownloadedAlbumTracker.collection_id == str(collection_id)
        ).first()
        return record is not None
    except Exception as e:
        logger.error(f"Failed to check if album is downloaded: {e}")
        return False
    finally:
        db.close()

def mark_album_downloaded(collection_id: str):
    """Marks an album collection_id as processed."""
    db = SessionLocal()
    try:
        if not is_album_downloaded(collection_id):
            record = DownloadedAlbumTracker(collection_id=str(collection_id))
            db.add(record)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to mark album as downloaded: {e}")
    finally:
        db.close()

def is_song_downloaded(title: str, artist: str) -> bool:
    """Checks if a song has already been processed."""
    db = SessionLocal()
    key = f"{title.lower()} - {artist.lower()}"
    try:
        record = db.query(DownloadedSongTracker).filter(
            DownloadedSongTracker.key == key
        ).first()
        return record is not None
    except Exception as e:
        logger.error(f"Failed to check if song is downloaded: {e}")
        return False
    finally:
        db.close()

def mark_song_downloaded(title: str, artist: str):
    """Marks a song as processed."""
    db = SessionLocal()
    key = f"{title.lower()} - {artist.lower()}"
    try:
        if not is_song_downloaded(title, artist):
            record = DownloadedSongTracker(key=key)
            db.add(record)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to mark song as downloaded: {e}")
    finally:
        db.close()
