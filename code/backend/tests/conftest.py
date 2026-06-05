import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.main import app
from app.services.store import STORE


@pytest.fixture(autouse=True)
def reset_store():
    STORE.reset()
    yield
    STORE.reset()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def test_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

