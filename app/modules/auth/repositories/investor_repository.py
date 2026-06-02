"""Investor repository."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.auth.models.investor import Investor


class InvestorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: str) -> Optional[Investor]:
        result = await self.db.execute(
            select(Investor).where(Investor.user_id == user_id)
        )
        return result.scalars().first()

    async def create(self, investor: Investor) -> Investor:
        self.db.add(investor)
        await self.db.commit()
        await self.db.refresh(investor)
        return investor

    async def update(self, investor: Investor) -> Investor:
        await self.db.commit()
        await self.db.refresh(investor)
        return investor
