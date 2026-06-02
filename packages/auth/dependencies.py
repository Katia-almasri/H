"""Reusable auth dependencies for role-based access control."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.database import get_db
from app.redis_client import get_redis
from app.modules.auth.enums import UserRole
from app.modules.auth.models.user import User
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.services.token_service import TokenService
from packages.core.exceptions import AuthenticationException, AuthorizationException

security = HTTPBearer(auto_error=True)


def _get_token_service(redis_client: Annotated[Redis, Depends(get_redis)]) -> TokenService:
    return TokenService(redis_client)


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    token_service: Annotated[TokenService, Depends(_get_token_service)],
) -> str:
    """Extract and verify user ID from access token."""
    payload = token_service.verify_access_token(credentials.credentials)
    if not payload:
        raise AuthenticationException("Invalid or expired token")
    return payload["sub"]


class RoleChecker:
    """Dependency that enforces one or more allowed roles.

    Usage in a router:
        require_admin = RoleChecker(allowed_roles=[UserRole.ADMIN])

        @router.post("/admin/action")
        async def admin_action(
            user_id: Annotated[str, Depends(require_admin)],
        ):
            ...
    """

    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
        token_service: Annotated[TokenService, Depends(_get_token_service)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> str:
        payload = token_service.verify_access_token(credentials.credentials)
        if not payload:
            raise AuthenticationException("Invalid or expired token")

        user_id = payload["sub"]
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(user_id)

        if not user:
            raise AuthenticationException("User not found")

        if user.role not in [role.value for role in self.allowed_roles]:
            raise AuthorizationException("Insufficient permissions")

        return user_id
