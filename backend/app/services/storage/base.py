"""Abstract interface for all storage providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
import re


@dataclass
class UploadResult:
    storage_path: str
    stored_file_name: str
    file_url: str | None


class StorageProvider(ABC):
    @abstractmethod
    def upload_file(self, file_bytes: bytes, folder_path: str, stored_file_name: str) -> UploadResult:
        """Store file_bytes at folder_path/stored_file_name."""

    @abstractmethod
    def download_file(self, storage_path: str) -> bytes:
        """Read and return file bytes from storage_path."""

    @abstractmethod
    def delete_file(self, storage_path: str) -> None:
        """Physically delete the file at storage_path."""

    @abstractmethod
    def file_exists(self, storage_path: str) -> bool:
        """Return True if the file exists at storage_path."""

    @staticmethod
    def generate_safe_filename(original_filename: str, prefix_uuid: str) -> str:
        name = os.path.basename(original_filename or "")
        name = re.sub(r"[^\w\s\-.]", "", name)
        name = re.sub(r"\s+", "_", name.strip())[:100]
        root, ext = os.path.splitext(name)
        ext = ext.lower()
        safe = f"{prefix_uuid}_{root}{ext}" if root else f"{prefix_uuid}{ext}"
        if "/" in safe or "\\" in safe or ".." in safe:
            raise ValueError(f"Filename sanitization failed: {safe}")
        return safe
