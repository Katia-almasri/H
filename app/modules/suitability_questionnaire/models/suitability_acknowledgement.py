"""Suitability acknowledgement model — APPEND-ONLY.

One row per ``(suitability_id, user_id, property_id, tenant_id)`` records an
Investor's explicit acknowledgement of the ``ELIGIBLE_WITH_WARNING`` risk
disclosure for a specific property under a specific Active_Suitability_Record.

Append-only contract
--------------------
This table is append-only by design. Per Requirement 4.4, RLS policies on the
underlying Postgres table deny ``UPDATE`` and ``DELETE`` for every role; any
correction must be expressed as a new row, never as a mutation of an existing
one. The repository layer (``SuitabilityAcknowledgementRepository``) MUST NOT
expose ``update`` or ``delete`` methods — only ``get`` and idempotent insert
via ``ON CONFLICT (suitability_id, user_id, property_id, tenant_id) DO NOTHING``.

Idempotency
-----------
The unique constraint on ``(suitability_id, user_id, property_id, tenant_id)``
turns repeated acknowledgement submissions into a no-op (Requirement 4.5):
the service returns the existing row instead of creating a duplicate.

Schema reference: design.md → "Tables → suitability_acknowledgements".
Requirements: 4.3, 4.4, 4.5, 9.1.
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET

from app.database import Base


class SuitabilityAcknowledgement(Base):
    """Append-only legal evidence of informed consent per property."""

    __tablename__ = "suitability_acknowledgements"

    # Primary key — UUID4 generated in the service layer, stored as a string
    # to match the project-wide convention (see InvestorSuitability and
    # app/modules/auth/models/user.py).
    id = Column(String, primary_key=True)

    # Multi-tenant discriminator. Every read and write filters on this column.
    tenant_id = Column(Text, nullable=False)

    # The Active_Suitability_Record the acknowledgement is bound to. References
    # ``investor_suitability.id`` (table created in task 2.1).
    suitability_id = Column(
        String,
        ForeignKey("investor_suitability.id"),
        nullable=False,
        index=True,
    )

    # Investor — references users.id.
    user_id = Column(String, nullable=False)

    # Target property — references properties.id (Sprint 3).
    property_id = Column(String, nullable=False)

    # Moment the Investor confirmed the warning. UTC.
    acknowledged_at = Column(TIMESTAMP(timezone=True), nullable=False)

    # Forensic metadata captured from the originating HTTP request.
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)

    created_at = Column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        # Idempotency guarantee for ``ON CONFLICT DO NOTHING`` inserts —
        # Requirement 4.5.
        UniqueConstraint(
            "suitability_id",
            "user_id",
            "property_id",
            "tenant_id",
            name="uq_suitability_acknowledgement_idempotent",
        ),
        # Tenant-scoped scans (e.g. tenant-bound audit reads).
        Index(
            "ix_suitability_acknowledgements_tenant_id",
            "tenant_id",
        ),
    )
