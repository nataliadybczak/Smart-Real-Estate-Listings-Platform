from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


def _connect_args() -> dict[str, Any]:
    ssl_ca = get_settings().database_ssl_ca
    return {"ssl": {"ca": ssl_ca}} if ssl_ca else {}


engine = create_engine(
    get_settings().database_url,
    connect_args=_connect_args(),
    pool_pre_ping=True,  # check the connection before use
    pool_recycle=280,  # renew connections before MySQL closes them
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per HTTP request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]
