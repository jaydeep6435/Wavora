import os
import subprocess
import shutil
import logging
from sqlalchemy.orm import Session
from core.config import settings
from models.song import Song
from supabase import create_client, Client

# Configure logging
logger = logging.getLogger("tuneslice.scanner")
logging.basicConfig(level=logging.INFO)

def get_supabase_client() -> Client:
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def get_audio_duration(file_url: str) -> float:
    """
    Query ffprobe to extract audio file duration in seconds using a remote URL.
    """
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe binary is not installed or not present in system PATH")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_url
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=15.0 # Increased timeout for network request
        )
        duration_str = result.stdout.strip()
        if not duration_str:
            raise ValueError("ffprobe returned empty duration")
        return float(duration_str)
    except Exception as e:
        logger.error(f"Failed to extract duration for {file_url} using ffprobe: {e}")
        raise

def parse_filename(filename: str) -> tuple[str, str]:
    """
    Helper to clean and parse title and artist from filename.
    Matches formats like 'title-artist.mp3' or 'title_artist.mp3'.
    Capitalizes names and strips extensions.
    """
    # Remove extension
    name_no_ext, _ = os.path.splitext(filename)
    
    title = ""
    artist = ""

    # Split by hyphen first
    if "-" in name_no_ext:
        parts = name_no_ext.split("-", 1)
        title = parts[0].replace("_", " ").strip()
        artist = parts[1].replace("_", " ").strip()
    # If no hyphen, look for underscore splitting title and artist
    elif "_" in name_no_ext:
        parts = name_no_ext.split("_", 1)
        title = parts[0].strip()
        artist = parts[1].strip()
    else:
        title = name_no_ext.strip()
        artist = "Unknown Artist"

    # Title case names
    title = title.title()
    artist = artist.title()

    return title, artist

async def sync_songs(db: Session) -> dict:
    """
    Main sync scanner service. Connects to Supabase Storage, processes
    each audio file in the 'songs' bucket, resolves dependencies, and saves details to DB.
    """
    logger.info(f"Connecting to Supabase to scan 'songs' bucket")
    results = {"scanned": 0, "added": 0, "updated": 0, "failed": 0}

    try:
        supabase = get_supabase_client()
        # List all files in the 'songs' bucket
        files_response = supabase.storage.from_("songs").list()
        # Note: supabase-py v2+ returns a list of dictionaries directly
        audio_files = [f["name"] for f in files_response if f["name"].lower().endswith(".mp3")]
    except Exception as e:
        logger.warning(f"Failed to access Supabase songs bucket: {e}. Skipping scan.")
        return results

    if not audio_files:
        logger.info("No audio files found in Supabase 'songs' bucket.")
        return results

    for audio_file in audio_files:
        results["scanned"] += 1
        
        # Get public URL for the song
        try:
            public_url_res = supabase.storage.from_("songs").get_public_url(audio_file)
            # In supabase-py v2, get_public_url returns the string directly
            full_audio_url = public_url_res
        except Exception as e:
            logger.error(f"Could not get public URL for {audio_file}: {e}")
            results["failed"] += 1
            continue

        filename_no_ext, _ = os.path.splitext(audio_file)

        try:
            # 1. Fetch exact duration from ffprobe using the public URL
            duration = get_audio_duration(full_audio_url)

            # 2. Extract song title and artist names
            title, artist = parse_filename(audio_file)

            # 3. Try fetching thumbnail from Spotify
            thumbnail_url = None
            from services.spotify import spotify_service
            logger.info(f"Fetching thumbnail for {title} from Spotify...")
            spotify_url = await spotify_service.search_track_thumbnail(title, artist)
            if spotify_url:
                thumbnail_url = spotify_url # Save the remote URL directly in DB

            # 4. Check if song already exists in the database
            existing_song = db.query(Song).filter(Song.audio_path == full_audio_url).first()

            if existing_song:
                # Update existing song if metadata changed
                changed = False
                if existing_song.title != title:
                    existing_song.title = title
                    changed = True
                if existing_song.artist != artist:
                    existing_song.artist = artist
                    changed = True
                if existing_song.duration != duration:
                    existing_song.duration = duration
                    changed = True
                if existing_song.thumbnail_path != thumbnail_url:
                    existing_song.thumbnail_path = thumbnail_url
                    changed = True
                
                if changed:
                    db.commit()
                    results["updated"] += 1
                    logger.info(f"Updated song metadata: {title} - {artist}")
            else:
                # Add new song entry
                new_song = Song(
                    title=title,
                    artist=artist,
                    audio_path=full_audio_url,
                    thumbnail_path=thumbnail_url,
                    duration=duration
                )
                db.add(new_song)
                db.commit()
                results["added"] += 1
                logger.info(f"Registered new song: {title} - {artist} ({duration:.2f}s)")

        except Exception as e:
            logger.error(f"Error processing audio file {audio_file}: {e}")
            results["failed"] += 1
            db.rollback()

    logger.info(f"Sync complete. Scanned: {results['scanned']}, Added: {results['added']}, Updated: {results['updated']}, Failed: {results['failed']}")
    return results
