from pathlib import Path

from app.db import database as db_module
from app.db.schema import ensure_database_schema


def build_alembic_config(database_url: str | None = None):
    try:
        from alembic.config import Config
    except ImportError as exc:  # pragma: no cover - depends on runtime installation
        raise RuntimeError("Alembic is not installed in this environment.") from exc

    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))

    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)
    elif db_module.engine is not None:
        config.set_main_option("sqlalchemy.url", str(db_module.engine.url))

    return config


def run_database_migrations(database_url: str | None = None) -> None:
    current_engine = db_module.engine
    current_url = str(current_engine.url) if current_engine is not None else None

    if database_url and database_url != current_url:
        current_engine = db_module.configure_database(database_url)

    if current_engine is None:
        return

    target_url = database_url or str(current_engine.url)
    if target_url in {"sqlite://", "sqlite:///:memory:"}:
        ensure_database_schema(current_engine)
        return

    try:
        from alembic import command
    except ImportError:
        ensure_database_schema(current_engine)
        return

    config = build_alembic_config(str(current_engine.url))
    command.upgrade(config, "head")
