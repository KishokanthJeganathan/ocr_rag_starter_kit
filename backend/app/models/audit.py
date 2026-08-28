"""Append-only audit log — every meaningful action on a document.

Stage 2 writes ``document.uploaded``, ``document.stored`` and ``worker.picked_up``.
Later stages add extraction, correction, approval and export events. The
application role is granted INSERT/SELECT only (see migration 0002), so rows
cannot be changed or deleted.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True, nullable=True
    )

    actor: Mapped[str] = mapped_column(String(255), nullable=False, server_default="system")
    event: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
