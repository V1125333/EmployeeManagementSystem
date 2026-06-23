"""Configured storage provider factory."""

from functools import lru_cache

from app.core.config import settings
from app.services.storage.base import StorageProvider
from app.services.storage.local_storage import LocalStorageProvider


@lru_cache(maxsize=1)
def get_storage() -> StorageProvider:
    provider = settings.STORAGE_PROVIDER.lower()
    if provider == "local":
        return LocalStorageProvider(upload_root=settings.LOCAL_UPLOAD_ROOT)
    raise ValueError(f"Unknown storage provider: '{provider}'. Set STORAGE_PROVIDER in .env")
