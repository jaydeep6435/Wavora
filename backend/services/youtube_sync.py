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
        'noplaylist': True,
        'quiet': False,
        'match_filter': yt_dlp.utils.match_filter_func("duration < 600") # Limit to tracks under 10 mins
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search for the top trending music video and download it
            # scsearch1: searches SoundCloud to completely bypass YouTube's datacenter IP block
            logger.info("Searching and downloading from SoundCloud...")
            info_dict = ydl.extract_info("scsearch1:trending pop", download=True)
            
            # extract_info returns a dictionary. Since it's a search, the actual video is in 'entries'
            if 'entries' in info_dict and len(info_dict['entries']) > 0:
                video_info = info_dict['entries'][0]
            else:
                video_info = info_dict
                
            video_id = video_info.get('id')
            video_title = video_info.get('title')
            logger.info(f"Downloaded: {video_title} (ID: {video_id})")

            # yt-dlp creates the mp3 file based on the outtmpl. 
            # The exact filename will be 'yt_sync_<video_id>.mp3'
            expected_filepath = os.path.join(tmp_dir, f"yt_sync_{video_id}.mp3")
            
            if not os.path.exists(expected_filepath):
                raise FileNotFoundError(f"Expected to find downloaded file at {expected_filepath} but it is missing.")
                
            logger.info("Uploading to Cloudinary in chunks (upload_large)...")
            # Upload to Cloudinary into the 'songs' folder.
            # Using upload_large handles big files and prevents '413 Request Entity Too Large'
            upload_result = cloudinary.uploader.upload_large(
                expected_filepath,
                resource_type="video",
                folder="songs/",
                public_id=f"{video_id}", # Optional: explicit public ID
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
