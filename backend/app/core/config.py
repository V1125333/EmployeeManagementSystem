"""
Core configuration — loads environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./reknew_orbit.db")

    # SMTP
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.office365.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")

    # App
    APP_NAME: str = os.getenv("APP_NAME", "Reknew Orbit")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    CERTIFICATE_VERIFY_BASE_URL: str = os.getenv(
        "CERTIFICATE_VERIFY_BASE_URL",
        "https://reknew.ai/verify",
    )
    PII_ENCRYPTION_KEY: str = os.getenv("PII_ENCRYPTION_KEY", "")
    FIELD_ENCRYPTION_KEY_VERSION: str = os.getenv("FIELD_ENCRYPTION_KEY_VERSION", "1")
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")


settings = Settings()
