from __future__ import annotations

import hashlib
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path, PurePosixPath
from typing import BinaryIO

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class FileStorageError(Exception):
    pass


class FileTooLargeError(FileStorageError):
    pass


class EmptyFileError(FileStorageError):
    pass


class FileStorageService(ABC):
    provider_name = "UNKNOWN"

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

    def create_download_url(
        self,
        storage_path: str,
        *,
        filename: str,
        content_type: str,
        expires_seconds: int,
    ) -> str | None:
        return None


class LocalFileStorage(FileStorageService):
    provider_name = "LOCAL"

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


class S3FileStorage(FileStorageService):
    provider_name = "S3"

    def __init__(self, bucket: str, prefix: str = "documents"):
        if not bucket.strip():
            raise ValueError("S3 bucket is required")
        self.bucket = bucket.strip()
        self.prefix = prefix.strip("/")
        self.client = boto3.client("s3")

    def _key(self, storage_path: str) -> str:
        relative = PurePosixPath(storage_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise FileStorageError("Invalid storage path")
        normalized = str(relative).lstrip("/")
        return f"{self.prefix}/{normalized}" if self.prefix else normalized

    def save(
        self, source: BinaryIO, storage_path: str, *, max_bytes: int
    ) -> tuple[int, str]:
        size = 0
        digest = hashlib.sha256()
        temporary = tempfile.SpooledTemporaryFile(max_size=min(max_bytes, 5 * 1024 * 1024))
        try:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise FileTooLargeError("Document exceeds configured size limit")
                digest.update(chunk)
                temporary.write(chunk)
            if size == 0:
                raise EmptyFileError("Document must not be empty")
            temporary.seek(0)
            self.client.upload_fileobj(temporary, self.bucket, self._key(storage_path))
        except (BotoCoreError, ClientError) as exc:
            raise FileStorageError("S3 document upload failed") from exc
        finally:
            temporary.close()
        return size, digest.hexdigest()

    def open(self, storage_path: str) -> BinaryIO:
        try:
            return self.client.get_object(
                Bucket=self.bucket,
                Key=self._key(storage_path),
            )["Body"]
        except (BotoCoreError, ClientError) as exc:
            raise FileStorageError("S3 document download failed") from exc

    def exists(self, storage_path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(storage_path))
            return True
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                return False
            raise FileStorageError("S3 document lookup failed") from exc
        except BotoCoreError as exc:
            raise FileStorageError("S3 document lookup failed") from exc

    def delete(self, storage_path: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._key(storage_path))
        except (BotoCoreError, ClientError) as exc:
            raise FileStorageError("S3 document deletion failed") from exc

    def create_download_url(
        self,
        storage_path: str,
        *,
        filename: str,
        content_type: str,
        expires_seconds: int,
    ) -> str:
        safe_filename = filename.replace('"', "_")
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": self._key(storage_path),
                    "ResponseContentType": content_type,
                    "ResponseContentDisposition": f'attachment; filename="{safe_filename}"',
                },
                ExpiresIn=expires_seconds,
            )
        except (BotoCoreError, ClientError) as exc:
            raise FileStorageError("Unable to create S3 download URL") from exc
