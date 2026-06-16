"""Audit log entry factory for the suitability module.

Provides a ``create_audit_log_entry`` helper that builds an ORM instance ready
to be added to the session. The underlying ``audit_logs`` table is append-only
(UPDATE and DELETE are blocked at the RLS level).

Required fields per the product steering audit rules:
- ``user_id``
- ``action`` (from ``AuditAction`` enum)
- ``ip_address``
- ``user_agent``
- ``timestamp_utc``
- ``metadata`` (JSONB)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import INET, JSONB

from app.database import Base


class AuditLogEntry(Base):
    """ORM model for the ``audit_logs`` append-only table."""

    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    tenant_id = Column(Text, nullable=False)
    user_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    timestamp_utc = Column(TIMESTAMP(timezone=True), nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=True)


def create_audit_log_entry(
    *,
    user_id: str,
    tenant_id: str,
    action: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLogEntry:
    """Build an ``AuditLogEntry`` instance ready for ``session.add()``.

    The caller is responsible for flushing/committing the session.
    """
    return AuditLogEntry(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        action=action if isinstance(action, str) else action.value,
        ip_address=ip_address,
        user_agent=user_agent[:512] if user_agent else None,
        timestamp_utc=datetime.now(timezone.utc),
        metadata_=metadata,
    )
