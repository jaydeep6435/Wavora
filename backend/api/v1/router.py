from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
import os
import uuid
import logging
from db.session import get_db
from models.song import Song
from schemas.song import SongResponse
from schemas.clip import ClipGenerateRequest
from typing import List
from services.audio_clipper import slice_audio_async
from services.song_scanner import sync_songs

logger = logging.getLogger("wavora.router")
api_router = APIRouter()

@api_router.post("/sync", summary="Force sync library with Cloudinary")
async def force_sync(db: Session = Depends(get_db)):
    """
    Manually trigger a scan to find new songs in Cloudinary and sync them to the database.
    """
    try:
        results = await sync_songs(db)
        return {"success": True, "results": results}
    except Exception as e:
        logger.error(f"Manual sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from services.youtube_sync import sync_trending_youtube_song
import cloudinary
import cloudinary.api
from core.config import settings

@api_router.get("/debug-cloudinary", summary="Dump raw Cloudinary data")
async def debug_cloudinary():
    """
    Directly query Cloudinary and return the raw JSON so we can debug missing tracks.
    """
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True
    )
    debug_data = {}
    for r_type in ["video", "audio", "raw", "image"]:
        try:
            res = cloudinary.api.resources(
                resource_type=r_type,
                type="upload",
                prefix="songs/",
                max_results=100
            )
            debug_data[r_type] = res.get("resources", [])
        except Exception as e:
            debug_data[r_type] = {"error": str(e)}
            
    return debug_data

@api_router.get("/debug-db", summary="Debug database and sync")
async def debug_db(db: Session = Depends(get_db)):
    """
    Run the sync manually and return exactly what happened, plus current DB state.
    """
    try:
        from models.song import Song
        before_songs = db.query(Song).all()
        before_state = [{"id": s.id, "title": s.title, "audio_path": s.audio_path.split("/")[-1]} for s in before_songs]
        
        sync_results = await sync_songs(db)
        
        after_songs = db.query(Song).all()
        after_state = [{"id": s.id, "title": s.title, "audio_path": s.audio_path.split("/")[-1]} for s in after_songs]
        
        return {
            "success": True,
            "sync_results": sync_results,
            "database_before": before_state,
            "database_after": after_state
        }
    except Exception as e:
        return {"success": False, "error": str(e), "traceback": __import__("traceback").format_exc()}

