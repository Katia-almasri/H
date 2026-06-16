"""Repository for the suitability_completion_markers table.

Provides three operations on the small flag table that indicates an Investor
must complete the Suitability Questionnaire after first KYC approval:

* ``mark``  — idempotent insert using ``ON CONFLICT (user_id, tenant_id) DO NOTHING``.
* ``clear`` — delete the marker row (no-op when absent).
* ``exists`` — check whether a marker exists for the given Investor/tenant pair.

The composite primary key ``(user_id, tenant_id)`` serves as the conflict target
for the idempotent insert — Requirement 1.1.
"""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suitability_questionnaire.models.suitability_completion_marker import (
    SuitabilityCompletionMarker,
)


class SuitabilityCompletionMarkerRepository:
    """Data-access layer for suitability completion markers."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def mark(
        self,
        user_id: str,
        tenant_id: str,
        kyc_submission_id: str,
    ) -> None:
        """Idempotently insert a completion marker.

        Uses ``INSERT … ON CONFLICT (user_id, tenant_id) DO NOTHING`` so that
        repeated KYC approvals never produce duplicate markers.
        """
        stmt = (
            insert(SuitabilityCompletionMarker)
            .values(
                user_id=user_id,
                tenant_id=tenant_id,
                kyc_submission_id=kyc_submission_id,
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "tenant_id"],
            )
        )
        await self.db.execute(stmt)

    async def clear(self, user_id: str, tenant_id: str) -> None:
        """Delete the marker row. No-op if absent."""
        stmt = delete(SuitabilityCompletionMarker).where(
            SuitabilityCompletionMarker.user_id == user_id,
            SuitabilityCompletionMarker.tenant_id == tenant_id,
        )
        await self.db.execute(stmt)

    async def exists(self, user_id: str, tenant_id: str) -> bool:
        """Return whether a marker exists for the given Investor/tenant pair."""
        stmt = select(SuitabilityCompletionMarker.user_id).where(
            SuitabilityCompletionMarker.user_id == user_id,
            SuitabilityCompletionMarker.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None
