from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from db.session import Base

class Song(Base):
    """
    SQLAlchemy Model representing song metadata stored in SQLite.
    Stores metadata only; raw audio files are stored in the filesystem.
    """
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    artist = Column(String, nullable=False, index=True)
    audio_path = Column(String, unique=True, nullable=False, index=True)
    thumbnail_path = Column(String, nullable=True)
    duration = Column(Float, nullable=False)

    # Link to Album
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=True)
    album = relationship("Album", back_populates="songs")
