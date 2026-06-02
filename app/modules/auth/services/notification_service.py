"""Notification service for emails and alerts."""

import secrets
import string
from typing import Dict, Optional
from datetime import datetime

import redis.asyncio as redis

from app.modules.auth.enums import NotificationTemplate, OTPPurpose


class NotificationService:
    """Service for sending notifications and managing OTPs."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def generate_otp(self, length: int = 6) -> str:
        """
        Generate a numeric OTP.
        
        Args:
            length: Length of OTP (default 6 digits)
            
        Returns:
            Numeric OTP string
        """
        return ''.join(secrets.choice(string.digits) for _ in range(length))

    def generate_reset_token(self, length: int = 32) -> str:
        """
        Generate a secure password reset token.
        
        Args:
            length: Length of token (default 32 characters)
            
        Returns:
            URL-safe token string
        """
        return secrets.token_urlsafe(length)

    async def store_otp(
        self,
        user_id: str,
        otp: str,
        purpose: OTPPurpose = OTPPurpose.EMAIL_VERIFICATION,
        ttl_seconds: int = 600
    ) -> None:
        """
        Store OTP in Redis with expiration.
        
        Args:
            user_id: User's unique identifier
            otp: OTP to store
            purpose: Purpose of OTP (from OTPPurpose enum)
            ttl_seconds: Time to live in seconds (default 10 minutes)
        """
        key = f"otp:{purpose.value}:{user_id}"
        await self.redis.setex(key, ttl_seconds, otp)

    async def verify_otp(
        self,
        user_id: str,
        otp: str,
        purpose: OTPPurpose = OTPPurpose.EMAIL_VERIFICATION
    ) -> bool:
        """
        Verify OTP and delete if correct.
        
        Args:
            user_id: User's unique identifier
            otp: OTP to verify
            purpose: Purpose of OTP (from OTPPurpose enum)
            
        Returns:
            True if OTP is valid, False otherwise
        """
        key = f"otp:{purpose.value}:{user_id}"
        stored_otp = await self.redis.get(key)
        
        if stored_otp and stored_otp == otp:
            # Delete OTP after successful verification (single-use)
            await self.redis.delete(key)
            return True
        
        return False

    async def store_reset_token(
        self,
        user_id: str,
        token: str,
        ttl_seconds: int = 1800
    ) -> None:
        """
        Store password reset token in Redis.
        
        Args:
            user_id: User's unique identifier
            token: Reset token
            ttl_seconds: Time to live in seconds (default 30 minutes)
        """
        # Store token -> user_id mapping
        token_key = f"reset_token:{token}"
        await self.redis.setex(token_key, ttl_seconds, user_id)
        
        # Store user_id -> token mapping (for invalidation)
        user_key = f"reset_token:user:{user_id}"
        await self.redis.setex(user_key, ttl_seconds, token)

    async def verify_reset_token(self, token: str) -> Optional[str]:
        """
        Verify password reset token and return user_id.
        
        Args:
            token: Reset token to verify
            
        Returns:
            User ID if token is valid, None otherwise
        """
        token_key = f"reset_token:{token}"
        user_id = await self.redis.get(token_key)
        
        if user_id:
            # Delete token after verification (single-use)
            await self.redis.delete(token_key)
            user_key = f"reset_token:user:{user_id}"
            await self.redis.delete(user_key)
            return user_id
        
        return None

    async def invalidate_reset_tokens(self, user_id: str) -> None:
        """
        Invalidate all password reset tokens for a user.
        
        Args:
            user_id: User's unique identifier
        """
        user_key = f"reset_token:user:{user_id}"
        token = await self.redis.get(user_key)
        
        if token:
            token_key = f"reset_token:{token}"
            await self.redis.delete(token_key)
            await self.redis.delete(user_key)

    async def send_email(
        self,
        to_email: str,
        template: NotificationTemplate,
        context: Dict[str, any]
    ) -> None:
        """
        Send email using template.
        
        Note: This is a placeholder that logs to console.
        In production, integrate with AWS SES, SendGrid, etc.
        
        Args:
            to_email: Recipient email address
            template: Email template (from NotificationTemplate enum)
            context: Template context variables
        """
        # Log to console for now
        print("\n" + "="*80)
        print(f"📧 EMAIL NOTIFICATION")
        print("="*80)
        print(f"To: {to_email}")
        print(f"Template: {template.value}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        print("-"*80)
        
        if template == NotificationTemplate.SEC_002_NEW_DEVICE:
            # New device security alert
            self._log_security_alert(context)
        elif template == NotificationTemplate.AUTH_003_PASSWORD_RESET:
            # Password reset email
            self._log_password_reset(context)
        elif template == NotificationTemplate.AUTH_002_EMAIL_VERIFICATION:
            # Email verification
            self._log_email_verification(context)
        
        print("="*80 + "\n")

    def _log_security_alert(self, context: Dict[str, any]) -> None:
        """Log security alert email to console."""
        print("Subject: 🔐 New Device Login Detected")
        print("\nDear User,")
        print("\nWe detected a login to your Harvest account from a new device:")
        print(f"\n  Device Type: {context.get('device_type', 'Unknown')}")
        print(f"  Browser: {context.get('browser', 'Unknown')}")
        print(f"  Operating System: {context.get('os', 'Unknown')}")
        print(f"  IP Address: {context.get('ip_address', 'Unknown')}")
        print(f"  Location: {context.get('city', 'Unknown')}, {context.get('country', 'Unknown')}")
        print(f"  Time: {context.get('timestamp', 'Unknown')}")
        print(f"  Device Fingerprint: {context.get('fingerprint', 'Unknown')[:16]}...")
        print("\nIf this was you, you can safely ignore this email.")
        print("If you don't recognize this activity, please:")
        print("  1. Change your password immediately")
        print("  2. Review your recent account activity")
        print("  3. Contact our support team")
        print("\nBest regards,")
        print("Harvest Security Team")

    def _log_password_reset(self, context: Dict[str, any]) -> None:
        """Log password reset email to console."""
        print("Subject: 🔑 Password Reset Request")
        print("\nDear User,")
        print("\nWe received a request to reset your Harvest account password.")
        print(f"\nReset Token: {context.get('reset_token', 'N/A')}")
        print(f"Valid for: {context.get('valid_minutes', 30)} minutes")
        print(f"\nReset Link: https://harvest.ae/reset-password?token={context.get('reset_token', 'N/A')}")
        print("\nIf you didn't request this, please ignore this email.")
        print("Your password will remain unchanged.")
        print("\nBest regards,")
        print("Harvest Team")

    def _log_email_verification(self, context: Dict[str, any]) -> None:
        """Log email verification to console."""
        print("Subject: ✅ Verify Your Email Address")
        print("\nDear User,")
        print("\nThank you for registering with Harvest!")
        print(f"\nYour verification code is: {context.get('otp', 'N/A')}")
        print(f"Valid for: {context.get('valid_minutes', 10)} minutes")
        print("\nPlease enter this code to verify your email address.")
        print("\nBest regards,")
        print("Harvest Team")

    async def send_new_device_alert(
        self,
        user_email: str,
        device_info: Dict[str, any]
    ) -> None:
        """
        Send new device login alert email.
        
        Args:
            user_email: User's email address
            device_info: Device information dictionary
        """
        await self.send_email(
            to_email=user_email,
            template=NotificationTemplate.SEC_002_NEW_DEVICE,
            context=device_info
        )

    async def send_password_reset_email(
        self,
        user_email: str,
        reset_token: str,
        valid_minutes: int = 30
    ) -> None:
        """
        Send password reset email.
        
        Args:
            user_email: User's email address
            reset_token: Password reset token
            valid_minutes: Token validity in minutes
        """
        await self.send_email(
            to_email=user_email,
            template=NotificationTemplate.AUTH_003_PASSWORD_RESET,
            context={
                "reset_token": reset_token,
                "valid_minutes": valid_minutes
            }
        )

    async def send_verification_email(
        self,
        user_email: str,
        otp: str,
        valid_minutes: int = 10
    ) -> None:
        """
        Send email verification OTP.
        
        Args:
            user_email: User's email address
            otp: Verification OTP
            valid_minutes: OTP validity in minutes
        """
        await self.send_email(
            to_email=user_email,
            template=NotificationTemplate.AUTH_002_EMAIL_VERIFICATION,
            context={
                "otp": otp,
                "valid_minutes": valid_minutes
            }
        )
