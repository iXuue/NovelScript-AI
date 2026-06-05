from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def create_app_engine(database_url: str | None = None):
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


_engine = None
SessionLocal = sessionmaker(autoflush=False, autocommit=False)


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_app_engine()
        SessionLocal.configure(bind=_engine)
    return _engine


def get_db() -> Generator[Session, None, None]:
    get_engine()
    with SessionLocal() as session:
        yield session
