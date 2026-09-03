import os
import re
import uuid
import logging
import base64
import glob
import time
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
import yt_dlp
from services.audio_processor import slice_audio_async

logger = logging.getLogger("wavora.youtube_custom")
router = APIRouter(prefix="/youtube-custom", tags=["YouTube Custom"])

def cleanup_temp_files():
    """
    Deletes temporary custom audio files older than 1 hour.
    """
    tmp_dir = get_tmp_dir()
    now = time.time()
    for f in glob.glob(os.path.join(tmp_dir, "custom_*.mp3")) + glob.glob(os.path.join(tmp_dir, "clip_*.mp3")):
        try:
            if os.stat(f).st_mtime < now - 3600:
                os.remove(f)
                logger.info(f"Cleaned up temporary file: {f}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {f}: {e}")

class YouTubeProcessRequest(BaseModel):
    url: str = Field(..., description="YouTube or YouTube Music URL")

class CustomClipGenerateRequest(BaseModel):
    video_id: str = Field(..., alias="videoId", description="Temporary Video ID")
    start_time: float = Field(..., alias="startTime", ge=0, description="Start time of the clip in seconds")
    end_time: float = Field(..., alias="endTime", description="End time of the clip in seconds")

    @field_validator("end_time")
    @classmethod
    def validate_clip_duration(cls, end_time: float, info) -> float:
        start_time = info.data.get("start_time")
        if start_time is not None:
            if end_time <= start_time:
                raise ValueError("End time must be greater than start time")
            duration = end_time - start_time
            if duration > 30.1:
                raise ValueError("Clip duration cannot exceed 30 seconds")
        return end_time

    model_config = {
        "populate_by_name": True
    }

def get_tmp_dir() -> str:
    tmp_dir = "/tmp"
    if os.name == "nt":
        tmp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"))
    os.makedirs(tmp_dir, exist_ok=True)
    return tmp_dir

@router.post("/process", summary="Download YouTube audio temporarily")
def process_youtube_link(request: YouTubeProcessRequest):
    """
    Downloads a YouTube audio temporarily to serve it for waveform slicing.
    Returns metadata and a local streaming URL.
    """
    tmp_dir = get_tmp_dir()
    video_id = str(uuid.uuid4())
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(tmp_dir, f'custom_{video_id}.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(request.url, download=True)
            
            title = info_dict.get('title', 'Unknown Title')
            artist = info_dict.get('uploader', 'Unknown Artist')
            duration = info_dict.get('duration', 0.0)
            thumbnail_url = info_dict.get('thumbnail', '')
            
            # Use proxy URL for streaming to bypass CORS
            stream_url = f"/api/v1/youtube-custom/stream/{video_id}"
            
            # The exact filepath yt-dlp saves to after post-processing will end in .mp3
            expected_filepath = os.path.join(tmp_dir, f'custom_{video_id}.mp3')
            
            if not os.path.exists(expected_filepath):
                raise HTTPException(status_code=500, detail="Failed to download audio file")

            return {
                "success": True,
                "video_id": video_id,
                "song": {
                    "id": f"custom_{video_id}", # Special string ID
                    "title": title,
                    "artist": artist,
                    "duration": float(duration) if duration else 180.0,
                    "thumbnail_url": thumbnail_url,
                    "audio_url": stream_url
                }
            }
    except Exception as e:
        logger.error(f"Failed to process youtube custom link: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process YouTube link: {str(e)}"
        )

@router.get("/stream/{video_id}", summary="Stream custom youtube audio")
def stream_custom_audio(video_id: str):
    """
    Serves the temporary mp3 file to the frontend with CORS headers so WaveSurfer can read it.
    """
    # Simple security check to prevent directory traversal
    if not re.match(r'^[a-zA-Z0-9-]+$', video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID format")
        
    tmp_dir = get_tmp_dir()
    filepath = os.path.join(tmp_dir, f"custom_{video_id}.mp3")
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Temporary audio file not found or expired")
        
    return FileResponse(
        path=filepath,
        media_type="audio/mpeg",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Accept-Ranges": "bytes"
        }
    )

@router.post("/generate-custom-clip", summary="Generate clip from custom youtube audio")
async def generate_custom_clip(request: CustomClipGenerateRequest):
    """
    Slices the temporary local audio file using FFmpeg and returns the base64 mp3.
    """
    tmp_dir = get_tmp_dir()
    input_path = os.path.join(tmp_dir, f"custom_{request.video_id}.mp3")
    
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="Original audio file not found. Please reload the YouTube link.")
        
    clip_id = str(uuid.uuid4())
    output_path = os.path.join(tmp_dir, f"clip_{clip_id}.mp3")
    
    try:
        await slice_audio_async(
            input_path=input_path,
            output_path=output_path,
            start_time=request.start_time,
            end_time=request.end_time
        )
    except Exception as e:
        logger.error(f"FFmpeg slicing failed for custom clip: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FFmpeg audio processing failed: {str(e)}"
        )
        
    try:
        with open(output_path, 'rb') as f:
            file_content = f.read()
            base64_content = base64.b64encode(file_content).decode('utf-8')
            clip_data_url = f"data:audio/mp3;base64,{base64_content}"
    except Exception as e:
        logger.error(f"Failed to read/encode generated custom clip: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process generated audio clip: {str(e)}"
        )
    finally:
        # Cleanup the temp CLIP file
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass

    return {
        "success": True,
        "clipUrl": clip_data_url,
        "duration": round(request.end_time - request.start_time, 2)
    }
