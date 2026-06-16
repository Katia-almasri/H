"""Repository for InvestorSuitability records.

Provides tenant-scoped data access for the suitability submission lifecycle:
active-record lookup, supersession, expiry management, and renewal scanning.

Every method filters by ``tenant_id``. No ``commit()`` or ``begin()`` calls —
the calling service owns the transaction boundary.

Requirements: 3.8, 3.9, 5.5, 5.7, 6.1, 6.2, 7.2, 8.2, 8.3, 9.3, 9.5.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.modules.suitability_questionnaire.models.investor_suitability import (
    InvestorSuitability,
)


class InvestorSuitabilityRepository:
    """Async data-access layer for the ``investor_suitability`` table."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_active(
        self, user_id: str, tenant_id: str
    ) -> Optional[InvestorSuitability]:
        """Return the at-most-one row where ``superseded_by IS NULL`` for this user+tenant."""
        stmt = (
            select(InvestorSuitability)
            .where(
                InvestorSuitability.tenant_id == tenant_id,
                InvestorSuitability.user_id == user_id,
                InvestorSuitability.superseded_by.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_not_suitable(
        self, user_id: str, tenant_id: str
    ) -> Optional[InvestorSuitability]:
        """Most recent record with ``outcome='NOT_SUITABLE'``, ordered by ``created_at DESC``.

        Used for cool-off enforcement (Requirement 5.5).
        """
        stmt = (
            select(InvestorSuitability)
            .where(
                InvestorSuitability.tenant_id == tenant_id,
                InvestorSuitability.user_id == user_id,
                InvestorSuitability.outcome == "NOT_SUITABLE",
            )
            .order_by(InvestorSuitability.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(
        self, record_id: str, tenant_id: str
    ) -> Optional[InvestorSuitability]:
        """Fetch a single record by primary key, filtered by tenant_id."""
        stmt = (
            select(InvestorSuitability)
            .where(
                InvestorSuitability.id == record_id,
                InvestorSuitability.tenant_id == tenant_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def supersede_and_insert(
        self,
        new_record: InvestorSuitability,
        prior_active_id: Optional[str],
    ) -> InvestorSuitability:
        """Atomically supersede the prior active record and insert the new one.

        If ``prior_active_id`` is provided, sets ``superseded_by = new_record.id``
        on that row. Then adds the new record to the session.

        Runs inside the caller's transaction — no internal commit.
        """
        if prior_active_id is not None:
            stmt = (
                update(InvestorSuitability)
                .where(
                    InvestorSuitability.id == prior_active_id,
                    InvestorSuitability.tenant_id == new_record.tenant_id,
                )
                .values(superseded_by=new_record.id)
            )
            await self.db.execute(stmt)

        self.db.add(new_record)
        await self.db.flush()
        return new_record

    async def mark_expired_now(self, record_id: str, tenant_id: str) -> None:
        """Set ``expires_at = now()`` on the specified record.

        Used by KYC-triggered invalidation (Requirement 7.2).
        """
        stmt = (
            update(InvestorSuitability)
            .where(
                InvestorSuitability.id == record_id,
                InvestorSuitability.tenant_id == tenant_id,
            )
            .values(expires_at=func.now())
        )
        await self.db.execute(stmt)

    async def scan_expiring(
        self,
        tenant_id: str,
        window_start: datetime,
        window_end: datetime,
        limit: int = 100,
        offset: int = 0,
    ) -> list[InvestorSuitability]:
        """Paged scan for records expiring within a time window.

        Returns records where ``expires_at`` is between ``window_start`` and
        ``window_end`` and ``superseded_by IS NULL`` (only active records).

        Used by the renewal notification worker.
        """
        stmt = (
            select(InvestorSuitability)
            .where(
                InvestorSuitability.tenant_id == tenant_id,
                InvestorSuitability.expires_at >= window_start,
                InvestorSuitability.expires_at <= window_end,
                InvestorSuitability.superseded_by.is_(None),
            )
            .order_by(InvestorSuitability.expires_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
