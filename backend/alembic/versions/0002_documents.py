"""documents, with row-level security

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

    # Row-level security (same pattern as migration 0001).
    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE documents FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON documents
          USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
          WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON documents")
    op.drop_table("documents")
    op.execute("DROP TYPE document_status")
    op.execute("DROP TYPE source_format")
