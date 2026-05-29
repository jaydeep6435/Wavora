import os
import glob
import logging
import yt_dlp
import cloudinary
import cloudinary.uploader
import random
import httpx
import re
from core.config import settings
from services.queue_manager import push_queue, pop_queue, is_album_downloaded, mark_album_downloaded
from db.session import SessionLocal
from models.album import Album
from models.song import Song

logger = logging.getLogger("wavora.youtube_sync")

def _init_cloudinary():
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY:
        raise ValueError("Cloudinary credentials missing")
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True
    )

def populate_album_queue():
    """
    Runs at midnight. Searches iTunes for an Album, creates it in DB, and queues its tracks.
    """
    logger.info("Starting Daily Album Selection task...")
    
    # Using search terms that target high-quality, official Bollywood movie soundtracks
    # like the ones shown in the user's iTunes screenshot (e.g. Kabir Singh, ANIMAL)
    indian_regions = [
        "bollywood original motion picture soundtrack",
        "hindi original motion picture soundtrack",
        "tamil original motion picture soundtrack",
        "telugu original motion picture soundtrack",
        "punjabi hit movie soundtrack",
        "indian original motion picture soundtrack"
    ]
    selected_region = random.choice(indian_regions)
    
    # Search iTunes for an ALBUM
    itunes_url = f"https://itunes.apple.com/search?term={selected_region}&media=music&entity=album&limit=30"
    logger.info(f"Querying iTunes for verified Album: {itunes_url}")
    
    response = httpx.get(itunes_url)
    data = response.json()
    results = data.get("results", [])
    
    if not results:
        logger.error(f"Could not find any albums on iTunes for {selected_region}.")
        return

    # Find an album we haven't downloaded yet (and make sure it's a real playlist/album, not a Single)
    target_album = None
    for album in results:
        collection_id = str(album.get("collectionId"))
        track_count = album.get("trackCount", 0)
        # Only select albums that have more than 3 tracks (no singles)
        if track_count > 3 and not is_album_downloaded(collection_id):
            target_album = album
            break
            
    if not target_album:
        logger.error("All top 30 albums for this region are already downloaded. Skipping.")
        return

    collection_id = str(target_album.get("collectionId"))
    album_title = target_album.get("collectionName")
    album_artist = target_album.get("artistName")
    artwork_url = target_album.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
    
    logger.info(f"Selected Album: {album_title} by {album_artist}")
    
    # Fetch songs in this album
    lookup_url = f"https://itunes.apple.com/lookup?id={collection_id}&entity=song"
    lookup_res = httpx.get(lookup_url)
    lookup_data = lookup_res.json()
    
    songs = [item for item in lookup_data.get("results", []) if item.get("wrapperType") == "track"]
    
    if not songs:
        logger.error("Album has no songs. Skipping.")
        mark_album_downloaded(collection_id)
        return
        
    # Save Album to DB
    db = SessionLocal()
    try:
        # Check if exists just in case
        existing_album = db.query(Album).filter(Album.itunes_id == collection_id).first()
        if not existing_album:
            new_album = Album(
                title=album_title,
                artist=album_artist,
                thumbnail_path=artwork_url,
                itunes_id=collection_id
            )
            db.add(new_album)
            db.commit()
            db.refresh(new_album)
            album_id = new_album.id
        else:
            album_id = existing_album.id
            
        # Queue the songs
        queue_items = []
        for song in songs:
            queue_items.append({
                "title": song.get("trackName"),
                "artist": song.get("artistName"),
                "album_id": album_id,
                "thumbnail_url": artwork_url,
                "duration": song.get("trackTimeMillis", 0) / 1000.0
            })
            
        push_queue(queue_items)
        mark_album_downloaded(collection_id)
        logger.info(f"Queued {len(queue_items)} songs for downloading.")
    except Exception as e:
        logger.error(f"Failed to queue album: {e}")
    finally:
        db.close()


