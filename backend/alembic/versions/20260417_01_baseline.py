"""baseline schema and persistent document registry

Revision ID: 20260417_01
Revises:
Create Date: 2026-04-17 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260417_01"
down_revision = None
branch_labels = None
depends_on = None


def has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def ensure_index(inspector, table_name: str, index_name: str, columns: list[str], *, unique: bool = False) -> None:
    existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name in existing_indexes:
        return

    op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not has_table(inspector, "users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("full_name", sa.String(), nullable=False),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        inspector = sa.inspect(bind)
    ensure_index(inspector, "users", "ix_users_email", ["email"], unique=True)

    if not has_table(inspector, "auth_sessions"):
        op.create_table(
            "auth_sessions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
        )
        inspector = sa.inspect(bind)
    ensure_index(inspector, "auth_sessions", "ix_auth_sessions_user_id", ["user_id"])
    ensure_index(inspector, "auth_sessions", "ix_auth_sessions_token_hash", ["token_hash"], unique=True)

    if not has_table(inspector, "password_reset_tokens"):
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
        )
        inspector = sa.inspect(bind)
    ensure_index(inspector, "password_reset_tokens", "ix_password_reset_tokens_user_id", ["user_id"])
    ensure_index(
        inspector,
        "password_reset_tokens",
        "ix_password_reset_tokens_token_hash",
        ["token_hash"],
        unique=True,
    )

    if not has_table(inspector, "chat_sessions"):
        op.create_table(
            "chat_sessions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("chat_id", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("active_doc_ids_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("messages_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("user_id", "chat_id", name="uq_chat_sessions_user_chat"),
        )
        inspector = sa.inspect(bind)
    ensure_index(inspector, "chat_sessions", "ix_chat_sessions_user_id", ["user_id"])
    ensure_index(inspector, "chat_sessions", "ix_chat_sessions_chat_id", ["chat_id"])
    ensure_index(inspector, "chat_sessions", "ix_chat_sessions_updated_at", ["updated_at"])
    ensure_index(inspector, "chat_sessions", "ix_chat_sessions_deleted_at", ["deleted_at"])

    if not has_table(inspector, "documents"):
        op.create_table(
            "documents",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("filename", sa.String(), nullable=False),
            sa.Column("storage_provider", sa.String(), nullable=True, server_default="local"),
            sa.Column("storage_path", sa.String(), nullable=True),
            sa.Column("faiss_path", sa.String(), nullable=True),
            sa.Column("json_path", sa.String(), nullable=True),
            sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rag_mode", sa.String(), nullable=False, server_default="lite"),
            sa.Column("vector_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("preview", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )
        inspector = sa.inspect(bind)
    else:
        existing_columns = {column["name"] for column in inspector.get_columns("documents")}
        with op.batch_alter_table("documents") as batch_op:
            if "user_id" not in existing_columns:
                batch_op.add_column(sa.Column("user_id", sa.String(), nullable=True))
            if "storage_provider" not in existing_columns:
                batch_op.add_column(sa.Column("storage_provider", sa.String(), nullable=True, server_default="local"))
            if "storage_path" not in existing_columns:
                batch_op.add_column(sa.Column("storage_path", sa.String(), nullable=True))
            if "byte_size" not in existing_columns:
                batch_op.add_column(sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"))
            if "chunk_count" not in existing_columns:
                batch_op.add_column(sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"))
            if "page_count" not in existing_columns:
                batch_op.add_column(sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"))
            if "rag_mode" not in existing_columns:
                batch_op.add_column(sa.Column("rag_mode", sa.String(), nullable=False, server_default="lite"))
            if "vector_ready" not in existing_columns:
                batch_op.add_column(sa.Column("vector_ready", sa.Boolean(), nullable=False, server_default=sa.false()))
            if "preview" not in existing_columns:
                batch_op.add_column(sa.Column("preview", sa.Text(), nullable=False, server_default=""))
            if "updated_at" not in existing_columns:
                batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
            if "uploaded_at" not in existing_columns:
                batch_op.add_column(sa.Column("uploaded_at", sa.DateTime(), nullable=True))
            if "deleted_at" not in existing_columns:
                batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        bind.execute(sa.text("UPDATE documents SET storage_provider = COALESCE(storage_provider, 'local')"))
        bind.execute(sa.text("UPDATE documents SET byte_size = COALESCE(byte_size, 0)"))
        bind.execute(sa.text("UPDATE documents SET chunk_count = COALESCE(chunk_count, 0)"))
        bind.execute(sa.text("UPDATE documents SET page_count = COALESCE(page_count, 0)"))
        bind.execute(sa.text("UPDATE documents SET rag_mode = COALESCE(rag_mode, 'lite')"))
        bind.execute(sa.text("UPDATE documents SET vector_ready = COALESCE(vector_ready, 0)"))
        bind.execute(sa.text("UPDATE documents SET preview = COALESCE(preview, '')"))
        bind.execute(sa.text("UPDATE documents SET updated_at = COALESCE(updated_at, created_at)"))
        bind.execute(sa.text("UPDATE documents SET uploaded_at = COALESCE(uploaded_at, created_at)"))
        inspector = sa.inspect(bind)

    ensure_index(inspector, "documents", "ix_documents_user_id", ["user_id"])
    ensure_index(inspector, "documents", "ix_documents_updated_at", ["updated_at"])
    ensure_index(inspector, "documents", "ix_documents_uploaded_at", ["uploaded_at"])
    ensure_index(inspector, "documents", "ix_documents_deleted_at", ["deleted_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in (
        "documents",
        "chat_sessions",
        "password_reset_tokens",
        "auth_sessions",
        "users",
    ):
        if has_table(inspector, table_name):
            op.drop_table(table_name)
            inspector = sa.inspect(bind)
