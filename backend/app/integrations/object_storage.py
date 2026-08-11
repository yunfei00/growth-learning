"""MinIO-compatible object storage client construction."""

from minio import Minio

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
