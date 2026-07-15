"""KYC submission repository."""

from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, desc, func, or_, select

from app.modules.auth.models.user import User
from app.modules.kyc.enums import KYCStatus
from app.modules.kyc.models.kyc_submission import KYCSubmission


class KYCSubmissionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, submission_id: str) -> Optional[KYCSubmission]:
        result = await self.db.execute(
            select(KYCSubmission).where(KYCSubmission.id == submission_id)
        )
        return result.scalars().first()

    async def get_by_user_id(self, user_id: str) -> Optional[KYCSubmission]:
        result = await self.db.execute(
            select(KYCSubmission)
            .where(KYCSubmission.user_id == user_id)
            .order_by(KYCSubmission.created_at.desc())
        )
        return result.scalars().first()

    async def create(self, submission: KYCSubmission) -> KYCSubmission:
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        return submission

    async def list_for_admin(
        self,
        *,
        page: int,
        page_size: int,
        search: Optional[str] = None,
        nationality: Optional[str] = None,
        tier: Optional[str] = None,
        status: Optional[str] = None,
        submitted_from: Optional[datetime] = None,
        submitted_to: Optional[datetime] = None,
        order_by: str = "submitted_at",
        order_direction: str = "desc",
    ) -> tuple[list[tuple[KYCSubmission, User]], int]:
        """Return paginated KYC submissions with investor profile data."""
        filters = []

        if search:
            search_pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    User.full_name.ilike(search_pattern),
                    User.username.ilike(search_pattern),
                    KYCSubmission.full_legal_name.ilike(search_pattern),
                )
            )
        if nationality:
            filters.append(KYCSubmission.nationality == nationality)
        if tier:
            filters.append(KYCSubmission.tier == tier)
        if status:
            filters.append(KYCSubmission.status == status)
        if submitted_from:
            filters.append(KYCSubmission.submitted_at >= submitted_from)
        if submitted_to:
            filters.append(KYCSubmission.submitted_at <= submitted_to)

        sort_columns = {
            "submitted_at": KYCSubmission.submitted_at,
            "created_at": KYCSubmission.created_at,
            "status": KYCSubmission.status,
            "tier": KYCSubmission.tier,
            "nationality": KYCSubmission.nationality,
            "investor_name": User.full_name,
        }
        sort_column = sort_columns[order_by]
        sort_expression = desc(sort_column) if order_direction == "desc" else asc(sort_column)
        offset = (page - 1) * page_size

        count_stmt = (
            select(func.count())
            .select_from(KYCSubmission)
            .join(User, User.id == KYCSubmission.user_id)
            .where(*filters)
        )
        total = await self.db.scalar(count_stmt)

        rows_stmt = (
            select(KYCSubmission, User)
            .join(User, User.id == KYCSubmission.user_id)
            .where(*filters)
            .order_by(sort_expression, KYCSubmission.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(rows_stmt)
        return result.all(), total or 0

    async def count_submissions(
        self,
        *,
        status: Optional[str] = None,
        submitted_from: Optional[datetime] = None,
        submitted_to: Optional[datetime] = None,
        reviewed_from: Optional[datetime] = None,
        reviewed_to: Optional[datetime] = None,
    ) -> int:
        """Count KYC submissions, optionally filtered by status and date windows."""
        filters = []
        if status:
            filters.append(KYCSubmission.status == status)
        if submitted_from:
            filters.append(KYCSubmission.submitted_at >= submitted_from)
        if submitted_to:
            filters.append(KYCSubmission.submitted_at < submitted_to)
        if reviewed_from:
            filters.append(KYCSubmission.reviewed_at >= reviewed_from)
        if reviewed_to:
            filters.append(KYCSubmission.reviewed_at < reviewed_to)

        stmt = select(func.count()).select_from(KYCSubmission).where(*filters)
        return await self.db.scalar(stmt) or 0

    async def list_review_timestamps(
        self,
        *,
        reviewed_from: datetime,
        reviewed_to: datetime,
    ) -> list[tuple[datetime, datetime]]:
        """Return submitted/reviewed timestamp pairs for reviewed KYC submissions."""
        stmt = (
            select(KYCSubmission.submitted_at, KYCSubmission.reviewed_at)
            .where(
                KYCSubmission.submitted_at.is_not(None),
                KYCSubmission.reviewed_at.is_not(None),
                KYCSubmission.status.in_(
                    [KYCStatus.APPROVED.value, KYCStatus.REJECTED.value]
                ),
                KYCSubmission.reviewed_at >= reviewed_from,
                KYCSubmission.reviewed_at < reviewed_to,
            )
        )
        result = await self.db.execute(stmt)
        return result.all()

    async def update(self, submission: KYCSubmission) -> KYCSubmission:
        await self.db.commit()
        await self.db.refresh(submission)
        return submission
