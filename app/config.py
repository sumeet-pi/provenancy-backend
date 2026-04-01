"""
Configuration module for loading environment variables.
Loads settings from .env file using python-dotenv.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Build path to .env file in the backend directory
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)


class Settings:
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # App metadata
    APP_NAME: str = "Provenancy API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"


settings = Settings()
