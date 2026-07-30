"""SQLAlchemy configuration for the local SQLite database."""

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker


DATABASE_PATH = Path(__file__).resolve().parents[2] / "poker.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine: Engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _configure_sqlite_connection(dbapi_connection: object, _: object) -> None:
    """Enable SQLite settings required for concurrent local access."""
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
)


class Base(DeclarativeBase):
    """Base class for every ORM model."""

