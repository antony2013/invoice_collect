from __future__ import annotations

import os
from collections.abc import Generator

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-bytes-long"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.core.minio import get_minio_service
from app.database import Base, get_db
from app.main import app

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


class FakeMinioService:
    """In-memory stand-in for MinioService used by tests."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str | None]] = {}

    @property
    def bucket(self) -> str:
        return "test-bucket"

    def upload_object(
        self,
        *,
        object_key: str,
        data: bytes,
        content_type: str | None,
    ) -> None:
        self.objects[object_key] = (data, content_type)

    def get_object(self, *, object_key: str) -> bytes:
        try:
            return self.objects[object_key][0]
        except KeyError as exc:
            raise KeyError(f"object {object_key} not found") from exc

    def remove_object(self, *, object_key: str) -> None:
        self.objects.pop(object_key, None)

    def object_exists(self, *, object_key: str) -> bool:
        return object_key in self.objects


@pytest.fixture(autouse=True)
def fake_minio() -> Generator[FakeMinioService, None, None]:
    fake = FakeMinioService()
    app.dependency_overrides[get_minio_service] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_minio_service, None)


@pytest.fixture(autouse=True)
def _clean_database() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
