import os
import glob
import logging
import yt_dlp
import cloudinary
import cloudinary.uploader
from core.config import settings

logger = logging.getLogger("wavora.youtube_sync")

def sync_trending_youtube_song():
    """
    Finds a trending song on YouTube, downloads it as an mp3, 
    uploads it to Cloudinary, and cleans up the local file.
    """
    logger.info("Starting Daily YouTube Sync task...")
    
    # Ensure Cloudinary is configured
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY:
        logger.error("Cloudinary credentials missing. Cannot run YouTube sync.")
        return {"success": False, "error": "Cloudinary credentials missing"}
        
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True
    )

    tmp_dir = "/tmp"
    if os.name == "nt":
        tmp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"))
        os.makedirs(tmp_dir, exist_ok=True)
        
    # yt-dlp configuration
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(tmp_dir, 'yt_sync_%(id)s.%(ext)s'),
        'noplaylist': False,
        'quiet': False
    }
    
    # Clean up any leftover temp files (including parts or webm) before we begin
    for f in glob.glob(os.path.join(tmp_dir, "yt_sync_*")):
        try:
            os.remove(f)
        except:
            pass

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            import random
            
            # Diverse list of all Indian cultures to pull trending hits from
            indian_regions = [
                "hindi punjabi",
                "south indian telugu tamil",
                "marathi",
                "gujarati garba",
                "rajasthani",
                "bhojpuri",
                "bollywood"
            ]
            selected_region = random.choice(indian_regions)
            
            search_query = f"ytsearch15:latest trending instagram reels songs {selected_region} official music video hit"
            logger.info(f"Searching YouTube with query: {search_query}")
            
            # First, fetch search results WITHOUT downloading
            info_dict = ydl.extract_info(search_query, download=False)
            
            target_entry = None
            if 'entries' in info_dict:
                for entry in info_dict['entries']:
                    duration = entry.get('duration', 9999)
                    # Filter out short clips/teasers (< 1 min) and huge mixes (> 11 mins)
                    if entry and duration >= 60 and duration <= 660:
                        target_entry = entry
                        break
            
            if not target_entry:
                raise ValueError("Could not find any suitable tracks under 10 minutes.")
                
            video_title = target_entry.get('title', 'Unknown Title')
            video_uploader = target_entry.get('uploader', 'Unknown Artist')
            # Fallback to id if webpage_url doesn't exist
            track_url = target_entry.get('webpage_url') or target_entry.get('url') or target_entry.get('id')
            
            logger.info(f"Downloading selected track: {video_title} by {video_uploader}")
            ydl.download([track_url])

            # Dynamically find the file yt-dlp just created
            downloaded_files = glob.glob(os.path.join(tmp_dir, "yt_sync_*.mp3"))
            if not downloaded_files:
                raise FileNotFoundError("yt-dlp finished but no mp3 file was found in the temp directory.")
                
            expected_filepath = downloaded_files[0]
                
            import re
            
            # Sanitize title and artist to create a clean public_id (e.g. Title-Artist)
            # This allows song_scanner.py to parse the filename and query iTunes for the thumbnail
            safe_title = re.sub(r'[^a-zA-Z0-9\s]', '', video_title).strip().replace(' ', '_')
            safe_artist = re.sub(r'[^a-zA-Z0-9\s]', '', video_uploader).strip().replace(' ', '_')
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
            logger.info(f"Successfully uploaded to Cloudinary: {cloudinary_url}")

            # Cleanup the local temp file
            if os.path.exists(expected_filepath):
                os.remove(expected_filepath)
                logger.info("Cleaned up local temp file.")

            return {
                "success": True, 
                "title": video_title, 
                "cloudinary_url": cloudinary_url
            }

    except Exception as e:
        logger.error(f"YouTube Sync failed: {e}")
        # Attempt to cleanup any partial files
        for f in glob.glob(os.path.join(tmp_dir, "yt_sync_*")):
            try:
                os.remove(f)
            except:
                pass
        return {"success": False, "error": str(e)}
