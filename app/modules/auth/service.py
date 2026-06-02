import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import uuid
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User, UserSession, EmailVerification, PasswordReset
from app.modules.auth.repository import (
    UserRepository,
    SessionRepository,
    EmailVerificationRepository,
    PasswordResetRepository
)
from app.modules.auth.schemas import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    UserProfile,
    RefreshTokenResponse
)
from packages.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    get_token_expiry
)
from packages.auth.password import hash_password, verify_password
from packages.core.config import settings
from packages.core.enums import UserRole, AccountStatus, AuditAction
from packages.core.exceptions import (
    ConflictException,
    AuthenticationException,
    ValidationException,
    RateLimitException
)


class AuthService:
    """Authentication service - orchestrates auth business logic"""
    
    def __init__(
        self,
        db: AsyncSession,
        redis: Redis,
        tenant_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        self.db = db
        self.redis = redis
        self.tenant_id = tenant_id
        self.ip_address = ip_address
        self.user_agent = user_agent
        
        # Initialize repositories
        self.user_repo = UserRepository(db, tenant_id)
        self.session_repo = SessionRepository(db, tenant_id)
        self.email_verif_repo = EmailVerificationRepository(db, tenant_id)
        self.password_reset_repo = PasswordResetRepository(db, tenant_id)
    
    async def register(self, request: RegisterRequest) -> RegisterResponse:
        """
        Register a new user.
        
        Steps:
        1. Check if email already exists
        2. Hash password using Argon2id
        3. Create user record
        4. Generate and store email verification OTP
        5. Send verification email (async)
        
        Returns:
            RegisterResponse with user details
            
        Raises:
            ConflictException: If email already exists
        """
        # Check if user already exists
        existing_user = await self.user_repo.get_by_email(request.email)
        if existing_user:
            raise ConflictException(
                message="Email address already registered",
                details={"email": request.email}
            )
        
        # Hash password
        password_hash = hash_password(request.password)
        
        # Create user
        user = User(
            email=request.email,
            password_hash=password_hash,
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone,
            role=UserRole.INVESTOR,
            status=AccountStatus.PENDING_VERIFICATION,
            email_verified=False,
            tenant_id=self.tenant_id
        )
        
        user = await self.user_repo.create(user)
        
        # Generate OTP for email verification
        await self._generate_email_otp(user.id, user.email)
        
        # TODO: Send verification email asynchronously
        # asyncio.create_task(send_verification_email(user.email, otp))
        
        return RegisterResponse(
            user_id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            status=user.status
        )
    
    async def login(self, request: LoginRequest) -> LoginResponse:
        """
        Authenticate user and issue tokens.
        
        Steps:
        1. Check rate limiting
        2. Find user by email
        3. Check account status (locked, suspended)
        4. Verify password
        5. Handle failed login attempts
        6. Generate access + refresh tokens
        7. Store session
        8. Update last login info
        
        Returns:
            LoginResponse with tokens and user profile
            
        Raises:
            AuthenticationException: If credentials invalid or account locked
            RateLimitException: If too many login attempts
        """
        # Check rate limit
        await self._check_login_rate_limit(request.email)
        
        # Get user
        user = await self.user_repo.get_by_email(request.email)
        if not user:
            raise AuthenticationException("Invalid email or password")
        
        # Check if account is locked
        if user.status == AccountStatus.LOCKED:
            if user.locked_until and user.locked_until > datetime.now(timezone.utc):
                raise AuthenticationException(
                    f"Account is locked until {user.locked_until.isoformat()}",
                    details={"locked_until": user.locked_until.isoformat()}
                )
        
        # Check if account is suspended
        if user.status == AccountStatus.SUSPENDED:
            raise AuthenticationException("Account is suspended. Contact support.")
        
        # Verify password
        if not verify_password(request.password, user.password_hash):
            # Increment failed attempts
            failed_count = await self.user_repo.increment_failed_login(user.id)
            
            # Lock account if threshold exceeded
            if failed_count >= settings.LOGIN_LOCKOUT_THRESHOLD:
                locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.LOGIN_LOCKOUT_DURATION_MINUTES
                )
                await self.user_repo.lock_account(user.id, locked_until)
                raise AuthenticationException(
                    f"Account locked due to too many failed attempts. Try again after {locked_until.isoformat()}"
                )
            
            raise AuthenticationException("Invalid email or password")
        
        # Generate tokens
        access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            tenant_id=self.tenant_id
        )
        
        refresh_token = create_refresh_token()
        refresh_token_hash = self._hash_token(refresh_token)
        
        # Store session
        session = UserSession(
            user_id=user.id,
            refresh_token_hash=refresh_token_hash,
            expires_at=get_token_expiry("refresh"),
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            tenant_id=self.tenant_id
        )
        await self.session_repo.create(session)
        
        # Update last login
        await self.user_repo.update_login_info(user.id, self.ip_address)
        
        # Build response
        user_profile = UserProfile(
            user_id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            status=user.status,
            email_verified=user.email_verified,
            two_fa_enabled=user.two_fa_enabled,
            last_login_at=user.last_login_at
        )
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_profile
        )
    
    async def refresh_tokens(self, refresh_token: str) -> RefreshTokenResponse:
        """
        Refresh access token using refresh token.
        Implements single-use refresh token rotation.
        
        Steps:
        1. Hash and lookup refresh token
        2. Validate session (not revoked, not expired)
        3. Get user
        4. Revoke old refresh token
        5. Issue new access + refresh tokens
        6. Store new session
        
        Returns:
            RefreshTokenResponse with new tokens
            
        Raises:
            AuthenticationException: If token invalid or revoked
        """
        token_hash = self._hash_token(refresh_token)
        
        # Get session
        session = await self.session_repo.get_by_token_hash(token_hash)
        if not session:
            raise AuthenticationException("Invalid or expired refresh token")
        
        # Get user
        user = await self.user_repo.get_by_id(session.user_id)
        if not user:
            raise AuthenticationException("User not found")
        
        # Revoke old session (single-use rotation)
        await self.session_repo.revoke(session.id)
        
        # Generate new tokens
        new_access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            tenant_id=self.tenant_id
        )
        
        new_refresh_token = create_refresh_token()
        new_refresh_token_hash = self._hash_token(new_refresh_token)
        
        # Store new session
        new_session = UserSession(
            user_id=user.id,
            refresh_token_hash=new_refresh_token_hash,
            expires_at=get_token_expiry("refresh"),
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            tenant_id=self.tenant_id
        )
        await self.session_repo.create(new_session)
        
        return RefreshTokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    async def logout(self, refresh_token: str) -> None:
        """
        Logout user by revoking refresh token.
        
        Args:
            refresh_token: Refresh token to revoke
        """
        token_hash = self._hash_token(refresh_token)
        session = await self.session_repo.get_by_token_hash(token_hash)
        
        if session:
            await self.session_repo.revoke(session.id)
            
            # Add to Redis blocklist
            await self._add_to_blocklist(refresh_token)
    
    async def verify_email(self, email: str, otp: str) -> None:
        """
        Verify user email with OTP.
        
        Args:
            email: User email
            otp: 6-digit OTP code
            
        Raises:
            ValidationException: If OTP invalid or expired
        """
        # Get verification record
        verification = await self.email_verif_repo.get_latest_by_email(email)
        if not verification:
            raise ValidationException("No pending verification found for this email")
        
        # Check attempts
        if verification.attempts >= 5:
            raise ValidationException("Too many verification attempts. Request a new code.")
        
        # Verify OTP
        otp_hash = self._hash_token(otp)
        if otp_hash != verification.otp_hash:
            await self.email_verif_repo.increment_attempts(verification.id)
            raise ValidationException("Invalid verification code")
        
        # Mark as verified
        await self.email_verif_repo.mark_verified(verification.id)
        await self.user_repo.verify_email(verification.user_id)
    
    async def resend_otp(self, email: str) -> None:
        """
        Resend email verification OTP.
        
        Args:
            email: User email
            
        Raises:
            ValidationException: If user not found or already verified
        """
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise ValidationException("User not found")
        
        if user.email_verified:
            raise ValidationException("Email already verified")
        
        await self._generate_email_otp(user.id, email)
        
        # TODO: Send email asynchronously
    
    async def _generate_email_otp(self, user_id: uuid.UUID, email: str) -> str:
        """Generate and store 6-digit OTP for email verification"""
        otp = "".join([str(secrets.randbelow(10)) for _ in range(6)])
        otp_hash = self._hash_token(otp)
        
        verification = EmailVerification(
            user_id=user_id,
            email=email,
            otp_hash=otp_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            tenant_id=self.tenant_id
        )
        
        await self.email_verif_repo.create(verification)
        return otp
    
    async def _check_login_rate_limit(self, email: str) -> None:
        """Check Redis-based rate limiting for login attempts"""
        key = f"login_rate:{email}"
        count = await self.redis.incr(key)
        
        if count == 1:
            await self.redis.expire(key, 60)  # 1 minute window
        
        if count > 10:  # 10 attempts per minute
            raise RateLimitException("Too many login attempts. Please try again later.")
    
    async def _add_to_blocklist(self, token: str) -> None:
        """Add refresh token to Redis blocklist"""
        key = f"rt_blocklist:{self._hash_token(token)}"
        ttl = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400  # Convert days to seconds
        await self.redis.setex(key, ttl, "1")
    
    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash token using SHA-256"""
        return hashlib.sha256(token.encode()).hexdigest()
