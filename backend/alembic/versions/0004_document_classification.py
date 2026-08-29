"""document classification: doc_type + confidence, and a 'processed' status

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE document_type AS ENUM ('nda', 'invoice', 'other')")
    document_type = postgresql.ENUM(name="document_type", create_type=False)

    op.add_column("documents", sa.Column("doc_type", document_type, nullable=True))
    op.add_column("documents", sa.Column("doc_type_confidence", sa.Float(), nullable=True))

    # New terminal status for a document that finished OCR + classification.
    op.execute("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'processed'")


def downgrade() -> None:
    op.drop_column("documents", "doc_type_confidence")
    op.drop_column("documents", "doc_type")
    op.execute("DROP TYPE document_type")
    # 'processed' stays in document_status — PostgreSQL can't drop an enum value.
