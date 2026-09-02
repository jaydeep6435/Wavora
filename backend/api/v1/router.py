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

@api_router.post("/debug-reset", summary="Clear queue and remove Frozen album")
async def debug_reset(db: Session = Depends(get_db)):
    """
    Clears the entire download queue and deletes the Frozen 2 album.
    """
    from models.sync_state import DownloadQueue
    from models.album import Album
    try:
        # Clear Queue
        db.query(DownloadQueue).delete()
        
        # Delete Frozen 2 Album
        albums_to_delete = db.query(Album).filter(Album.title.ilike("%Frozen%")).all()
        for album in albums_to_delete:
            db.delete(album)
            
        db.commit()
        return {"success": True, "message": f"Cleared queue and deleted {len(albums_to_delete)} 'Frozen' albums."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}

@api_router.post("/requeue-albums", summary="Re-queue all empty albums for download")
async def requeue_albums(db: Session = Depends(get_db)):
    """
    Scans all albums in DB that have zero songs.
    For each, fetches tracks from iTunes using stored itunes_id and re-queues them for download.
    """
    import httpx
    from models.album import Album
    from models.song import Song
    from services.queue_manager import push_queue

    albums = db.query(Album).all()
    total_queued = 0
    report = []

    for album in albums:
        song_count = db.query(Song).filter(Song.album_id == album.id).count()
        if song_count > 0:
            report.append({"album": album.title, "status": "skipped (already has songs)", "songs": song_count})
            continue

        if not album.itunes_id:
            report.append({"album": album.title, "status": "skipped (no iTunes ID)"})
            continue

        # Fetch tracks from iTunes
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://itunes.apple.com/lookup",
                    params={"id": album.itunes_id, "entity": "song"}
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            report.append({"album": album.title, "status": f"iTunes fetch error: {str(e)}"})
            continue

        tracks = [t for t in data.get("results", []) if t.get("wrapperType") == "track"]
        if not tracks:
            report.append({"album": album.title, "status": "no tracks found on iTunes"})
            continue

        artwork = album.thumbnail_path or ""
        queue_items = []
        for track in tracks:
            duration_ms = track.get("trackTimeMillis", 0)
            queue_items.append({
                "title": track.get("trackName", ""),
                "artist": track.get("artistName", album.artist),
                "album_id": album.id,
                "thumbnail_url": artwork,
                "duration": round(duration_ms / 1000, 2) if duration_ms else 0.0
            })

        push_queue(queue_items)
        total_queued += len(queue_items)
        report.append({"album": album.title, "status": "queued", "tracks_queued": len(queue_items)})
        logger.info(f"Re-queued {len(queue_items)} tracks for album '{album.title}'")

    return {
        "success": True,
        "total_queued": total_queued,
        "albums_processed": len(albums),
        "report": report
    }

@api_router.post("/youtube-sync/force", summary="Force sync trending song from YouTube")
async def force_youtube_sync(db: Session = Depends(get_db)):
    """
    Manually trigger the background job that downloads a trending YouTube song, 
    uploads it to Cloudinary, and then syncs the database.
    """
    try:
        yt_result = sync_trending_youtube_song()
        if not yt_result.get("success"):
            raise Exception(yt_result.get("error"))
        db_results = await sync_songs(db)
        return {
            "success": True, 
            "youtube": yt_result,
            "database_sync": db_results
        }
    except Exception as e:
        logger.error(f"Manual YouTube sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/process-queue", summary="Force-process ALL items in the download queue")
