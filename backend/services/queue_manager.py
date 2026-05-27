import os
import json
import logging
from typing import List, Dict

logger = logging.getLogger("wavora.queue")

QUEUE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "sync_state.json")

def _load_state() -> dict:
    if not os.path.exists(QUEUE_FILE):
        return {
            "downloaded_albums": [],  # List of iTunes collectionId strings
            "downloaded_songs": [],   # List of string "Title - Artist"
            "queue": []               # List of dicts: {"title": "", "artist": "", "album_id": int}
        }
    try:
        with open(QUEUE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load queue state: {e}")
        return {"downloaded_albums": [], "downloaded_songs": [], "queue": []}

def _save_state(state: dict):
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    try:
        with open(QUEUE_FILE, "w") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save queue state: {e}")

def get_queue() -> List[Dict]:
    state = _load_state()
    return state.get("queue", [])

def push_queue(items: List[Dict]):
    state = _load_state()
    queue = state.get("queue", [])
    queue.extend(items)
    state["queue"] = queue
    _save_state(state)

def pop_queue() -> Dict | None:
    state = _load_state()
    queue = state.get("queue", [])
    if not queue:
        return None
    item = queue.pop(0)
    state["queue"] = queue
    _save_state(state)
    return item

def is_album_downloaded(collection_id: str) -> bool:
    state = _load_state()
    return str(collection_id) in state.get("downloaded_albums", [])

def mark_album_downloaded(collection_id: str):
    state = _load_state()
    albums = state.get("downloaded_albums", [])
    if str(collection_id) not in albums:
        albums.append(str(collection_id))
    state["downloaded_albums"] = albums
    _save_state(state)

def is_song_downloaded(title: str, artist: str) -> bool:
    state = _load_state()
    key = f"{title.lower()} - {artist.lower()}"
    return key in state.get("downloaded_songs", [])

def mark_song_downloaded(title: str, artist: str):
    state = _load_state()
    songs = state.get("downloaded_songs", [])
    key = f"{title.lower()} - {artist.lower()}"
    if key not in songs:
        songs.append(key)
    state["downloaded_songs"] = songs
    _save_state(state)
