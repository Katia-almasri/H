"""Session repository for refresh token management."""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from datetime import datetime

from app.modules.auth.models.session import UserSession


class SessionRepository:
    """Repository for UserSession model database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, session_id: str) -> Optional[UserSession]:
        """Get session by ID."""
        result = await self.db.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_token_hash(self, token_hash: str) -> Optional[UserSession]:
        """Get session by refresh token hash."""
        result = await self.db.execute(
            select(UserSession)
            .where(UserSession.refresh_token_hash == token_hash)
            .where(UserSession.is_active == True)
        )
        return result.scalar_one_or_none()

    async def get_user_sessions(self, user_id: str) -> List[UserSession]:
        """Get all active sessions for a user."""
        result = await self.db.execute(
            select(UserSession)
            .where(UserSession.user_id == user_id)
            .where(UserSession.is_active == True)
        )
        return list(result.scalars().all())

    async def create(self, session: UserSession) -> UserSession:
        """Create a new session."""
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def update_last_used(self, session_id: str) -> None:
        """Update session last used timestamp."""
        await self.db.execute(
            update(UserSession)
            .where(UserSession.id == session_id)
            .values(last_used_at=datetime.utcnow())
        )
        await self.db.commit()

    async def deactivate(self, session_id: str) -> None:
        """Deactivate a session."""
        await self.db.execute(
            update(UserSession)
            .where(UserSession.id == session_id)
            .values(is_active=False)
        )
        await self.db.commit()

    async def deactivate_user_sessions(self, user_id: str) -> None:
        """Deactivate all sessions for a user."""
        await self.db.execute(
            update(UserSession)
            .where(UserSession.user_id == user_id)
            .values(is_active=False)
        )
        await self.db.commit()

    async def delete_expired(self) -> None:
        """Delete expired sessions."""
        await self.db.execute(
            delete(UserSession)
            .where(UserSession.expires_at < datetime.utcnow())
        )
        await self.db.commit()
