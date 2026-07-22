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
    COMPLIANCE_COMPLIANT_THRESHOLD_HOURS: float = float(os.getenv("COMPLIANCE_COMPLIANT_THRESHOLD_HOURS", "2.0"))
    COMPLIANCE_WARNING_THRESHOLD_HOURS: float = float(os.getenv("COMPLIANCE_WARNING_THRESHOLD_HOURS", "5.0"))

    # Requests module config
    REQUESTS_SP_MAX_DURATION_MINUTES: int = int(os.getenv("REQUESTS_SP_MAX_DURATION_MINUTES", "480"))
    REQUESTS_EXPENSE_RECEIPT_REQUIRED: bool = os.getenv("REQUESTS_EXPENSE_RECEIPT_REQUIRED", "true").lower() == "true"
    REQUESTS_OVERTIME_MAX_DURATION_MINUTES: int = int(os.getenv("REQUESTS_OVERTIME_MAX_DURATION_MINUTES", "720"))
    REQUESTS_WFH_MAX_DAYS: int = int(os.getenv("REQUESTS_WFH_MAX_DAYS", "90"))

    # Storage
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "local")
    LOCAL_UPLOAD_ROOT: str = os.getenv("LOCAL_UPLOAD_ROOT", "uploads")
    ATTACHMENT_MAX_FILE_SIZE_BYTES: int = int(os.getenv("ATTACHMENT_MAX_FILE_SIZE_BYTES", str(10 * 1024 * 1024)))
    ATTACHMENT_MAX_FILES_PER_REQUEST: int = int(os.getenv("ATTACHMENT_MAX_FILES_PER_REQUEST", "5"))

    # Future Hetzner/S3 storage
    HETZNER_BUCKET_NAME: str = os.getenv("HETZNER_BUCKET_NAME", "")
    HETZNER_ENDPOINT: str = os.getenv("HETZNER_ENDPOINT", "")
    HETZNER_ACCESS_KEY: str = os.getenv("HETZNER_ACCESS_KEY", "")
    HETZNER_SECRET_KEY: str = os.getenv("HETZNER_SECRET_KEY", "")

    # Account recovery
    RESET_TOKEN_EXPIRY_MINUTES: int = int(os.getenv("RESET_TOKEN_EXPIRY_MINUTES", "15"))
    RESET_MAX_ATTEMPTS: int = int(os.getenv("RESET_MAX_ATTEMPTS", "5"))
    RESET_LOCKOUT_MINUTES: int = int(os.getenv("RESET_LOCKOUT_MINUTES", "30"))
    RESET_RATE_LIMIT_PER_HOUR: int = int(os.getenv("RESET_RATE_LIMIT_PER_HOUR", "5"))
    PASSWORD_MIN_LENGTH: int = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "3"))
    LOGIN_CHALLENGE_EXPIRY_MINUTES: int = int(os.getenv("LOGIN_CHALLENGE_EXPIRY_MINUTES", "5"))
    UNLOCK_REQUEST_RATE_LIMIT_PER_HOUR: int = int(os.getenv("UNLOCK_REQUEST_RATE_LIMIT_PER_HOUR", "3"))

    # Server-side transactional email (never expose these as VITE_* variables)
    TRANSACTIONAL_EMAIL_ENABLED: bool = os.getenv("TRANSACTIONAL_EMAIL_ENABLED", "false").lower() == "true"
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "graph")
    TRANSACTIONAL_FROM_EMAIL: str = os.getenv("TRANSACTIONAL_FROM_EMAIL", "")
    FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
    EMAIL_PAYLOAD_ENCRYPTION_KEY: str = os.getenv("EMAIL_PAYLOAD_ENCRYPTION_KEY", "")
    ACTIVATION_TOKEN_EXPIRY_MINUTES: int = int(os.getenv("ACTIVATION_TOKEN_EXPIRY_MINUTES", "1440"))
    EMAIL_MAX_ATTEMPTS: int = int(os.getenv("EMAIL_MAX_ATTEMPTS", "8"))
    EMAIL_BASE_RETRY_SECONDS: int = int(os.getenv("EMAIL_BASE_RETRY_SECONDS", "30"))
    EMAIL_MAX_RETRY_SECONDS: int = int(os.getenv("EMAIL_MAX_RETRY_SECONDS", "3600"))
    EMAIL_LOCK_TIMEOUT_SECONDS: int = int(os.getenv("EMAIL_LOCK_TIMEOUT_SECONDS", "300"))
    EMAIL_WORKER_POLL_SECONDS: int = int(os.getenv("EMAIL_WORKER_POLL_SECONDS", "5"))
    GRAPH_HTTP_TIMEOUT_SECONDS: float = float(os.getenv("GRAPH_HTTP_TIMEOUT_SECONDS", "30"))
    GRAPH_AUTH_MODE: str = os.getenv("GRAPH_AUTH_MODE", "client_secret")
    GRAPH_TENANT_ID: str = os.getenv("GRAPH_TENANT_ID", "")
    GRAPH_CLIENT_ID: str = os.getenv("GRAPH_CLIENT_ID", "")
    GRAPH_CLIENT_SECRET: str = os.getenv("GRAPH_CLIENT_SECRET", "")
    GRAPH_CERTIFICATE_PATH: str = os.getenv("GRAPH_CERTIFICATE_PATH", "")
    GRAPH_CERTIFICATE_PASSWORD: str = os.getenv("GRAPH_CERTIFICATE_PASSWORD", "")
    GRAPH_MANAGED_IDENTITY_CLIENT_ID: str = os.getenv("GRAPH_MANAGED_IDENTITY_CLIENT_ID", "")


settings = Settings()
