"""Repository for the append-only suitability_acknowledgements table.

This repository intentionally omits ``update`` and ``delete`` methods because the
underlying table is append-only per Requirement 4.4. RLS policies on the Postgres
table further deny UPDATE and DELETE for every role.

Idempotent insert
-----------------
``idempotent_create`` uses ``INSERT … ON CONFLICT DO NOTHING`` on the unique key
``(suitability_id, user_id, property_id, tenant_id)``. If the row already exists
the method falls back to a SELECT and returns the existing record — satisfying
Requirement 4.5 (repeated submissions are a no-op).
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suitability_questionnaire.models.suitability_acknowledgement import (
    SuitabilityAcknowledgement,
)


class SuitabilityAcknowledgementRepository:
    """Data-access layer for suitability acknowledgements (append-only)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(
        self,
        suitability_id: str,
        user_id: str,
        property_id: str,
        tenant_id: str,
    ) -> SuitabilityAcknowledgement | None:
        """Fetch an acknowledgement by its unique key."""
        stmt = select(SuitabilityAcknowledgement).where(
            SuitabilityAcknowledgement.suitability_id == suitability_id,
            SuitabilityAcknowledgement.user_id == user_id,
            SuitabilityAcknowledgement.property_id == property_id,
            SuitabilityAcknowledgement.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def idempotent_create(
        self,
        record: SuitabilityAcknowledgement,
    ) -> SuitabilityAcknowledgement:
        """Insert a new acknowledgement or return the existing one on conflict.

        Uses ``INSERT … ON CONFLICT (suitability_id, user_id, property_id,
        tenant_id) DO NOTHING``. If nothing is returned (row already existed),
        falls back to a SELECT to retrieve the existing record.
        """
        stmt = (
            insert(SuitabilityAcknowledgement)
            .values(
                id=record.id,
                tenant_id=record.tenant_id,
                suitability_id=record.suitability_id,
                user_id=record.user_id,
                property_id=record.property_id,
                acknowledged_at=record.acknowledged_at,
                ip_address=record.ip_address,
                user_agent=record.user_agent,
                created_at=record.created_at,
            )
            .on_conflict_do_nothing(
                constraint="uq_suitability_acknowledgement_idempotent",
            )
            .returning(SuitabilityAcknowledgement.__table__)
        )

        result = await self.db.execute(stmt)
        row = result.fetchone()

        if row is not None:
            # Map the raw row back into an ORM instance.
            return SuitabilityAcknowledgement(**row._mapping)

        # Conflict occurred — the row already exists. Fetch it.
        return await self.get(  # type: ignore[return-value]
            suitability_id=record.suitability_id,
            user_id=record.user_id,
            property_id=record.property_id,
            tenant_id=record.tenant_id,
        )
