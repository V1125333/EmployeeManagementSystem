"""Local filesystem storage provider."""

import os

from app.services.storage.base import StorageProvider, UploadResult


class LocalStorageProvider(StorageProvider):
    def __init__(self, upload_root: str):
        self.upload_root = upload_root

    def _abs(self, storage_path: str) -> str:
        abs_path = os.path.realpath(os.path.join(self.upload_root, storage_path))
        abs_root = os.path.realpath(self.upload_root)
        if not abs_path.startswith(abs_root + os.sep) and abs_path != abs_root:
            raise ValueError(f"Path traversal detected: {storage_path}")
        return abs_path

    def upload_file(self, file_bytes: bytes, folder_path: str, stored_file_name: str) -> UploadResult:
        abs_folder = self._abs(folder_path)
        os.makedirs(abs_folder, exist_ok=True)
        abs_path = os.path.join(abs_folder, stored_file_name)
        if os.path.exists(abs_path):
            raise FileExistsError(f"File already exists: {abs_path}")
        with open(abs_path, "wb") as handle:
            handle.write(file_bytes)
        storage_path = os.path.join(folder_path, stored_file_name).replace("\\", "/")
        return UploadResult(storage_path=storage_path, stored_file_name=stored_file_name, file_url=None)

    def download_file(self, storage_path: str) -> bytes:
        abs_path = self._abs(storage_path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"File not found: {storage_path}")
        with open(abs_path, "rb") as handle:
            return handle.read()

    def delete_file(self, storage_path: str) -> None:
        abs_path = self._abs(storage_path)
        if os.path.isfile(abs_path):
            os.remove(abs_path)

    def file_exists(self, storage_path: str) -> bool:
        try:
            abs_path = self._abs(storage_path)
            return os.path.isfile(abs_path)
        except ValueError:
            return False
