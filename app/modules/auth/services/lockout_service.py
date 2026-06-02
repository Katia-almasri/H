"""Account lockout service for failed login attempt tracking."""

from datetime import datetime, timedelta
from typing import Optional

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.modules.auth.models.user import User
from app.modules.auth.enums import AccountStatus


class LockoutService:
    """Service for managing account lockouts based on failed login attempts."""

    def __init__(self, redis_client: redis.Redis, db: AsyncSession):
        self.redis = redis_client
        self.db = db
        
        # Lockout configuration
        self.short_lockout_threshold = 5  # Failed attempts before 30-min lock
        self.short_lockout_duration_minutes = 30
        self.permanent_lockout_threshold = 10  # Total failures in 24h before permanent lock
        self.tracking_window_hours = 24

    async def record_failed_login(self, user_id: str, ip_address: str) -> dict:
        """
        Record a failed login attempt and check if lockout is needed.
        
        Args:
            user_id: User's unique identifier
            ip_address: IP address of the login attempt
            
        Returns:
            Dictionary with lockout status:
            - is_locked: bool
            - lockout_type: "temporary" | "permanent" | None
            - locked_until: datetime | None
            - attempts_remaining: int | None
        """
        # Increment consecutive failures (for 30-min lockout)
        consecutive_key = f"login:consecutive:{user_id}"
        consecutive_failures = await self.redis.incr(consecutive_key)
        
        # Set expiry on first failure (resets after 30 minutes of no attempts)
        if consecutive_failures == 1:
            await self.redis.expire(consecutive_key, self.short_lockout_duration_minutes * 60)
        
        # Track total failures in 24h window (for permanent lockout)
        total_key = f"login:total:{user_id}"
        total_failures = await self.redis.incr(total_key)
        
        # Set expiry on first failure in 24h window
        if total_failures == 1:
            await self.redis.expire(total_key, self.tracking_window_hours * 60 * 60)
        
        # Check for permanent lockout (10 failures in 24h)
        if total_failures >= self.permanent_lockout_threshold:
            await self._apply_permanent_lockout(user_id)
            return {
                "is_locked": True,
                "lockout_type": "permanent",
                "locked_until": None,  # Requires admin unlock
                "attempts_remaining": 0,
                "message": "Account permanently locked. Contact administrator."
            }
        
        # Check for temporary lockout (5 consecutive failures)
        if consecutive_failures >= self.short_lockout_threshold:
            locked_until = await self._apply_temporary_lockout(user_id)
            return {
                "is_locked": True,
                "lockout_type": "temporary",
                "locked_until": locked_until,
                "attempts_remaining": 0,
                "message": f"Account locked for {self.short_lockout_duration_minutes} minutes due to too many failed attempts."
            }
        
        # Not locked yet, return remaining attempts
        attempts_remaining = self.short_lockout_threshold - consecutive_failures
        return {
            "is_locked": False,
            "lockout_type": None,
            "locked_until": None,
            "attempts_remaining": attempts_remaining,
            "message": f"{attempts_remaining} attempts remaining before temporary lockout."
        }

    async def _apply_temporary_lockout(self, user_id: str) -> datetime:
        """
        Apply a temporary 30-minute lockout to a user account.
        
        Args:
            user_id: User's unique identifier
            
        Returns:
            Datetime when the lockout expires
        """
        locked_until = datetime.utcnow() + timedelta(minutes=self.short_lockout_duration_minutes)
        
        # Update user record in database
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                locked_until=locked_until,
                updated_at=datetime.utcnow()
            )
        )
        await self.db.commit()
        
        # Store lockout in Redis for quick checks
        lockout_key = f"lockout:temp:{user_id}"
        await self.redis.setex(
            lockout_key,
            self.short_lockout_duration_minutes * 60,
            locked_until.isoformat()
        )
        
        return locked_until

    async def _apply_permanent_lockout(self, user_id: str) -> None:
        """
        Apply a permanent lockout to a user account (requires admin unlock).
        
        Args:
            user_id: User's unique identifier
        """
        # Update user record in database
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                account_status=AccountStatus.SUSPENDED.value,
                locked_until=None,  # Permanent lock has no expiry
                updated_at=datetime.utcnow()
            )
        )
        await self.db.commit()
        
        # Store permanent lockout flag in Redis
        lockout_key = f"lockout:permanent:{user_id}"
        await self.redis.set(lockout_key, "1")

    async def check_lockout_status(self, user_id: str) -> dict:
        """
        Check if a user account is currently locked.
        
        Args:
            user_id: User's unique identifier
            
        Returns:
            Dictionary with lockout status:
            - is_locked: bool
            - lockout_type: "temporary" | "permanent" | None
            - locked_until: datetime | None
        """
        # Check for permanent lockout
        permanent_key = f"lockout:permanent:{user_id}"
        is_permanent = await self.redis.exists(permanent_key)
        
        if is_permanent:
            return {
                "is_locked": True,
                "lockout_type": "permanent",
                "locked_until": None,
                "message": "Account permanently locked. Contact administrator."
            }
        
        # Check for temporary lockout
        temp_key = f"lockout:temp:{user_id}"
        locked_until_str = await self.redis.get(temp_key)
        
        if locked_until_str:
            locked_until = datetime.fromisoformat(locked_until_str)
            
            # Check if lockout has expired
            if datetime.utcnow() < locked_until:
                return {
                    "is_locked": True,
                    "lockout_type": "temporary",
                    "locked_until": locked_until,
                    "message": f"Account locked until {locked_until.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                }
            else:
                # Lockout expired, clean up
                await self.redis.delete(temp_key)
                await self._reset_consecutive_failures(user_id)
        
        return {
            "is_locked": False,
            "lockout_type": None,
            "locked_until": None
        }

    async def reset_failed_attempts(self, user_id: str) -> None:
        """
        Reset failed login attempts after successful login.
        
        Args:
            user_id: User's unique identifier
        """
        await self._reset_consecutive_failures(user_id)
        
        # Update database
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                failed_login_attempts="0",
                locked_until=None,
                updated_at=datetime.utcnow()
            )
        )
        await self.db.commit()

    async def _reset_consecutive_failures(self, user_id: str) -> None:
        """Reset consecutive failure counter."""
        consecutive_key = f"login:consecutive:{user_id}"
        await self.redis.delete(consecutive_key)

    async def admin_unlock_account(self, user_id: str) -> None:
        """
        Admin action to unlock a permanently locked account.
        
        Args:
            user_id: User's unique identifier
        """
        # Remove permanent lockout flag
        permanent_key = f"lockout:permanent:{user_id}"
        await self.redis.delete(permanent_key)
        
        # Remove temporary lockout if exists
        temp_key = f"lockout:temp:{user_id}"
        await self.redis.delete(temp_key)
        
        # Reset all counters
        consecutive_key = f"login:consecutive:{user_id}"
        total_key = f"login:total:{user_id}"
        await self.redis.delete(consecutive_key)
        await self.redis.delete(total_key)
        
        # Update database
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                account_status=AccountStatus.ACTIVE.value,
                failed_login_attempts="0",
                locked_until=None,
                updated_at=datetime.utcnow()
            )
        )
        await self.db.commit()

    async def get_failure_stats(self, user_id: str) -> dict:
        """
        Get current failure statistics for a user.
        
        Args:
            user_id: User's unique identifier
            
        Returns:
            Dictionary with failure statistics
        """
        consecutive_key = f"login:consecutive:{user_id}"
        total_key = f"login:total:{user_id}"
        
        consecutive = await self.redis.get(consecutive_key)
        total = await self.redis.get(total_key)
        
        return {
            "consecutive_failures": int(consecutive) if consecutive else 0,
            "total_failures_24h": int(total) if total else 0,
            "consecutive_threshold": self.short_lockout_threshold,
            "permanent_threshold": self.permanent_lockout_threshold
        }