async def force_process_queue():
    """
    Immediately processes every pending song in the download queue one by one.
    Use this to bulk-download all queued songs without waiting for the scheduler.
    """
    import asyncio
    from services.queue_manager import get_queue, pop_queue
    from services.youtube_sync import process_queue_item

    queue_snapshot = get_queue()
    total = len(queue_snapshot)

    if total == 0:
        return {"success": True, "message": "Queue is already empty. Nothing to process.", "processed": 0}

    logger.info(f"Force-processing {total} items from the download queue...")

    processed = 0
    failed = 0
    results = []

    for i in range(total):
        item = get_queue()
        if not item:
            break
        current = item[0]
        try:
            # Run the blocking download in a thread pool to not block the event loop
            await asyncio.get_event_loop().run_in_executor(None, process_queue_item)
            processed += 1
            results.append({"title": current["title"], "artist": current["artist"], "status": "queued_for_download"})
            logger.info(f"Processed {processed}/{total}: {current['title']}")
        except Exception as e:
            failed += 1
            results.append({"title": current["title"], "artist": current["artist"], "status": f"error: {str(e)}"})
            logger.error(f"Failed to process {current['title']}: {e}")

    return {
        "success": True,
        "message": f"Finished processing queue. {processed} downloaded, {failed} failed.",
        "processed": processed,
        "failed": failed,
        "results": results
    }

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
from schemas.album import AlbumCreateRequest

@api_router.post("/albums", summary="Create an album from iTunes and queue its songs for download")
async def create_album(request: AlbumCreateRequest, db: Session = Depends(get_db)):
    """
    Search iTunes for an album by name, create it in the database,
    and add all its songs to the download queue for background processing.
    """
    import httpx
    from services.queue_manager import push_queue, is_album_downloaded, mark_album_downloaded

    search_query = request.album_name
    logger.info(f"Searching iTunes for album: {search_query}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://itunes.apple.com/search",
                params={
                    "term": search_query,
                    "media": "music",
                    "entity": "album",
                    "limit": 5,
                }
            )
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"iTunes API error: {str(e)}")

    results = data.get("results", [])
    if not results:
        raise HTTPException(status_code=404, detail=f"No album found on iTunes for: {search_query}")

    # Pick the first album result
    album_data = results[0]
    collection_id = str(album_data.get("collectionId", ""))
    album_title = album_data.get("collectionName", search_query)
    album_artist = album_data.get("artistName", "Unknown Artist")
    artwork_url = (album_data.get("artworkUrl100") or "").replace("100x100bb", "600x600bb")

    # Check if album already exists in DB
    existing = db.query(Album).filter(Album.itunes_id == collection_id).first()
    if existing:
        return {
            "success": False,
            "message": f"Album '{album_title}' already exists in the database.",
            "album_id": existing.id
        }

    # Create Album record in DB
    new_album = Album(
        title=album_title,
        artist=album_artist,
        thumbnail_path=artwork_url or None,
        itunes_id=collection_id
    )
    db.add(new_album)
    db.commit()
    db.refresh(new_album)
    logger.info(f"Created album: {album_title} (id={new_album.id})")

    # Now fetch all tracks in this album from iTunes
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            tracks_response = await client.get(
                "https://itunes.apple.com/lookup",
                params={
                    "id": collection_id,
                    "entity": "song",
                }
            )
            tracks_response.raise_for_status()
            tracks_data = tracks_response.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"iTunes tracks fetch error: {str(e)}")

    tracks = [t for t in tracks_data.get("results", []) if t.get("wrapperType") == "track"]
    logger.info(f"Found {len(tracks)} tracks for album '{album_title}'")

    # Queue all tracks for background download
    queue_items = []
    for track in tracks:
        track_title = track.get("trackName", "")
        track_artist = track.get("artistName", album_artist)
        duration_ms = track.get("trackTimeMillis", 0)
        duration_s = round(duration_ms / 1000, 2) if duration_ms else 0.0
        track_artwork = (track.get("artworkUrl100") or artwork_url or "").replace("100x100bb", "600x600bb")

        queue_items.append({
            "title": track_title,
            "artist": track_artist,
            "album_id": new_album.id,
            "thumbnail_url": track_artwork,
            "duration": duration_s
        })

    push_queue(queue_items)
    mark_album_downloaded(collection_id)

    return {
        "success": True,
        "message": f"Album '{album_title}' created with {len(tracks)} songs queued for download.",
        "album_id": new_album.id,
        "album_title": album_title,
        "album_artist": album_artist,
        "tracks_queued": len(tracks)
    }

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
