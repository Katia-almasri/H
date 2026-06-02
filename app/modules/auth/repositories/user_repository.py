"""User repository for database operations."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime

from app.modules.auth.models.user import User


class UserRepository:
    """Repository for User model database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        """Create a new user."""
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user: User) -> User:
        """Update existing user."""
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def increment_failed_login(self, user_id: str) -> None:
        """Increment failed login attempts."""
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                failed_login_attempts=User.failed_login_attempts + 1,
                updated_at=datetime.utcnow()
            )
        )
        await self.db.commit()

    async def reset_failed_login(self, user_id: str) -> None:
        """Reset failed login attempts."""
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                failed_login_attempts=0,
                locked_until=None,
                updated_at=datetime.utcnow()
            )
        )
        await self.db.commit()

    async def update_last_login(self, user_id: str) -> None:
        """Update last login timestamp."""
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                last_login_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
        await self.db.commit()
