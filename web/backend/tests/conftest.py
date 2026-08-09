import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.security import hash_password


@pytest.fixture()
def db_factory(tmp_path):
    # isolated per-test SQLite DB file — no shared state across tests, and
    # never touches the real web/backend/data/plan_gen.db
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    return TestSessionLocal


@pytest.fixture()
def client(db_factory, tmp_path, monkeypatch):
    def override_get_db():
        db = db_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # pipeline_runner.run_generation() runs in a background thread and opens
    # its own DB session via the module-level SessionLocal — it doesn't go
    # through FastAPI's dependency injection, so the override above alone
    # doesn't reach it. Patch it directly, and redirect its file dirs into
    # tmp_path so tests never touch the real web/backend/data/.
    from app import pipeline_runner
    monkeypatch.setattr(pipeline_runner, "SessionLocal", db_factory)
    monkeypatch.setattr(pipeline_runner, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(pipeline_runner, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(pipeline_runner, "IMAGE_DIR", tmp_path / "images")

    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(db_factory):
    def _make_user(email="user@example.com", password="hunter2", name="테스트유저"):
        db = db_factory()
        try:
            user = User(email=email, password_hash=hash_password(password), name=name)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
        finally:
            db.close()
    return _make_user
