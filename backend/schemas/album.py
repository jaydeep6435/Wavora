from pydantic import BaseModel
from typing import Optional, List
from schemas.song import SongResponse

class AlbumBase(BaseModel):
    title: str
    artist: str
    thumbnail_path: Optional[str] = None

class AlbumResponse(AlbumBase):
    id: int
    songs: List[SongResponse] = []

    class Config:
        from_attributes = True