def process_queue_item():
    """
    Runs every 7 minutes. Pops a song from the queue and downloads it.
    """
    item = pop_queue()
    if not item:
        # Nothing in queue
        return
        
    title = item["title"]
    artist = item["artist"]
    album_id = item["album_id"]
    thumbnail_url = item["thumbnail_url"]
    expected_duration = item["duration"]
    
    logger.info(f"Processing queue item: {title} by {artist}")
    
    try:
        _init_cloudinary()
    except Exception as e:
        logger.error(e)
        return

    tmp_dir = "/tmp"
    if os.name == "nt":
        tmp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"))
        os.makedirs(tmp_dir, exist_ok=True)
        
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(tmp_dir, 'yt_sync_%(id)s.%(ext)s'),
        'noplaylist': True,
        'quiet': False
    }
    
    # Clean old temp files
    for f in glob.glob(os.path.join(tmp_dir, "yt_sync_*")):
        try: os.remove(f)
        except: pass

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search top 5 results to find the exact official song
            search_query = f"ytsearch5:{title} {artist} original audio"
            info_dict = ydl.extract_info(search_query, download=False)
            
            target_entry = None
            if 'entries' in info_dict and len(info_dict['entries']) > 0:
                # 1. Look for an exact match (duration within 15 seconds of iTunes duration)
                for entry in info_dict['entries']:
                    if not entry: continue
                    vid_duration = entry.get('duration', 0)
                    if expected_duration > 0 and abs(vid_duration - expected_duration) <= 15:
                        target_entry = entry
                        logger.info(f"Exact duration match found! ({vid_duration}s vs {expected_duration}s)")
                        break
                
                # 2. Fallback: If no exact match, find the first video that is a full song (>= 60 seconds)
                if not target_entry:
                    for entry in info_dict['entries']:
                        if entry and entry.get('duration', 0) >= 60:
                            target_entry = entry
                            logger.info(f"No exact match, falling back to first full video ({entry.get('duration')}s)")
                            break
                            
                # 3. Last resort: Fallback to the very first result if everything was short
                if not target_entry:
                    target_entry = info_dict['entries'][0]
            
            if not target_entry:
                logger.error(f"Could not find track on YouTube: {title}")
                return
                
            track_url = target_entry.get('webpage_url') or target_entry.get('url') or target_entry.get('id')
            ydl.download([track_url])

            downloaded_files = glob.glob(os.path.join(tmp_dir, "yt_sync_*.mp3"))
            if not downloaded_files:
                logger.error("Download finished but no mp3 found.")
                return
                
            expected_filepath = downloaded_files[0]
                
            safe_title = re.sub(r'[^a-zA-Z0-9\s]', '', title).strip().replace(' ', '_')
            safe_artist = re.sub(r'[^a-zA-Z0-9\s]', '', artist).strip().replace(' ', '_')
            custom_public_id = f"{safe_title}-{safe_artist}"[:100] + ".mp3"

            logger.info(f"Uploading to Cloudinary as {custom_public_id}...")
            upload_result = cloudinary.uploader.upload_large(
                expected_filepath,
                resource_type="raw",
                folder="songs/",
                public_id=custom_public_id,
                overwrite=True
            )
            
            cloudinary_url = upload_result.get("secure_url")
            
            if os.path.exists(expected_filepath):
                os.remove(expected_filepath)
                
            # Save to Database
            db = SessionLocal()
            try:
                # Check if song exists
                existing_song = db.query(Song).filter(Song.audio_path == cloudinary_url).first()
                if not existing_song:
                    new_song = Song(
                        title=title,
                        artist=artist,
                        audio_path=cloudinary_url,
                        thumbnail_path=thumbnail_url,
                        duration=expected_duration if expected_duration > 0 else 180.0,
                        album_id=album_id
                    )
                    db.add(new_song)
                    db.commit()
                    logger.info(f"Successfully saved {title} to DB under Album ID {album_id}")
                else:
                    # If song already exists (e.g. found by scanner), link it to this album!
                    if existing_song.album_id != album_id:
                        existing_song.album_id = album_id
                        db.commit()
                        logger.info(f"Linked existing song {title} to Album ID {album_id}")
            except Exception as db_e:
                logger.error(f"Database save failed: {db_e}")
            finally:
                db.close()
                
    except Exception as e:
        logger.error(f"Processing failed for {title}: {e}")
        for f in glob.glob(os.path.join(tmp_dir, "yt_sync_*")):
            try: os.remove(f)
            except: pass

def sync_trending_youtube_song():
    """
    Legacy entrypoint for manual forced syncs (e.g. from Postman).
    We will just populate a queue and process one item immediately.
    """
    populate_album_queue()
    process_queue_item()
    return {"success": True, "message": "Triggered album queue and processed 1 track"}
