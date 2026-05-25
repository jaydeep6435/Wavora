import os
import subprocess
import shutil
import logging
from sqlalchemy.orm import Session
from core.config import settings
from models.song import Song

# Configure logging
logger = logging.getLogger("tuneslice.scanner")
logging.basicConfig(level=logging.INFO)

def get_audio_duration(file_path: str) -> float:
    """
    Query ffprobe to extract audio file duration in seconds without loading the file into RAM.
    """
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe binary is not installed or not present in system PATH")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=5.0
        )
        duration_str = result.stdout.strip()
        if not duration_str:
            raise ValueError("ffprobe returned empty duration")
        return float(duration_str)
    except Exception as e:
        logger.error(f"Failed to extract duration for {file_path} using ffprobe: {e}")
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

def find_matching_thumbnail(filename_no_ext: str, thumbnails_dir: str) -> str | None:
    """
    Scans the thumbnails directory for an artwork file matching the song filename.
    Supports .jpg, .jpeg, .png, and .webp extensions.
    """
    if not os.path.exists(thumbnails_dir):
        return None

    valid_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    
    # Try direct match with the lowercase song filename base
    for ext in valid_extensions:
        potential_name = f"{filename_no_ext}{ext}"
        potential_path = os.path.join(thumbnails_dir, potential_name)
        if os.path.isfile(potential_path):
            return potential_path
            
    # Try matching title string case-insensitively
    for file in os.listdir(thumbnails_dir):
        base, ext = os.path.splitext(file)
        if base.lower() == filename_no_ext.lower() and ext.lower() in valid_extensions:
            return os.path.join(thumbnails_dir, file)

    return None

async def sync_songs(db: Session) -> dict:
    """
    Main sync scanner service. Traverses the songs directory, processes
    each audio file, resolves dependencies, and saves details to the SQLite DB.
    """
    # Resolve absolute paths relative to execution folder
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    songs_dir = os.path.abspath(os.path.join(base_dir, "songs"))
    thumbnails_dir = os.path.abspath(os.path.join(base_dir, "thumbnails"))

    logger.info(f"Scanning songs directory: {songs_dir}")
    logger.info(f"Scanning thumbnails directory: {thumbnails_dir}")

    results = {"scanned": 0, "added": 0, "updated": 0, "failed": 0}

    if not os.path.exists(songs_dir):
        logger.warning(f"Songs directory does not exist: {songs_dir}. Skipping scan.")
        return results

    # Get all .mp3 files in /songs
    audio_files = [f for f in os.listdir(songs_dir) if f.lower().endswith(".mp3")]

    for audio_file in audio_files:
        results["scanned"] += 1
        full_audio_path = os.path.join(songs_dir, audio_file)
        filename_no_ext, _ = os.path.splitext(audio_file)

        try:
            # 1. Fetch exact duration from ffprobe
            duration = get_audio_duration(full_audio_path)

            # 2. Extract song title and artist names
            title, artist = parse_filename(audio_file)

            # 3. Lookup artwork inside thumbnails folder
            thumbnail_path = find_matching_thumbnail(filename_no_ext, thumbnails_dir)

            # 3.5. If no local thumbnail, try fetching from Spotify
            if not thumbnail_path:
                from services.spotify import spotify_service
                logger.info(f"No local thumbnail for {title}. Fetching from Spotify...")
                spotify_url = await spotify_service.search_track_thumbnail(title, artist)
                if spotify_url:
                    downloaded_path = await spotify_service.download_thumbnail(spotify_url, filename_no_ext, thumbnails_dir)
                    if downloaded_path:
                        thumbnail_path = downloaded_path

            # 4. Check if song already exists in the database
            existing_song = db.query(Song).filter(Song.audio_path == full_audio_path).first()

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
                if existing_song.thumbnail_path != thumbnail_path:
                    existing_song.thumbnail_path = thumbnail_path
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
                    audio_path=full_audio_path,
                    thumbnail_path=thumbnail_path,
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
