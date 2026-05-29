from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db_session
from app.core.security import hash_api_key
from app.db.models import Base, User
from app.main import create_app


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def api_key() -> str:
    return "tf_test_api_key"


@pytest.fixture()
def user(session: Session, api_key: str) -> User:
    user = User(name="Test User", api_key_hash=hash_api_key(api_key))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture()
def client(
    session: Session,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    import app.api.routes as task_routes

    monkeypatch.setattr(task_routes, "enqueue_summarize_task", lambda task_id: None)
    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
