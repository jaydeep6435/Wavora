from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union
import json

class Settings(BaseSettings):
    PROJECT_NAME: str = "TuneSlice"
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

    DATABASE_URL: str = "sqlite:///./tuneslice.db"

    # Base Media Storage Directories
    SONGS_DIR: str = "../songs"
    CLIPS_DIR: str = "../clips"
    THUMBNAILS_DIR: str = "../thumbnails"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
