import os
import subprocess
import shutil
import logging
from sqlalchemy.orm import Session
from core.config import settings
from models.song import Song
import cloudinary
import cloudinary.api

# Configure logging
logger = logging.getLogger("wavora.scanner")
logging.basicConfig(level=logging.INFO)

def configure_cloudinary():
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY:
        raise ValueError("Cloudinary credentials must be set in .env")
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True
    )

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
        return None

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
    Main sync scanner service. Connects to Cloudinary, processes
    each audio file in the 'songs' folder, resolves dependencies, and saves details to DB.
    """
    logger.info(f"Connecting to Cloudinary to scan 'songs/' folder")
    results = {"scanned": 0, "added": 0, "updated": 0, "failed": 0, "debug": []}

    audio_files_list = [] # List of tuples: (filename, secure_url, cld_duration)

    try:
        configure_cloudinary()
        
        # Cloudinary treats API audio uploads as 'video', but manual web dashboard uploads might be 'raw'
        audio_files_list = []
        
        for r_type in ["video", "audio", "raw", "image"]:
            try:
                response = cloudinary.api.resources(
                    resource_type=r_type,
                    type="upload",
                    prefix="songs/",
                    max_results=500
                )
                
                resources = response.get("resources", [])
                for resource in resources:
                    public_id = resource.get("public_id")
                    secure_url = resource.get("secure_url")
                    
                    filename = public_id.split("/")[-1]
                    if filename:
                        audio_files_list.append((filename, secure_url, resource.get("duration")))
                        results["debug"].append(f"Found in Cloudinary: {filename} ({r_type})")
            except Exception as e:
                logger.warning(f"Failed to fetch resource type {r_type}: {e}")
                results["debug"].append(f"Skipped {r_type} query: {str(e)}")

    except Exception as e:
        logger.warning(f"Failed to fetch resources from Cloudinary: {e}. Skipping scan.")
        return results

    if not audio_files_list:
        logger.info("No audio files found in Cloudinary 'songs/' folder.")
        return results

    for audio_file, full_audio_url, cld_duration in audio_files_list:
        results["scanned"] += 1
        
        filename_no_ext, _ = os.path.splitext(audio_file)

        try:
            # 1. Fetch exact duration from Cloudinary or fallback to ffprobe
            if cld_duration:
                duration = float(cld_duration)
            else:
                duration = get_audio_duration(full_audio_url) or 180.0 # Fallback to 3 mins if ffprobe completely fails

            # 2. Extract song title and artist names
            title, artist = parse_filename(audio_file)

            # 3. Try fetching thumbnail and official metadata from iTunes
            thumbnail_url = None
            from services.spotify import spotify_service
            logger.info(f"Fetching metadata for {title} from iTunes...")
            itunes_data = await spotify_service.search_track_thumbnail(title, artist)
            if itunes_data:
                thumbnail_url = itunes_data.get("thumbnail_url")
                
                # Intelligent overwrite: use official iTunes title and artist to fix messy filenames
                official_title = itunes_data.get("title")
                official_artist = itunes_data.get("artist")
                if official_title:
                    title = official_title
                if official_artist:
                    artist = official_artist

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
            results["debug"].append(f"Failed {audio_file}: {str(e)}")
            results["failed"] += 1
            db.rollback()

    logger.info(f"Sync complete. Scanned: {results['scanned']}, Added: {results['added']}, Updated: {results['updated']}, Failed: {results['failed']}")
    return results
