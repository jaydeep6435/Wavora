from pydantic import BaseModel, Field
from typing import Optional
import os

class SongBase(BaseModel):
    title: str = Field(..., description="Title of the song")
    artist: str = Field(..., description="Artist name")
    audio_path: str = Field(..., description="Supabase public URL to the audio file")
    thumbnail_path: Optional[str] = Field(None, description="Remote URL path for the thumbnail image")
    duration: float = Field(..., ge=0, description="Duration of the song in seconds")
    album_id: Optional[int] = Field(None, description="Foreign Key to the Album")

class SongCreate(SongBase):
    pass

class AlbumBase(BaseModel):
    title: str
    artist: str
    thumbnail_path: Optional[str] = None

class AlbumResponse(AlbumBase):
    id: int
    songs: Optional[list] = [] # To be populated with SongResponse objects
    
    model_config = {
        "from_attributes": True
    }

class SongResponse(SongBase):
    id: int
    audio_url: Optional[str] = Field(None, description="Web accessible URL path for streaming raw audio")
    thumbnail_url: Optional[str] = Field(None, description="Web accessible URL path for the thumbnail artwork")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "id": 1,
                "title": "Believer",
                "artist": "Imagine Dragons",
                "audio_path": "E:\\Wavorar\\songs\\believer-imagine_dragons.mp3",
                "thumbnail_path": "E:\\Wavorar\\thumbnails\\believer-imagine_dragons.jpg",
                "duration": 204.5,
                "audio_url": "/songs/believer-imagine_dragons.mp3",
                "thumbnail_url": "/thumbnails/believer-imagine_dragons.jpg"
            }
        }
    }
