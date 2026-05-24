from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
import os
import uuid
from db.session import get_db
from models.song import Song
from schemas.song import SongResponse
from schemas.clip import ClipGenerateRequest
from typing import List
from services.audio_clipper import slice_audio_async

api_router = APIRouter()

def map_song_to_response(song: Song) -> SongResponse:
    """
    Utility mapper that reads a database Song model and computes relative 
    web-accessible URLs for raw audio streaming and artwork.
    """
    audio_filename = os.path.basename(song.audio_path)
    audio_url = f"/songs/{audio_filename}"
    
    thumbnail_url = None
    if song.thumbnail_path:
        thumbnail_filename = os.path.basename(song.thumbnail_path)
        thumbnail_url = f"/thumbnails/{thumbnail_filename}"
        
    return SongResponse(
        id=song.id,
        title=song.title,
        artist=song.artist,
        audio_path=song.audio_path,
        thumbnail_path=song.thumbnail_path,
        duration=song.duration,
        audio_url=audio_url,
        thumbnail_url=thumbnail_url
    )

@api_router.get("/songs", response_model=List[SongResponse], summary="Get all songs")
async def get_songs(
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int = Query(100, ge=1, le=100, description="Max number of items to return"),
    db: Session = Depends(get_db)
):
    """
    Retrieve all local songs metadata stored in the SQLite database, with pagination capabilities.
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

    # Resolve absolute path to clips directory
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    clips_dir = os.path.abspath(os.path.join(base_dir, "clips"))
    output_path = os.path.join(clips_dir, clip_filename)
    
    # 4. Execute the non-blocking async FFmpeg clipping engine
    try:
        await slice_audio_async(
            input_path=song.audio_path,
            output_path=output_path,
            start_time=request.start_time,
            end_time=request.end_time
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FFmpeg audio processing failed: {str(e)}"
        )

    # 5. Return success payload matching requirements exactly
    return {
        "success": True,
        "clipUrl": f"/clips/{clip_filename}",
        "duration": round(request.end_time - request.start_time, 2)
    }
