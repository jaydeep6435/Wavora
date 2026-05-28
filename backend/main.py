from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from core.config import settings
from core.logging_config import setup_logging
from api.v1.router import api_router
import logging
from sqlalchemy import text
import os

# Initialize structured logging
setup_logging(settings.ENVIRONMENT)
logger = logging.getLogger("wavora.main")
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.youtube_sync import sync_trending_youtube_song

from contextlib import asynccontextmanager

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    # 1. Initialize Database Schema
    from db.session import engine
    from db.base import Base
    from sqlalchemy import text

    # Create all tables first (like 'albums')
    Base.metadata.create_all(bind=engine)

    # Handle migration for album_id gracefully after tables exist
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE songs ADD COLUMN album_id INTEGER REFERENCES albums(id)"))
            conn.commit()
            logger.info("Successfully added album_id column to songs table.")
    except Exception as e:
        if "duplicate column name" not in str(e).lower():
            logger.warning(f"Note on migration: {e}")

    # 2. Run Directory Scanner to Sync Local Songs in the BACKGROUND
    import asyncio
    from db.session import SessionLocal
    from services.song_scanner import sync_songs
    
    async def run_sync_background():
        db = SessionLocal()
        try:
            await sync_songs(db)
        except Exception as e:
            logger.error(f"Startup song scanning sync failed: {e}")
        finally:
            db.close()
            
    # Do not block startup!
    asyncio.create_task(run_sync_background())
    
    from services.youtube_sync import populate_album_queue, process_queue_item
    # 3. Start APScheduler for YouTube Sync
    # Populate Album queue at midnight
    scheduler.add_job(populate_album_queue, 'cron', hour=0, minute=0)
    # Process one song from the queue every 2 minutes (safe rate to avoid IP bans)
    scheduler.add_job(process_queue_item, 'cron', minute='*/2')
    scheduler.start()

    yield
    # Shutdown actions (if any)
    scheduler.shutdown()
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)


# Set CORS origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Register API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    if settings.ENVIRONMENT == "production":
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )

# TODO: For production monitoring, integrate tools like Prometheus here:
# from prometheus_fastapi_instrumentator import Instrumentator
# Instrumentator().instrument(app).expose(app)

@app.get("/", tags=["Health Check"])
async def root():
    db_status = "offline"
    from db.session import SessionLocal
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_status = "online"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
    finally:
        try:
            db.close()
        except:
            pass
            
    return {
        "status": "online",
        "database": db_status,
        "environment": settings.ENVIRONMENT,
        "project": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "api_v1_url": f"{settings.API_V1_STR}"
    }
