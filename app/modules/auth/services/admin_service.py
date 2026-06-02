"""Admin registration service."""

import uuid
from datetime import datetime
from typing import Tuple

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.hash import argon2

from app.modules.auth.models.user import User
from app.modules.auth.models.admin import Admin
from app.modules.auth.enums import UserRole, AccountStatus, OTPPurpose
from app.modules.auth.repositories import UserRepository
from app.modules.auth.repositories.admin_repository import AdminRepository
from app.modules.auth.services.token_service import TokenService
from app.modules.auth.services.notification_service import NotificationService


class AdminService:
    """Service for admin registration and management."""

    def __init__(self, db: AsyncSession, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client
        self.user_repo = UserRepository(db)
        self.admin_repo = AdminRepository(db)
        self.token_service = TokenService(redis_client)
        self.notification_service = NotificationService(redis_client)

    async def register_admin(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str,
        phone_number: str | None = None,
        department: str | None = None,
        position: str | None = None,
        is_super_admin: bool = False,
    ) -> Tuple[User, Admin, str, str]:
        """
        Register a new admin account.

        Creates a User with role=ADMIN and an associated Admin profile.
        Issues tokens immediately (temp route — no email verification required).

        Returns:
            Tuple of (User, Admin, access_token, refresh_token)

        Raises:
            ValueError: If email or username already taken
        """
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            raise ValueError("Email already registered")

        existing_user = await self.user_repo.get_by_username(username)
        if existing_user:
            raise ValueError("Username already taken")

        hashed_password = argon2.hash(password)

        # Create user with ADMIN role
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            phone_number=phone_number,
            role=UserRole.ADMIN.value,
            account_status=AccountStatus.NEEDS_EMAIL_VERIFICATION.value,
            is_active=True,
            is_email_verified=False,
            failed_login_attempts="0",
        )
        user = await self.user_repo.create(user)

        # Create admin profile
        admin = Admin(
            id=str(uuid.uuid4()),
            user_id=user.id,
            department=department,
            position=position,
            is_super_admin=is_super_admin,
        )
        admin = await self.admin_repo.create(admin)

        # Send verification OTP
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

        # Issue tokens immediately for temp admin registration
        access_token = self.token_service.create_access_token(
            user.id, user.email, user.role
        )
        refresh_token = self.token_service.create_refresh_token()

        return user, admin, access_token, refresh_token
