from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db.database import Base
from app.models import auth_session, chat_session, document, password_reset_token, user  # noqa: F401


def _ensure_column(
    connection,
    table_name: str,
    existing_columns: set[str],
    column_name: str,
    ddl: str,
) -> bool:
    if column_name in existing_columns:
        return False

    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
    existing_columns.add(column_name)
    return True


def _ensure_indexes(connection) -> None:
    index_statements = [
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)",
        "CREATE INDEX IF NOT EXISTS ix_auth_sessions_user_id ON auth_sessions (user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_auth_sessions_token_hash ON auth_sessions (token_hash)",
        "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id ON password_reset_tokens (user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash)",
        "CREATE INDEX IF NOT EXISTS ix_chat_sessions_user_id ON chat_sessions (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_chat_sessions_chat_id ON chat_sessions (chat_id)",
        "CREATE INDEX IF NOT EXISTS ix_chat_sessions_updated_at ON chat_sessions (updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_chat_sessions_deleted_at ON chat_sessions (deleted_at)",
        "CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_documents_updated_at ON documents (updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_documents_uploaded_at ON documents (uploaded_at)",
        "CREATE INDEX IF NOT EXISTS ix_documents_deleted_at ON documents (deleted_at)",
    ]

    for statement in index_statements:
        connection.execute(text(statement))


def ensure_database_schema(database_engine: Engine) -> None:
    if database_engine is None:
        return

    Base.metadata.create_all(bind=database_engine)

    with database_engine.begin() as connection:
        inspector = inspect(connection)
        if "documents" not in inspector.get_table_names():
            _ensure_indexes(connection)
            return

        existing_columns = {
            column["name"]
            for column in inspector.get_columns("documents")
        }
        boolean_false_literal = "FALSE" if connection.dialect.name == "postgresql" else "0"

        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "user_id",
            "user_id VARCHAR",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "storage_provider",
            "storage_provider VARCHAR DEFAULT 'local'",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "storage_path",
            "storage_path VARCHAR",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "faiss_path",
            "faiss_path VARCHAR",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "json_path",
            "json_path VARCHAR",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "byte_size",
            "byte_size INTEGER NOT NULL DEFAULT 0",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "chunk_count",
            "chunk_count INTEGER NOT NULL DEFAULT 0",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "page_count",
            "page_count INTEGER NOT NULL DEFAULT 0",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "rag_mode",
            "rag_mode VARCHAR NOT NULL DEFAULT 'lite'",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "vector_ready",
            f"vector_ready BOOLEAN NOT NULL DEFAULT {boolean_false_literal}",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "preview",
            "preview TEXT NOT NULL DEFAULT ''",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "updated_at",
            "updated_at DATETIME",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "uploaded_at",
            "uploaded_at DATETIME",
        )
        _ensure_column(
            connection,
            "documents",
            existing_columns,
            "deleted_at",
            "deleted_at DATETIME",
        )

        created_at_reference = "created_at" if "created_at" in existing_columns else "CURRENT_TIMESTAMP"
        connection.execute(text(
            "UPDATE documents SET storage_provider = COALESCE(storage_provider, 'local')"
        ))
        connection.execute(text(
            "UPDATE documents SET byte_size = COALESCE(byte_size, 0)"
        ))
        connection.execute(text(
            "UPDATE documents SET chunk_count = COALESCE(chunk_count, 0)"
        ))
        connection.execute(text(
            "UPDATE documents SET page_count = COALESCE(page_count, 0)"
        ))
        connection.execute(text(
            "UPDATE documents SET rag_mode = COALESCE(rag_mode, 'lite')"
        ))
        connection.execute(text(
            f"UPDATE documents SET vector_ready = COALESCE(vector_ready, {boolean_false_literal})"
        ))
        connection.execute(text(
            "UPDATE documents SET preview = COALESCE(preview, '')"
        ))
        connection.execute(text(
            f"UPDATE documents SET updated_at = COALESCE(updated_at, {created_at_reference}, CURRENT_TIMESTAMP)"
        ))
        connection.execute(text(
            f"UPDATE documents SET uploaded_at = COALESCE(uploaded_at, {created_at_reference}, CURRENT_TIMESTAMP)"
        ))

        _ensure_indexes(connection)
