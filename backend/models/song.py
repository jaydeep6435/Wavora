from sqlalchemy import Column, Integer, String, Float
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
