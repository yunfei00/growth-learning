"""MinIO-compatible private object storage construction."""

import io
from typing import Protocol

from anyio import to_thread
from minio import Minio
from minio.error import S3Error

from app.core.config import Settings, get_settings


class ObjectStorageConfigurationError(ValueError):
    """Raised when object storage credentials are missing."""


def build_minio_client(settings: Settings | None = None) -> Minio:
    """Build a MinIO client without performing startup I/O."""
    app_settings = settings or get_settings()
    access_key = app_settings.minio_access_key.get_secret_value()
    secret_key = app_settings.minio_secret_key.get_secret_value()
    if not access_key or not secret_key:
        raise ObjectStorageConfigurationError(
            "MINIO_ACCESS_KEY and MINIO_SECRET_KEY are required for object storage"
        )

    return Minio(
        app_settings.minio_endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=app_settings.minio_secure,
    )


class PrivateObjectStorage(Protocol):
    """Small async surface used by household-private experiment media."""

    async def put(self, object_key: str, content: bytes, mime_type: str) -> None: ...

    async def read(self, object_key: str) -> bytes: ...

    async def remove(self, object_key: str) -> None: ...


class MinioPrivateObjectStorage:
    """Private-bucket adapter; objects are streamed only after household authorization."""

    def __init__(self, client: Minio, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def _ensure_bucket(self) -> None:
        if self.client.bucket_exists(self.bucket):
            return
        try:
            self.client.make_bucket(self.bucket)
        except S3Error as error:
            if error.code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                raise

    async def put(self, object_key: str, content: bytes, mime_type: str) -> None:
        def write() -> None:
            self._ensure_bucket()
            self.client.put_object(
                self.bucket,
                object_key,
                io.BytesIO(content),
                len(content),
                content_type=mime_type,
            )

        await to_thread.run_sync(write)

    async def read(self, object_key: str) -> bytes:
        def fetch() -> bytes:
            response = self.client.get_object(self.bucket, object_key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await to_thread.run_sync(fetch)

    async def remove(self, object_key: str) -> None:
        await to_thread.run_sync(self.client.remove_object, self.bucket, object_key)


def build_private_object_storage(settings: Settings | None = None) -> MinioPrivateObjectStorage:
    app_settings = settings or get_settings()
    return MinioPrivateObjectStorage(build_minio_client(app_settings), app_settings.minio_bucket)
