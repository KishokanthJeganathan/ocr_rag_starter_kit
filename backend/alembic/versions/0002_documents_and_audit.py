"""documents + audit_log, with row-level security

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_TABLES = ("documents", "audit_log")


def upgrade() -> None:
    op.execute("CREATE TYPE source_format AS ENUM ('pdf', 'png', 'jpg', 'docx')")
    op.execute("CREATE TYPE document_status AS ENUM ('queued', 'processing', 'failed')")
    source_format = postgresql.ENUM(name="source_format", create_type=False)
    document_status = postgresql.ENUM(name="document_status", create_type=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("source_format", source_format, nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("is_scanned", sa.Boolean(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("status", document_status, server_default="queued", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_documents_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"], ["matters.id"], name=op.f("fk_documents_matter_id_matters"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("tenant_id", "content_sha256", name="uq_documents_tenant_sha256"),
    )
    op.create_index(op.f("ix_documents_tenant_id"), "documents", ["tenant_id"])
    op.create_index(op.f("ix_documents_matter_id"), "documents", ["matter_id"])
    op.create_index(op.f("ix_documents_status"), "documents", ["status"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("actor", sa.String(length=255), server_default="system", nullable=False),
        sa.Column("event", sa.String(length=128), nullable=False),
        sa.Column(
            "detail", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_audit_log_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name=op.f("fk_audit_log_document_id_documents"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_tenant_id"), "audit_log", ["tenant_id"])
    op.create_index(op.f("ix_audit_log_document_id"), "audit_log", ["document_id"])
    op.create_index(op.f("ix_audit_log_event"), "audit_log", ["event"])
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"])

    # Row-level security (same pattern as migration 0001).
    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
              USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
              WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """
        )

    # The audit log is append-only. A trigger blocks direct UPDATE/DELETE for
    # everyone (the app role owns the table, so a grant REVOKE would not bind it).
    # pg_trigger_depth() = 0 means "not fired from a cascade", so deleting a
    # tenant still cascades its audit rows away.
    op.execute(
        """
        CREATE FUNCTION audit_log_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only (% is not allowed)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_mutate
          BEFORE UPDATE OR DELETE ON audit_log
          FOR EACH ROW WHEN (pg_trigger_depth() = 0)
          EXECUTE FUNCTION audit_log_append_only()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_mutate ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_append_only()")
    for table in _RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.drop_table("audit_log")
    op.drop_table("documents")
    op.execute("DROP TYPE document_status")
    op.execute("DROP TYPE source_format")