@api_router.get("/debug-queue", summary="View the download queue")
async def debug_queue():
    """
    Returns the current pending items in the download queue.
    """
    from services.queue_manager import get_queue
    try:
        queue = get_queue()
        return {
            "success": True,
            "total_pending": len(queue),
            "queue": queue
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@api_router.post("/youtube-sync/force", summary="Force sync trending song from YouTube")
async def force_youtube_sync(db: Session = Depends(get_db)):
    """
    Manually trigger the background job that downloads a trending YouTube song, 
    uploads it to Cloudinary, and then syncs the database.
    """
    try:
        # Run the download & upload to Cloudinary
        yt_result = sync_trending_youtube_song()
        if not yt_result.get("success"):
            raise Exception(yt_result.get("error"))
            
        # Trigger DB sync so the new song shows up
        db_results = await sync_songs(db)
        return {
            "success": True, 
            "youtube": yt_result,
            "database_sync": db_results
        }
    except Exception as e:
        logger.error(f"Manual YouTube sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def map_song_to_response(song: Song) -> SongResponse:
    """
    Utility mapper that reads a database Song model and computes relative 
    web-accessible URLs for raw audio streaming and artwork.
    For Cloudinary, the audio_path and thumbnail_path are already public URLs.
    """
    return SongResponse(
        id=song.id,
        title=song.title,
        artist=song.artist,
        audio_path=song.audio_path,
        thumbnail_path=song.thumbnail_path,
        duration=song.duration,
        audio_url=song.audio_path,
        thumbnail_url=song.thumbnail_path,
        album_id=song.album_id
    )

from models.album import Album
from schemas.song import AlbumResponse

@api_router.get("/albums", response_model=List[AlbumResponse], summary="Get all albums")
async def get_albums(
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int = Query(100, ge=1, le=100, description="Max number of items to return"),
    db: Session = Depends(get_db)
):
    """
    Retrieve all albums and their associated songs.
    """
    albums = db.query(Album).offset(skip).limit(limit).all()
    # Map each album to AlbumResponse, injecting its songs via map_song_to_response
    response_list = []
    for album in albums:
        album_dict = {
            "id": album.id,
            "title": album.title,
            "artist": album.artist,
            "thumbnail_path": album.thumbnail_path,
            "songs": [map_song_to_response(song) for song in album.songs]
        }
        response_list.append(album_dict)
    return response_list

@api_router.get("/songs", response_model=List[SongResponse], summary="Get all songs")
async def get_songs(
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int = Query(100, ge=1, le=100, description="Max number of items to return"),
    db: Session = Depends(get_db)
):
    """
    Retrieve all local songs metadata stored in the database, with pagination capabilities.
    """
    songs = db.query(Song).offset(skip).limit(limit).all()
    return [map_song_to_response(song) for song in songs]

@api_router.get("/search", response_model=List[SongResponse], summary="Search songs")
async def search_songs(
    q: str = Query(..., min_length=1, description="Query string to search in song titles or artists"),
    db: Session = Depends(get_db)
):
    """
    Search songs dynamically by title or artist using a case-insensitive match (SQL LIKE/ILIKE).
    """
    search_pattern = f"%{q}%"
    songs = db.query(Song).filter(
        (Song.title.ilike(search_pattern)) | 
        (Song.artist.ilike(search_pattern))
    ).limit(50).all()
    
    return [map_song_to_response(song) for song in songs]

@api_router.post("/generate-clip", summary="Generate audio clip")
async def generate_clip(
    request: ClipGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Validate song coordinates and generate a 30-second song clip from timestamps.
    """
    # 1. Verify song exists in DB before slicing
    song = db.query(Song).filter(Song.id == request.song_id).first()
    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Song with ID {request.song_id} does not exist"
        )
        
    # 2. Check boundaries against actual song duration
    if request.start_time >= song.duration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Start time ({request.start_time}s) exceeds song duration ({song.duration:.2f}s)"
        )
    if request.end_time > song.duration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"End time ({request.end_time}s) exceeds song duration ({song.duration:.2f}s)"
        )
        
    # 3. Generate unique UUID filename
    clip_id = str(uuid.uuid4())
    clip_filename = f"{clip_id}.mp3"

    # Resolve absolute path to a temporary directory
    # On Vercel, /tmp is writable
    tmp_dir = "/tmp"
    if os.name == "nt": # Fallback for Windows local dev
        tmp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"))
        os.makedirs(tmp_dir, exist_ok=True)
        
    output_path = os.path.join(tmp_dir, clip_filename)
    
    # 4. Execute the non-blocking async FFmpeg clipping engine
    try:
        await slice_audio_async(
            input_path=song.audio_path,  # remote URL
            output_path=output_path,
            start_time=request.start_time,
            end_time=request.end_time
        )
    except Exception as e:
        logger.error(f"FFmpeg slicing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FFmpeg audio processing failed: {str(e)}"
        )

    import base64

    # 5. Read the generated clip file and encode to base64 data URL
    try:
        with open(output_path, 'rb') as f:
            file_content = f.read()
            base64_content = base64.b64encode(file_content).decode('utf-8')
            clip_data_url = f"data:audio/mp3;base64,{base64_content}"
    except Exception as e:
        logger.error(f"Failed to read/encode generated clip: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process generated audio clip: {str(e)}"
        )
    finally:
        # Cleanup the temp file immediately
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass

    # 6. Return success payload with base64 audio data URI
    return {
        "success": True,
        "clipUrl": clip_data_url,
        "duration": round(request.end_time - request.start_time, 2)
    }
