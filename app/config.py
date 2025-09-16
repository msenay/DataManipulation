"""Application configuration management."""
import os
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseModel):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")
    
    # Application
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # API
    api_v1_prefix: str = "/v1"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v):
        """Validate and parse database URL."""
        try:
            parsed = urlparse(v)
            if not parsed.scheme:
                raise ValueError("Database URL must include a scheme")
            return v
        except Exception as e:
            raise ValueError(f"Invalid database URL: {e}")

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return self.database_url.startswith("sqlite")

    @property
    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL database."""
        return self.database_url.startswith("postgresql")


# Global settings instance
settings = Settings()