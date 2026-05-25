from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union
import json

class Settings(BaseSettings):
    PROJECT_NAME: str = "Wavora"
    API_V1_STR: str = "/api/v1"
    
    # CORS Origins - Parse comma-separated string or JSON array from environment
    BACKEND_CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        return v

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    
    # Cloudinary Settings
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    # Base Media Storage Directories
    SONGS_DIR: str = "../songs"
    CLIPS_DIR: str = "../clips"
    THUMBNAILS_DIR: str = "../thumbnails"

    # Spotify API (Optional for thumbnail fetching)
    SPOTIFY_CLIENT_ID: str | None = None
    SPOTIFY_CLIENT_SECRET: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
