from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.declarative import declarative_base as legacy_declarative_base
from typing import Generator
from core.config import settings

# Fix Railway PostgreSQL URLs for SQLAlchemy
db_url = settings.DATABASE_URL
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Only use specific connect_args for sqlite
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator:
    """
    Dependency generator for DB sessions. Yields a session and safely 
    closes it after request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
