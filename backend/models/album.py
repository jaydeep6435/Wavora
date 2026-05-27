from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from db.session import Base

class Album(Base):
    """
    SQLAlchemy Model representing an Album.
    Groups multiple songs together.
    """
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    artist = Column(String, nullable=False, index=True)
    thumbnail_path = Column(String, nullable=True)
    
    # Optional: store iTunes ID to prevent duplicates easily
    itunes_id = Column(String, unique=True, nullable=True, index=True)

    # Establish relationship to songs
    songs = relationship("Song", back_populates="album", cascade="all, delete-orphan")
