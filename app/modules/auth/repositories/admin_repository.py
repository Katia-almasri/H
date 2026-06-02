"""Admin repository."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.auth.models.admin import Admin


class AdminRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: str) -> Optional[Admin]:
        result = await self.db.execute(
            select(Admin).where(Admin.user_id == user_id)
        )
        return result.scalars().first()

    async def get_by_id(self, admin_id: str) -> Optional[Admin]:
        result = await self.db.execute(
            select(Admin).where(Admin.id == admin_id)
        )
        return result.scalars().first()

    async def create(self, admin: Admin) -> Admin:
        self.db.add(admin)
        await self.db.commit()
        await self.db.refresh(admin)
        return admin

    async def update(self, admin: Admin) -> Admin:
        await self.db.commit()
        await self.db.refresh(admin)
        return admin
