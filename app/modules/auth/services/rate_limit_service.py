"""Rate limiting service for login attempts."""

from datetime import datetime, timedelta
from typing import Optional

import redis.asyncio as redis


class RateLimitService:
    """Service for rate limiting login attempts by IP address."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        
        # Rate limit configuration
        self.max_attempts = 10  # Maximum attempts per window
        self.window_seconds = 60  # Time window in seconds (1 minute)

    async def check_rate_limit(self, ip_address: str) -> dict:
        """
        Check if an IP address has exceeded the rate limit.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            Dictionary with rate limit status:
            - is_allowed: bool
            - attempts_remaining: int
            - reset_at: datetime
            - retry_after: int (seconds until reset)
        """
        key = f"ratelimit:login:{ip_address}"
        
        # Get current attempt count
        current_attempts = await self.redis.get(key)
        
        if current_attempts is None:
            # First attempt, initialize counter
            await self.redis.setex(key, self.window_seconds, 1)
            
            reset_at = datetime.utcnow() + timedelta(seconds=self.window_seconds)
            
            return {
                "is_allowed": True,
                "attempts_remaining": self.max_attempts - 1,
                "reset_at": reset_at,
                "retry_after": 0
            }
        
        current_attempts = int(current_attempts)
        
        # Check if limit exceeded
        if current_attempts >= self.max_attempts:
            # Get TTL to know when the limit resets
            ttl = await self.redis.ttl(key)
            reset_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            return {
                "is_allowed": False,
                "attempts_remaining": 0,
                "reset_at": reset_at,
                "retry_after": ttl
            }
        
        # Increment counter
        await self.redis.incr(key)
        
        # Get updated TTL
        ttl = await self.redis.ttl(key)
        reset_at = datetime.utcnow() + timedelta(seconds=ttl)
        
        return {
            "is_allowed": True,
            "attempts_remaining": self.max_attempts - current_attempts - 1,
            "reset_at": reset_at,
            "retry_after": 0
        }

    async def record_attempt(self, ip_address: str) -> None:
        """
        Record a login attempt for an IP address.
        This is called after check_rate_limit allows the request.
        
        Args:
            ip_address: IP address making the attempt
        """
        # This is now handled in check_rate_limit
        pass

    async def reset_rate_limit(self, ip_address: str) -> None:
        """
        Reset rate limit for an IP address (admin action).
        
        Args:
            ip_address: IP address to reset
        """
        key = f"ratelimit:login:{ip_address}"
        await self.redis.delete(key)

    async def get_rate_limit_info(self, ip_address: str) -> dict:
        """
        Get current rate limit information for an IP address.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            Dictionary with rate limit information
        """
        key = f"ratelimit:login:{ip_address}"
        
        current_attempts = await self.redis.get(key)
        
        if current_attempts is None:
            return {
                "current_attempts": 0,
                "max_attempts": self.max_attempts,
                "window_seconds": self.window_seconds,
                "attempts_remaining": self.max_attempts,
                "is_limited": False
            }
        
        current_attempts = int(current_attempts)
        ttl = await self.redis.ttl(key)
        
        return {
            "current_attempts": current_attempts,
            "max_attempts": self.max_attempts,
            "window_seconds": self.window_seconds,
            "attempts_remaining": max(0, self.max_attempts - current_attempts),
            "is_limited": current_attempts >= self.max_attempts,
            "reset_in_seconds": ttl
        }

    async def is_rate_limited(self, ip_address: str) -> bool:
        """
        Quick check if an IP address is currently rate limited.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            True if rate limited, False otherwise
        """
        key = f"ratelimit:login:{ip_address}"
        current_attempts = await self.redis.get(key)
        
        if current_attempts is None:
            return False
        
        return int(current_attempts) >= self.max_attempts
