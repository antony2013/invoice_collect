from __future__ import annotations

from io import BytesIO
from typing import Annotated

from fastapi import Depends, HTTPException, status
from minio import Minio
from minio.error import MinioException, S3Error
from urllib3.exceptions import HTTPError as UrllibHTTPError

from app.config import Settings, get_settings


class MinioService:
    """Thin wrapper around the MinIO client with a lazily-created connection."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Minio | None = None

    @property
    def client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                self._settings.minio_endpoint,
                access_key=self._settings.minio_access_key,
                secret_key=self._settings.minio_secret_key,
                secure=self._settings.minio_secure,
            )
        return self._client

    @property
    def bucket(self) -> str:
        return self._settings.minio_bucket

    def upload_object(
        self,
        *,
        object_key: str,
        data: bytes,
        content_type: str | None,
    ) -> None:
        try:
            self.client.put_object(
                self.bucket,
                object_key,
                BytesIO(data),
                length=len(data),
                content_type=content_type or "application/octet-stream",
            )
        except S3Error as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Object storage error: {exc.message or 'unavailable'}",
            ) from exc
        except (MinioException, OSError, ValueError, UrllibHTTPError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Object storage is unavailable. Try again later.",
            ) from exc

    def get_object(self, *, object_key: str) -> bytes:
        try:
            response = self.client.get_object(self.bucket, object_key)
        except S3Error as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Object storage error: {exc.message or 'unavailable'}",
            ) from exc
        except (MinioException, OSError, ValueError, UrllibHTTPError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Object storage is unavailable. Try again later.",
            ) from exc
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def remove_object(self, *, object_key: str) -> None:
        try:
            self.client.remove_object(self.bucket, object_key)
        except S3Error as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Object storage error: {exc.message or 'unavailable'}",
            ) from exc
        except (MinioException, OSError, ValueError, UrllibHTTPError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Object storage is unavailable. Try again later.",
            ) from exc

    def object_exists(self, *, object_key: str) -> bool:
        try:
            return self.client.stat_object(self.bucket, object_key) is not None
        except S3Error:
            return False
        except (MinioException, OSError, ValueError, UrllibHTTPError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Object storage is unavailable. Try again later.",
            ) from exc


_service: MinioService | None = None


def get_minio_service() -> MinioService:
    """FastAPI dependency returning a shared MinioService instance."""
    global _service
    if _service is None:
        _service = MinioService(get_settings())
    return _service


MinioDep = Annotated[MinioService, Depends(get_minio_service)]
