"""KYC status log repository — append-only."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.kyc.models.kyc_status_log import KYCStatusLog


class KYCStatusLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, log: KYCStatusLog) -> KYCStatusLog:
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log
