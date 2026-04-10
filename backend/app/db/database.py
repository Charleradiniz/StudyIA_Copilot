from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

Base = declarative_base()
engine: Engine | None = None
SessionLocal: sessionmaker | None = None


def configure_database(database_url: str | None = None) -> Engine | None:
    global engine
    global SessionLocal

    target_url = database_url or DATABASE_URL

    if engine is not None:
        engine.dispose()

    if not target_url:
        engine = None
        SessionLocal = None
        return None

    engine_kwargs = (
        {"connect_args": {"check_same_thread": False}}
        if target_url.startswith("sqlite")
        else {}
    )
    engine = create_engine(target_url, **engine_kwargs)
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    return engine


configure_database()
