from sqlalchemy import Column, Integer, String, Float, ForeignKey
from db.session import Base

class DownloadedAlbumTracker(Base):
    """Tracks which iTunes collections have already been processed to prevent duplicates"""
    __tablename__ = "downloaded_album_tracker"
    
    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(String, unique=True, index=True, nullable=False)

class DownloadedSongTracker(Base):
    """Tracks individual songs that have already been processed"""
    __tablename__ = "downloaded_song_tracker"
    
    id = Column(Integer, primary_key=True, index=True)
    # The key is typically formatted as "title - artist" in lowercase
    key = Column(String, unique=True, index=True, nullable=False)

class DownloadQueue(Base):
    """Represents the queue of songs waiting to be downloaded from YouTube and uploaded to Cloudinary"""
    __tablename__ = "download_queue"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=True)
    thumbnail_url = Column(String, nullable=True)
    duration = Column(Float, nullable=False, default=0.0)
