"""Token management service for JWT and refresh tokens."""

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional

import redis.asyncio as redis
from jose import JWTError, jwt

from packages.core.config import settings


class TokenService:
    """Service for managing JWT access tokens and refresh tokens."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.access_token_expire_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS

    @property
    def _algorithm(self) -> str:
        """Return HS256 when no RSA keys are configured, RS256 otherwise."""
        if settings.JWT_PRIVATE_KEY and settings.JWT_PRIVATE_KEY != "":
            return "RS256"
        return "HS256"

    @property
    def _sign_key(self) -> str:
        """Return the key used to sign tokens."""
        if self._algorithm == "RS256":
            return settings.JWT_PRIVATE_KEY
        # HS256 fallback — use a derived secret from APP_NAME + REDIS_URL
        return f"{settings.APP_NAME}-dev-secret-{settings.REDIS_URL}"

    @property
    def _verify_key(self) -> str:
        """Return the key used to verify tokens."""
        if self._algorithm == "RS256":
            return settings.JWT_PUBLIC_KEY
        return self._sign_key

    def create_access_token(self, user_id: str, email: str, role: str) -> str:
        """Create a signed JWT access token."""
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow(),
        }

        return jwt.encode(payload, self._sign_key, algorithm=self._algorithm)

    def create_refresh_token(self) -> str:
        """Create a refresh token (UUID4)."""
        return str(uuid.uuid4())

    def hash_token(self, token: str) -> str:
        """Hash a token using SHA-256."""
        return hashlib.sha256(token.encode()).hexdigest()

    async def add_to_blocklist(self, refresh_token: str, reason: str = "logout") -> None:
        """Add a refresh token to the Redis blocklist."""
        token_hash = self.hash_token(refresh_token)
        key = f"blocklist:refresh:{token_hash}"
        ttl_seconds = self.refresh_token_expire_days * 24 * 60 * 60
        await self.redis.setex(key, ttl_seconds, reason)

    async def is_token_blocklisted(self, refresh_token: str) -> bool:
        """Check if a refresh token is in the blocklist."""
        token_hash = self.hash_token(refresh_token)
        key = f"blocklist:refresh:{token_hash}"
        return bool(await self.redis.exists(key))

    def verify_access_token(self, token: str) -> Optional[dict]:
        """Verify and decode a JWT access token."""
        try:
            payload = jwt.decode(
                token,
                self._verify_key,
                algorithms=[self._algorithm]
            )
            if payload.get("type") != "access":
                return None
            return payload
        except JWTError:
            return None

    def get_token_expiry(self) -> int:
        """Get access token expiry time in seconds."""
        return self.access_token_expire_minutes * 60
