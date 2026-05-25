from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from core.config import settings
from api.v1.router import api_router
import os

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    # 1. Initialize PostgreSQL Database Schema
    from db.session import engine
    from db.base import Base
    Base.metadata.create_all(bind=engine)

    # 2. Run Directory Scanner to Sync Local Songs
    from db.session import SessionLocal
    from services.song_scanner import sync_songs
    db = SessionLocal()
    try:
        await sync_songs(db)
    except Exception as e:
        import logging
        logging.getLogger("tuneslice.main").error(f"Startup song scanning sync failed: {e}")
    finally:
        db.close()

    yield
    # Shutdown actions (if any)

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
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Register API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Health Check"])
async def root():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "api_v1_url": f"{settings.API_V1_STR}"
    }
