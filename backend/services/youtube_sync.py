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
        'noplaylist': False,  # Allow it to process the search list
        'max_downloads': 1,   # But stop after successfully downloading 1 track
        'quiet': False,
        'match_filter': yt_dlp.utils.match_filter_func("duration < 600") # Limit to tracks under 10 mins
    }
    
    # Clean up any leftover temp files (including parts or webm) before we begin
    for f in glob.glob(os.path.join(tmp_dir, "yt_sync_*")):
        try:
            os.remove(f)
        except:
            pass

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search for the top trending music video and download it
            # scsearch15: grabs top 15 results. It will skip long DJ mixes and download the first valid one.
            logger.info("Searching and downloading from SoundCloud...")
            
            try:
                ydl.extract_info("scsearch15:trending pop", download=True)
            except Exception as download_e:
                # yt-dlp intentionally raises an exception to break out of the playlist loop when max_downloads is reached
                if "max-downloads" in str(download_e) or "Maximum number of downloads" in str(download_e):
                    logger.info("Successfully downloaded 1 track and reached max-downloads limit. Proceeding...")
                else:
                    raise download_e

            # Dynamically find the file yt-dlp just created
            downloaded_files = glob.glob(os.path.join(tmp_dir, "yt_sync_*.mp3"))
            if not downloaded_files:
                raise FileNotFoundError("yt-dlp finished but no mp3 file was found in the temp directory.")
                
            expected_filepath = downloaded_files[0]
                
            logger.info("Uploading to Cloudinary in chunks (upload_large)...")
            # Upload to Cloudinary into the 'songs' folder.
            # Using upload_large handles big files and prevents '413 Request Entity Too Large'
            upload_result = cloudinary.uploader.upload_large(
                expected_filepath,
                resource_type="video",
                folder="songs/"
            )
            
            cloudinary_url = upload_result.get("secure_url")
            logger.info(f"Successfully uploaded to Cloudinary: {cloudinary_url}")

            # Cleanup the local temp file
            if os.path.exists(expected_filepath):
                os.remove(expected_filepath)
                logger.info("Cleaned up local temp file.")

            return {
                "success": True, 
                "title": "Trending Track", 
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
