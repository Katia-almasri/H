"""KYC submission repository."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.kyc.models.kyc_submission import KYCSubmission


class KYCSubmissionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, submission_id: str) -> Optional[KYCSubmission]:
        result = await self.db.execute(
            select(KYCSubmission).where(KYCSubmission.id == submission_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> Optional[KYCSubmission]:
        result = await self.db.execute(
            select(KYCSubmission)
            .where(KYCSubmission.user_id == user_id)
            .order_by(KYCSubmission.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def create(self, submission: KYCSubmission) -> KYCSubmission:
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        return submission

    async def update(self, submission: KYCSubmission) -> KYCSubmission:
        await self.db.commit()
        await self.db.refresh(submission)
        return submission
