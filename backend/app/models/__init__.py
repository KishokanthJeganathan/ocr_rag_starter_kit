"""SQLAlchemy models. Importing this package registers every table on
``Base.metadata`` (used by Alembic autogenerate).

Stage 0 defines only the tenant isolation hierarchy. ``documents``, the audit
log, and extraction-schema tables are added by the stages that first use them.
"""

from __future__ import annotations

from app.models.base import Base
from app.models.matter import Matter
from app.models.tenant import Tenant

__all__ = [
    "Base",
    "Matter",
    "Tenant",
]
