"""initial schema: tenants + matters with row-level security

Stage 0 establishes only the tenant isolation boundary. The ``documents`` table,
the audit log, and extraction-schema tables are introduced by later migrations,
designed against what those stages actually store.

Revision ID: 0001
Revises:
Create Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_TABLES = ("tenants", "matters")


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("name", name=op.f("uq_tenants_name")),
    )

    op.create_table(
        "matters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_matters_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matters")),
    )
    op.create_index(op.f("ix_matters_tenant_id"), "matters", ["tenant_id"])

    # --- Row-level security ------------------------------------------------
    # FORCE makes the policies apply to the table owner too (the app role owns
    # these tables). A missing app.current_tenant setting yields NULL, so the
    # predicate is false and nothing is visible: default-deny.
    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY tenant_self ON tenants
          USING (id = current_setting('app.current_tenant', true)::uuid)
          WITH CHECK (id = current_setting('app.current_tenant', true)::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation ON matters
          USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
          WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON matters")
    op.execute("DROP POLICY IF EXISTS tenant_self ON tenants")
    op.drop_index(op.f("ix_matters_tenant_id"), table_name="matters")
    op.drop_table("matters")
    op.drop_table("tenants")
