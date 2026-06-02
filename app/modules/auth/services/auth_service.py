"""Main authentication service orchestrating all auth operations."""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.hash import argon2

from app.modules.auth.models.user import User
from app.modules.auth.models.session import UserSession
from app.modules.auth.enums import UserRole, AccountStatus, OTPPurpose
from app.modules.auth.repositories import UserRepository, SessionRepository
from app.modules.auth.services.token_service import TokenService
from app.modules.auth.services.lockout_service import LockoutService
from app.modules.auth.services.rate_limit_service import RateLimitService
from app.modules.auth.services.device_service import DeviceService
from app.modules.auth.services.notification_service import NotificationService


class AuthService:
    """Main authentication service."""

    def __init__(
        self,
        db: AsyncSession,
        redis_client: redis.Redis
    ):
        self.db = db
        self.redis = redis_client
        
        # Initialize repositories
        self.user_repo = UserRepository(db)
        self.session_repo = SessionRepository(db)
        
        # Initialize services
        self.token_service = TokenService(redis_client)
        self.lockout_service = LockoutService(redis_client, db)
        self.rate_limit_service = RateLimitService(redis_client)
        self.device_service = DeviceService(redis_client, db)
        self.notification_service = NotificationService(redis_client)

    async def register_user(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str,
        phone_number: Optional[str] = None
    ) -> User:
        """
        Register a new user. Account stays in NEEDS_EMAIL_VERIFICATION
        until the user verifies their email with the OTP.

        No tokens are issued at this stage.
        """
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            raise ValueError("Email already registered")

        existing_user = await self.user_repo.get_by_username(username)
        if existing_user:
            raise ValueError("Username already taken")

        hashed_password = argon2.hash(password)

        user = User(
            id=str(uuid.uuid4()),
            email=email,
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            phone_number=phone_number,
            role=UserRole.INVESTOR.value,
            account_status=AccountStatus.NEEDS_EMAIL_VERIFICATION.value,
            is_active=True,
            is_email_verified=False,
            failed_login_attempts="0",
        )

        user = await self.user_repo.create(user)

        # Generate and send verification OTP
        otp = self.notification_service.generate_otp()
        await self.notification_service.store_otp(
            user.id,
            otp,
            purpose=OTPPurpose.EMAIL_VERIFICATION,
            ttl_seconds=600,
        )
        await self.notification_service.send_verification_email(
            user.email, otp, valid_minutes=10
        )

        return user

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        device_name: Optional[str] = None,
        accept_language: Optional[str] = None,
        accept_encoding: Optional[str] = None
    ) -> Tuple[User, str, str]:
        """
        Authenticate user and create session.
        
        Args:
            email: Email or username
            password: Plain text password
            ip_address: IP address of the request
            user_agent: User agent string
            device_name: Device name
            accept_language: Accept-Language header
            accept_encoding: Accept-Encoding header
            
        Returns:
            Tuple of (User, access_token, refresh_token)
            
        Raises:
            ValueError: If authentication fails
            PermissionError: If account is locked or rate limited
        """
        # Check rate limit
        rate_limit = await self.rate_limit_service.check_rate_limit(ip_address)
        if not rate_limit["is_allowed"]:
            raise PermissionError(
                f"Too many login attempts. Try again in {rate_limit['retry_after']} seconds."
            )
        
        # Get user by email or username
        user = await self.user_repo.get_by_email(email)
        if not user:
            user = await self.user_repo.get_by_username(email)
        
        if not user:
            raise ValueError("Invalid credentials")
        
        # Check account lockout status
        lockout_status = await self.lockout_service.check_lockout_status(user.id)
        if lockout_status["is_locked"]:
            raise PermissionError(lockout_status["message"])
        
        # Verify password
        if not argon2.verify(password, user.hashed_password):
            # Record failed attempt
            lockout_result = await self.lockout_service.record_failed_login(
                user.id,
                ip_address
            )
            
            if lockout_result["is_locked"]:
                raise PermissionError(lockout_result["message"])
            
            raise ValueError(
                f"Invalid credentials. {lockout_result['attempts_remaining']} attempts remaining."
            )
        
        # Check if account is active
        if not user.is_active:
            raise PermissionError("Account is inactive")

        if user.account_status == AccountStatus.NEEDS_EMAIL_VERIFICATION.value:
            raise PermissionError("Email not verified. Please verify your email before logging in.")

        if user.account_status == AccountStatus.SUSPENDED.value:
            raise PermissionError("Account is suspended")
        
        # Successful login - reset failed attempts
        await self.lockout_service.reset_failed_attempts(user.id)
        
        # Get device information
        device_info = await self.device_service.get_device_info(
            user_agent or "",
            ip_address,
            accept_language,
            accept_encoding
        )
        
        # Check if this is a new device
        is_new_device = not await self.device_service.is_known_device(
            user.id,
            device_info["fingerprint"]
        )
        
        # Send security alert for new device
        if is_new_device:
            await self.notification_service.send_new_device_alert(
                user.email,
                device_info
            )
            
            # Register the device
            await self.device_service.register_device(
                user.id,
                device_info["fingerprint"]
            )
        
        # Create tokens
        access_token = self.token_service.create_access_token(
            user.id,
            user.email,
            user.role
        )
        refresh_token = self.token_service.create_refresh_token()
        
        # Create session
        session = UserSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            refresh_token_hash=self.token_service.hash_token(refresh_token),
            device_fingerprint=device_info["fingerprint"],
            device_name=device_name,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        await self.session_repo.create(session)
        
        # Update last login
        await self.user_repo.update_last_login(user.id)
        
        return user, access_token, refresh_token

    async def logout(
        self,
        refresh_token: str,
        user_id: str
    ) -> None:
        """
        Logout user by invalidating refresh token.
        
        Args:
            refresh_token: Refresh token to invalidate
            user_id: User's unique identifier
        """
        # Add refresh token to blocklist
        await self.token_service.add_to_blocklist(refresh_token, reason="logout")
        
        # Deactivate session in database
        token_hash = self.token_service.hash_token(refresh_token)
        session = await self.session_repo.get_by_token_hash(token_hash)
        
        if session:
            await self.session_repo.deactivate(session.id)

    async def refresh_access_token(
        self,
        refresh_token: str
    ) -> Tuple[str, str]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Current refresh token
            
        Returns:
            Tuple of (new_access_token, new_refresh_token)
            
        Raises:
            ValueError: If refresh token is invalid or blocklisted
        """
        # Check if token is blocklisted
        is_blocklisted = await self.token_service.is_token_blocklisted(refresh_token)
        if is_blocklisted:
            raise ValueError("Refresh token has been revoked")
        
        # Get session
        token_hash = self.token_service.hash_token(refresh_token)
        session = await self.session_repo.get_by_token_hash(token_hash)
        
        if not session:
            raise ValueError("Invalid refresh token")
        
        if not session.is_active:
            raise ValueError("Session is no longer active")
        
        if session.expires_at < datetime.utcnow():
            raise ValueError("Refresh token has expired")
        
        # Get user
        user = await self.user_repo.get_by_id(session.user_id)
        if not user:
            raise ValueError("User not found")
        
        # Blocklist old refresh token (single-use rotation)
        await self.token_service.add_to_blocklist(refresh_token, reason="token_rotation")
        
        # Deactivate old session
        await self.session_repo.deactivate(session.id)
        
        # Create new tokens
        new_access_token = self.token_service.create_access_token(
            user.id,
            user.email,
            user.role
        )
        new_refresh_token = self.token_service.create_refresh_token()
        
        # Create new session
        new_session = UserSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            refresh_token_hash=self.token_service.hash_token(new_refresh_token),
            device_name=session.device_name,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        await self.session_repo.create(new_session)
        
        # Update session last used
        await self.session_repo.update_last_used(new_session.id)
        
        return new_access_token, new_refresh_token

    async def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> None:
        """
        Change user password and invalidate all sessions.
        
        Args:
            user_id: User's unique identifier
            old_password: Current password
            new_password: New password
            
        Raises:
            ValueError: If old password is incorrect
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Verify old password
        if not argon2.verify(old_password, user.hashed_password):
            raise ValueError("Current password is incorrect")
        
        # Hash new password
        new_hashed_password = argon2.hash(new_password)
        
        # Update password
        user.hashed_password = new_hashed_password
        user.updated_at = datetime.utcnow()
        await self.user_repo.update(user)
        
        # Invalidate all user sessions
        await self.session_repo.deactivate_user_sessions(user_id)
        
        # TODO: Blocklist all refresh tokens for this user
        # This requires tracking user_id -> token mappings

    async def verify_access_token(self, token: str) -> Optional[dict]:
        """
        Verify JWT access token.
        
        Args:
            token: JWT access token
            
        Returns:
            Decoded token payload if valid, None otherwise
        """
        return self.token_service.verify_access_token(token)


    async def request_password_reset(
        self,
        email: str
    ) -> None:
        """
        Request a password reset token.
        
        Args:
            email: User's email address
            
        Note:
            Always returns success to prevent email enumeration.
            Only sends email if user exists.
        """
        # Get user by email
        user = await self.user_repo.get_by_email(email)
        
        if user:
            # Generate reset token
            reset_token = self.notification_service.generate_reset_token()
            
            # Store token in Redis (30 minutes TTL)
            await self.notification_service.store_reset_token(
                user.id,
                reset_token,
                ttl_seconds=1800  # 30 minutes
            )
            
            # Send password reset email
            await self.notification_service.send_password_reset_email(
                user.email,
                reset_token,
                valid_minutes=30
            )
        
        # Always return success (prevent email enumeration)
        return

    async def reset_password_with_token(
        self,
        token: str,
        new_password: str
    ) -> None:
        """
        Reset password using a reset token.
        
        Args:
            token: Password reset token
            new_password: New password
            
        Raises:
            ValueError: If token is invalid or expired
        """
        # Verify token and get user_id
        user_id = await self.notification_service.verify_reset_token(token)
        
        if not user_id:
            raise ValueError("Invalid or expired reset token")
        
        # Get user
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Hash new password
        new_hashed_password = argon2.hash(new_password)
        
        # Update password
        user.hashed_password = new_hashed_password
        user.updated_at = datetime.utcnow()
        await self.user_repo.update(user)
        
        # Invalidate all user sessions (force re-login)
        await self.session_repo.deactivate_user_sessions(user_id)
        
        # Invalidate any other reset tokens
        await self.notification_service.invalidate_reset_tokens(user_id)
        
        # TODO: Blocklist all refresh tokens for this user
        # This requires tracking user_id -> token mappings

    async def verify_email_with_otp(
        self,
        user_id: str,
        otp: str
    ) -> Optional[Tuple[User, str, str]]:
        """
        Verify email address using OTP.
        On success, activates the account and issues tokens.

        Returns:
            Tuple of (User, access_token, refresh_token) on success, None on failure.
        """
        is_valid = await self.notification_service.verify_otp(
            user_id, otp, purpose=OTPPurpose.EMAIL_VERIFICATION
        )

        if not is_valid:
            return None

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None

        # Activate account
        user.is_email_verified = True
        user.account_status = AccountStatus.ACTIVE.value
        user.updated_at = datetime.utcnow()
        await self.user_repo.update(user)

        # Issue tokens now that email is verified
        access_token = self.token_service.create_access_token(
            user.id, user.email, user.role
        )
        refresh_token = self.token_service.create_refresh_token()

        return user, access_token, refresh_token

    async def resend_verification_otp(
        self,
        user_id: str
    ) -> None:
        """
        Resend email verification OTP.
        
        Args:
            user_id: User's unique identifier
            
        Raises:
            ValueError: If user not found or already verified
        """
        user = await self.user_repo.get_by_id(user_id)
        
        if not user:
            raise ValueError("User not found")
        
        if user.is_email_verified:
            raise ValueError("Email already verified")
        
        # Generate new OTP
        otp = self.notification_service.generate_otp()
        
        # Store OTP in Redis (10 minutes TTL)
        await self.notification_service.store_otp(
            user_id,
            otp,
            purpose=OTPPurpose.EMAIL_VERIFICATION,
            ttl_seconds=600  # 10 minutes
        )
        
        # Send verification email
        await self.notification_service.send_verification_email(
            user.email,
            otp,
            valid_minutes=10
        )
