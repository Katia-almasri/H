"""Device detection and fingerprinting service."""

import hashlib
import json
from typing import Optional, Dict
from datetime import datetime

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.auth.models.session import UserSession


class DeviceService:
    """Service for detecting new devices and generating device fingerprints."""

    def __init__(self, redis_client: redis.Redis, db: AsyncSession):
        self.redis = redis_client
        self.db = db

    def generate_device_fingerprint(
        self,
        user_agent: str,
        ip_address: str,
        accept_language: Optional[str] = None,
        accept_encoding: Optional[str] = None
    ) -> str:
        """
        Generate a device fingerprint from request headers.
        
        Args:
            user_agent: User-Agent header
            ip_address: IP address
            accept_language: Accept-Language header
            accept_encoding: Accept-Encoding header
            
        Returns:
            SHA-256 hash as device fingerprint
        """
        # Combine relevant headers to create fingerprint
        fingerprint_data = {
            "user_agent": user_agent or "",
            "ip_prefix": self._get_ip_prefix(ip_address),  # Use /24 subnet
            "accept_language": accept_language or "",
            "accept_encoding": accept_encoding or ""
        }
        
        # Create deterministic string
        fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
        
        # Hash to create fingerprint
        fingerprint = hashlib.sha256(fingerprint_string.encode()).hexdigest()
        
        return fingerprint

    def _get_ip_prefix(self, ip_address: str) -> str:
        """
        Get IP address prefix (first 3 octets for IPv4).
        This allows for some IP variation while detecting location changes.
        
        Args:
            ip_address: Full IP address
            
        Returns:
            IP prefix (e.g., "192.168.1" from "192.168.1.100")
        """
        parts = ip_address.split(".")
        if len(parts) == 4:
            return ".".join(parts[:3])
        return ip_address

    async def is_known_device(
        self,
        user_id: str,
        device_fingerprint: str
    ) -> bool:
        """
        Check if a device fingerprint is known for a user.
        
        Args:
            user_id: User's unique identifier
            device_fingerprint: Device fingerprint hash
            
        Returns:
            True if device is known, False if new device
        """
        # Check Redis cache first (fast lookup)
        cache_key = f"device:known:{user_id}:{device_fingerprint}"
        is_cached = await self.redis.exists(cache_key)
        
        if is_cached:
            return True
        
        # Check database for historical sessions
        result = await self.db.execute(
            select(UserSession)
            .where(UserSession.user_id == user_id)
            .where(UserSession.device_fingerprint == device_fingerprint)
            .limit(1)
        )
        session = result.scalars().first()
        
        if session:
            # Cache the result for 30 days
            await self.redis.setex(cache_key, 30 * 24 * 60 * 60, "1")
            return True
        
        return False

    async def register_device(
        self,
        user_id: str,
        device_fingerprint: str
    ) -> None:
        """
        Register a device as known for a user.
        
        Args:
            user_id: User's unique identifier
            device_fingerprint: Device fingerprint hash
        """
        cache_key = f"device:known:{user_id}:{device_fingerprint}"
        
        # Cache for 30 days
        await self.redis.setex(cache_key, 30 * 24 * 60 * 60, "1")

    def parse_user_agent(self, user_agent: str) -> Dict[str, str]:
        """
        Parse user agent string to extract device information.
        
        Args:
            user_agent: User-Agent header string
            
        Returns:
            Dictionary with device info (browser, os, device_type)
        """
        user_agent_lower = user_agent.lower()
        
        # Detect browser
        browser = "Unknown"
        if "chrome" in user_agent_lower and "edg" not in user_agent_lower:
            browser = "Chrome"
        elif "firefox" in user_agent_lower:
            browser = "Firefox"
        elif "safari" in user_agent_lower and "chrome" not in user_agent_lower:
            browser = "Safari"
        elif "edg" in user_agent_lower:
            browser = "Edge"
        elif "opera" in user_agent_lower or "opr" in user_agent_lower:
            browser = "Opera"
        
        # Detect OS
        os = "Unknown"
        if "windows" in user_agent_lower:
            os = "Windows"
        elif "mac os" in user_agent_lower or "macos" in user_agent_lower:
            os = "macOS"
        elif "linux" in user_agent_lower:
            os = "Linux"
        elif "android" in user_agent_lower:
            os = "Android"
        elif "ios" in user_agent_lower or "iphone" in user_agent_lower or "ipad" in user_agent_lower:
            os = "iOS"
        
        # Detect device type
        device_type = "Desktop"
        if "mobile" in user_agent_lower or "android" in user_agent_lower:
            device_type = "Mobile"
        elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
            device_type = "Tablet"
        
        return {
            "browser": browser,
            "os": os,
            "device_type": device_type
        }

    def get_approximate_location(self, ip_address: str) -> Dict[str, str]:
        """
        Get approximate location from IP address.
        
        Note: This is a placeholder. In production, use a GeoIP service like:
        - MaxMind GeoIP2
        - IP2Location
        - ipapi.co
        
        Args:
            ip_address: IP address
            
        Returns:
            Dictionary with location info (country, city, region)
        """
        # Placeholder implementation
        # TODO: Integrate with GeoIP service
        
        # For local/private IPs
        if ip_address.startswith("192.168.") or ip_address.startswith("10.") or ip_address.startswith("127."):
            return {
                "country": "Local Network",
                "city": "Unknown",
                "region": "Unknown",
                "country_code": "XX"
            }
        
        # Default placeholder
        return {
            "country": "Unknown",
            "city": "Unknown",
            "region": "Unknown",
            "country_code": "XX"
        }

    async def get_device_info(
        self,
        user_agent: str,
        ip_address: str,
        accept_language: Optional[str] = None,
        accept_encoding: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Get comprehensive device information.
        
        Args:
            user_agent: User-Agent header
            ip_address: IP address
            accept_language: Accept-Language header
            accept_encoding: Accept-Encoding header
            
        Returns:
            Dictionary with complete device info
        """
        fingerprint = self.generate_device_fingerprint(
            user_agent,
            ip_address,
            accept_language,
            accept_encoding
        )
        
        device_info = self.parse_user_agent(user_agent)
        location_info = self.get_approximate_location(ip_address)
        
        return {
            "fingerprint": fingerprint,
            "browser": device_info["browser"],
            "os": device_info["os"],
            "device_type": device_info["device_type"],
            "ip_address": ip_address,
            "country": location_info["country"],
            "city": location_info["city"],
            "region": location_info["region"],
            "country_code": location_info["country_code"],
            "timestamp": datetime.utcnow().isoformat()
        }
