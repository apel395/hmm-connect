from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path, PurePosixPath
from typing import BinaryIO


class FileStorageError(Exception):
    pass


class FileTooLargeError(FileStorageError):
    pass


class EmptyFileError(FileStorageError):
    pass


class FileStorageService(ABC):
    @abstractmethod
    def save(
        self, source: BinaryIO, storage_path: str, *, max_bytes: int
    ) -> tuple[int, str]:
        raise NotImplementedError

    @abstractmethod
    def open(self, storage_path: str) -> BinaryIO:
        raise NotImplementedError

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        raise NotImplementedError


class LocalFileStorage(FileStorageService):
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()

    def _resolve(self, storage_path: str) -> Path:
        relative = PurePosixPath(storage_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise FileStorageError("Invalid storage path")
        target = (self.root / Path(*relative.parts)).resolve()
        if not target.is_relative_to(self.root):
            raise FileStorageError("Invalid storage path")
        return target

    def save(
        self, source: BinaryIO, storage_path: str, *, max_bytes: int
    ) -> tuple[int, str]:
        target = self._resolve(storage_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        digest = hashlib.sha256()
        try:
            with target.open("xb") as destination:
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise FileTooLargeError("Document exceeds configured size limit")
                    digest.update(chunk)
                    destination.write(chunk)
            if size == 0:
                raise EmptyFileError("Document must not be empty")
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return size, digest.hexdigest()

    def open(self, storage_path: str) -> BinaryIO:
        return self._resolve(storage_path).open("rb")

    def exists(self, storage_path: str) -> bool:
        return self._resolve(storage_path).is_file()

    def delete(self, storage_path: str) -> None:
        self._resolve(storage_path).unlink(missing_ok=True)
