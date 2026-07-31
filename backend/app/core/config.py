"""
Core configuration — loads environment variables.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ENV_FILE = BACKEND_ROOT / ".env"

# Always load server configuration from backend/.env, regardless of the
# directory used to start Uvicorn, pytest, or a worker. Explicit process
# environment variables continue to take precedence.
load_dotenv(dotenv_path=BACKEND_ENV_FILE, override=False)


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
    AUTH_JWT_SECRET: str = os.getenv("AUTH_JWT_SECRET", "")
    AUTH_JWT_ISSUER: str = os.getenv("AUTH_JWT_ISSUER", "reknew-orbit-api")
    AUTH_JWT_AUDIENCE: str = os.getenv("AUTH_JWT_AUDIENCE", "reknew-orbit-web")
    AUTH_ACCESS_TOKEN_MINUTES: int = int(os.getenv("AUTH_ACCESS_TOKEN_MINUTES", "15"))
    AI_CHAT_REQUESTS_PER_MINUTE: int = int(os.getenv("AI_CHAT_REQUESTS_PER_MINUTE", "10"))
    AI_CHAT_REQUESTS_PER_DAY: int = int(os.getenv("AI_CHAT_REQUESTS_PER_DAY", "100"))
    AI_CHAT_TIMEOUT_SECONDS: float = float(os.getenv("AI_CHAT_TIMEOUT_SECONDS", "15"))
    AI_CHAT_MAX_REQUEST_BYTES: int = int(os.getenv("AI_CHAT_MAX_REQUEST_BYTES", "4096"))
    AI_CHAT_MAX_RESPONSE_BYTES: int = int(os.getenv("AI_CHAT_MAX_RESPONSE_BYTES", "24576"))
    AI_CHAT_MAX_BALANCES: int = int(os.getenv("AI_CHAT_MAX_BALANCES", "20"))
    AI_CONVERSATION_RETENTION_DAYS: int = int(
        os.getenv("AI_CONVERSATION_RETENTION_DAYS", "90")
    )
    AI_CONVERSATION_HISTORY_LIMIT: int = int(
        os.getenv("AI_CONVERSATION_HISTORY_LIMIT", "50")
    )
    # Contextual LLM Phase A. These settings are backend-only and shadow mode
    # cannot influence routing, tools, workflows, or user-visible responses.
    CONTEXTUAL_LLM_ENABLED: bool = (
        os.getenv("CONTEXTUAL_LLM_ENABLED", "false").lower() == "true"
    )
    CONTEXTUAL_LLM_SHADOW_MODE: bool = (
        os.getenv("CONTEXTUAL_LLM_SHADOW_MODE", "true").lower() == "true"
    )
    CONTEXTUAL_LLM_PROVIDER: str = os.getenv(
        "CONTEXTUAL_LLM_PROVIDER", "disabled"
    )
    CONTEXTUAL_LLM_MODEL: str = os.getenv("CONTEXTUAL_LLM_MODEL", "")
    CONTEXTUAL_LLM_API_KEY: str = os.getenv("CONTEXTUAL_LLM_API_KEY", "")
    CONTEXTUAL_LLM_BASE_URL: str = os.getenv(
        "CONTEXTUAL_LLM_BASE_URL", "https://api.openai.com/v1"
    )
    CONTEXTUAL_LLM_TIMEOUT_SECONDS: float = float(
        os.getenv("CONTEXTUAL_LLM_TIMEOUT_SECONDS", "4")
    )
    CONTEXTUAL_LLM_RETRY_COUNT: int = int(
        os.getenv("CONTEXTUAL_LLM_RETRY_COUNT", "1")
    )
    CONTEXTUAL_LLM_MAX_INPUT_TOKENS: int = int(
        os.getenv("CONTEXTUAL_LLM_MAX_INPUT_TOKENS", "6000")
    )
    CONTEXTUAL_LLM_MAX_OUTPUT_TOKENS: int = int(
        os.getenv("CONTEXTUAL_LLM_MAX_OUTPUT_TOKENS", "700")
    )
    CONTEXTUAL_LLM_TEMPERATURE: float = float(
        os.getenv("CONTEXTUAL_LLM_TEMPERATURE", "0")
    )
    CONTEXTUAL_LLM_PROMPT_VERSION: str = os.getenv(
        "CONTEXTUAL_LLM_PROMPT_VERSION",
        "contextual_leave_interpreter_v2",
    )
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


def contextual_provider_configuration_errors(
    *,
    require_enabled_configuration: bool = False,
) -> list[str]:
    """Return safe configuration errors without returning credential values."""
    if (
        not settings.CONTEXTUAL_LLM_ENABLED
        and not require_enabled_configuration
    ):
        return []
    errors: list[str] = []
    if not settings.CONTEXTUAL_LLM_SHADOW_MODE:
        errors.append(
            "CONTEXTUAL_LLM_SHADOW_MODE must remain true in Phase A."
        )
    provider = settings.CONTEXTUAL_LLM_PROVIDER.strip().lower()
    if provider not in {"openai", "openai_compatible"}:
        errors.append(
            "CONTEXTUAL_LLM_PROVIDER must be openai or openai_compatible "
            "when contextual interpretation is enabled."
        )
    if not settings.CONTEXTUAL_LLM_MODEL.strip():
        errors.append("CONTEXTUAL_LLM_MODEL is required.")
    if not settings.CONTEXTUAL_LLM_API_KEY.strip():
        errors.append("CONTEXTUAL_LLM_API_KEY is required.")
    parsed_url = urlparse(settings.CONTEXTUAL_LLM_BASE_URL.strip())
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        errors.append("CONTEXTUAL_LLM_BASE_URL must be a valid HTTPS URL.")
    if not 0.25 <= settings.CONTEXTUAL_LLM_TIMEOUT_SECONDS <= 15:
        errors.append(
            "CONTEXTUAL_LLM_TIMEOUT_SECONDS must be between 0.25 and 15."
        )
    if settings.CONTEXTUAL_LLM_RETRY_COUNT not in {0, 1}:
        errors.append("CONTEXTUAL_LLM_RETRY_COUNT must be 0 or 1.")
    if settings.CONTEXTUAL_LLM_MAX_INPUT_TOKENS < 3000:
        errors.append(
            "CONTEXTUAL_LLM_MAX_INPUT_TOKENS must be at least 3000."
        )
    prompt_path = (
        BACKEND_ROOT
        / "app"
        / "ai"
        / "prompt_templates"
        / f"{settings.CONTEXTUAL_LLM_PROMPT_VERSION}.json"
    )
    if not prompt_path.is_file():
        errors.append(
            "CONTEXTUAL_LLM_PROMPT_VERSION does not name an installed "
            "prompt template."
        )
    return errors


def validate_security_settings() -> None:
    """Fail startup when required server-side security settings are invalid."""
    jwt_secret = settings.AUTH_JWT_SECRET.strip()
    if not jwt_secret:
        raise RuntimeError(
            "AUTH_JWT_SECRET is required. "
            f"Set it in {BACKEND_ENV_FILE} or in the backend process environment."
        )
    if len(jwt_secret) < 32:
        raise RuntimeError(
            "AUTH_JWT_SECRET must be at least 32 characters long. "
            f"Update it in {BACKEND_ENV_FILE} or in the backend process environment."
        )
    provider_errors = contextual_provider_configuration_errors()
    if provider_errors:
        raise RuntimeError(
            "Invalid contextual LLM configuration: "
            + " ".join(provider_errors)
        )
