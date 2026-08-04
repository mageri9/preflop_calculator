from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker
from src.core.config import settings

engine: Engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

@event.listens_for(engine, "connect")
def _configure_sqlite_connection(dbapi_connection: object, _: object) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
)

class Base(DeclarativeBase):
    """Base class for every ORM model."""