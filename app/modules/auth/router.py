"""Auth router — investor registration + shared auth + investor 2FA."""

from typing import Annotated

from fastapi import APIRouter, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from starlette.status import HTTP_201_CREATED

from app.database import get_db
from app.redis_client import get_redis
from app.modules.auth.services import AuthService, InvestorTwoFAService, TokenService, AdminService
from app.modules.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    LoginResponse,
    LogoutResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenResponse,
    AdminRegisterRequest,
    AdminResponse,
    UpdateInvestorProfileRequest,
)
from packages.core.exceptions import (
    AuthenticationException,
    ConflictException,
    NotFoundException,
    AccountLockedException,
    RateLimitException,
    ValidationException,
)
from packages.core.response import api_response
from packages.auth.dependencies import RoleChecker
from app.modules.auth.enums import UserRole

# ── Routers ───────────────────────────────────────────────────────────────────
router = APIRouter(tags=["Authentication"])
security = HTTPBearer(auto_error=True)

# ── Role-based dependencies ───────────────────────────────────────────────────
require_investor = RoleChecker(allowed_roles=[UserRole.INVESTOR])
require_admin = RoleChecker(allowed_roles=[UserRole.ADMIN])


# ── Dependencies ──────────────────────────────────────────────────────────────

def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> AuthService:
    return AuthService(db, redis_client)


def get_two_fa_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> InvestorTwoFAService:
    return InvestorTwoFAService(db, redis_client)


def get_token_service(
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> TokenService:
    return TokenService(redis_client)


def get_admin_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> AdminService:
    return AdminService(db, redis_client)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> str:
    payload = token_service.verify_access_token(credentials.credentials)
    if not payload:
        raise AuthenticationException("Invalid or expired token")
    return payload["sub"]


# ══════════════════════════════════════════════════════════════════════════════
# INVESTOR REGISTRATION (role-specific)
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/investors/register", status_code=status.HTTP_201_CREATED, summary="Register investor")
async def register_investor(
    body: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Register a new investor account. Sends email OTP for verification."""
    try:
        user = await auth_service.register_user(
            email=body.email,
            username=body.username,
            password=body.password,
            full_name=body.full_name,
            phone_number=body.phone_number,
        )
    except ValueError as e:
        raise ConflictException(str(e))

    return api_response(
        message="Registration successful. Verify your email with the OTP sent to your inbox.",
        data={"user": UserResponse.model_validate(user).model_dump()},
        code=HTTP_201_CREATED,
    )


@router.put("/investors/me", summary="Update investor profile")
async def update_investor_profile(
    body: UpdateInvestorProfileRequest,
    user_id: Annotated[str, Depends(require_investor)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Update the authenticated investor's profile.

    Updates user-level fields (username, full_name, phone_number).
    Email changes are not supported here — they require a separate
    re-verification flow.
    """
    try:
        user = await auth_service.update_investor_profile(
            user_id=user_id,
            username=body.username,
            full_name=body.full_name,
            phone_number=body.phone_number,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise NotFoundException(msg)
        raise ConflictException(msg)

    return api_response(
        message="Profile updated successfully.",
        data={"user": UserResponse.model_validate(user).model_dump()},
    )


# ══════════════════════════════════════════════════════════════════════════════
# SHARED AUTH (all roles)
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/auth/login", summary="Login")
async def login(
    body: LoginRequest,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Authenticate any user (investor, admin, developer)."""
    try:
        user, access_token, refresh_token = await auth_service.login(
            email=body.email,
            password=body.password,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent", ""),
            accept_language=request.headers.get("Accept-Language"),
            accept_encoding=request.headers.get("Accept-Encoding"),
        )
    except PermissionError as e:
        msg = str(e)
        if "locked" in msg.lower():
            raise AccountLockedException(msg)
        raise RateLimitException(msg)
    except ValueError as e:
        raise AuthenticationException(str(e))

    data = LoginResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=auth_service.token_service.get_token_expiry(),
        ),
        requires_2fa=False,
    )
    return api_response(message="Login successful", data=data.model_dump())


@router.post("/auth/verify-email", summary="Verify email with OTP")
async def verify_email(
    user_id: str,
    otp: str,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Verify email for any role. Returns tokens on success."""
    result = await auth_service.verify_email_with_otp(user_id, otp)
    if not result:
        raise ValidationException("Invalid or expired OTP")

    user, access_token, refresh_token = result
    data = {
        "user": UserResponse.model_validate(user).model_dump(),
        "tokens": TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=auth_service.token_service.get_token_expiry(),
        ).model_dump(),
    }
    return api_response(message="Email verified. Account active.", data=data)


@router.post("/auth/resend-otp", summary="Resend verification OTP")
async def resend_otp(
    user_id: str,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    try:
        await auth_service.resend_verification_otp(user_id)
    except ValueError as e:
        raise ValidationException(str(e))
    return api_response(message="Verification code resent.")


@router.post("/auth/forgot-password", summary="Request password reset")
async def forgot_password(
    body: ForgotPasswordRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    await auth_service.request_password_reset(body.email)
    return api_response(message="If the email exists, a reset link has been sent.")


@router.post("/auth/reset-password", summary="Reset password with token")
async def reset_password(
    body: ResetPasswordRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    try:
        await auth_service.reset_password_with_token(token=body.token, new_password=body.new_password)
    except ValueError as e:
        raise ValidationException(str(e))
    return api_response(message="Password reset successfully. Please login again.")


@router.post("/auth/logout", summary="Logout")
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    payload = auth_service.token_service.verify_access_token(credentials.credentials)
    if not payload:
        raise AuthenticationException("Invalid or expired token")
    await auth_service.logout(credentials.credentials, payload["sub"])
    return api_response(message="Logged out successfully", data=LogoutResponse(message="Logged out successfully").model_dump())


@router.post("/auth/refresh", summary="Refresh access token")
async def refresh_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    try:
        new_access, new_refresh = await auth_service.refresh_access_token(credentials.credentials)
    except ValueError as e:
        raise AuthenticationException(str(e))
    data = TokenResponse(access_token=new_access, refresh_token=new_refresh, token_type="bearer", expires_in=auth_service.token_service.get_token_expiry())
    return api_response(message="Token refreshed", data=data.model_dump())


@router.get("/auth/me", summary="Get current user")
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    payload = auth_service.token_service.verify_access_token(credentials.credentials)
    if not payload:
        raise AuthenticationException("Invalid or expired token")
    user = await auth_service.user_repo.get_by_id(payload["sub"])
    if not user:
        raise NotFoundException("User not found")
    return api_response(message="User retrieved", data=UserResponse.model_validate(user).model_dump())


# ══════════════════════════════════════════════════════════════════════════════
# INVESTOR 2FA (investor-only)
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/investors/2fa/setup", summary="Initiate 2FA setup")
async def setup_2fa(
    user_id: Annotated[str, Depends(require_investor)],
    two_fa_service: Annotated[InvestorTwoFAService, Depends(get_two_fa_service)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
):
    """Generate TOTP secret, QR URI, and 8 recovery codes for investor."""
    payload = token_service.verify_access_token(credentials.credentials)
    email = payload.get("email", "")
    result = await two_fa_service.initiate_setup(user_id, email)
    return api_response(message="2FA setup initiated. Save your recovery codes.", data=result)


@router.post("/investors/2fa/acknowledge-codes", summary="Acknowledge recovery codes")
async def acknowledge_codes(
    user_id: Annotated[str, Depends(require_investor)],
    two_fa_service: Annotated[InvestorTwoFAService, Depends(get_two_fa_service)],
):
    success = await two_fa_service.acknowledge_recovery_codes(user_id)
    if not success:
        raise ValidationException("No pending 2FA setup found")
    return api_response(message="Recovery codes acknowledged.")


@router.post("/investors/2fa/confirm", summary="Confirm 2FA with TOTP code")
async def confirm_2fa(
    totp_code: str,
    user_id: Annotated[str, Depends(require_investor)],
    two_fa_service: Annotated[InvestorTwoFAService, Depends(get_two_fa_service)],
):
    success = await two_fa_service.confirm_setup(user_id, totp_code)
    if not success:
        raise ValidationException("Invalid TOTP code or codes not acknowledged.")
    return api_response(message="2FA enabled successfully.")


@router.post("/investors/2fa/verify", summary="Verify TOTP for protected action")
async def verify_2fa(
    totp_code: str,
    user_id: Annotated[str, Depends(require_investor)],
    two_fa_service: Annotated[InvestorTwoFAService, Depends(get_two_fa_service)],
):
    valid = await two_fa_service.verify_totp(user_id, totp_code)
    if not valid:
        raise AuthenticationException("Invalid TOTP code")
    return api_response(message="2FA verification successful.")


@router.post("/investors/2fa/recover", summary="Use recovery code")
async def recover_2fa(
    recovery_code: str,
    request: Request,
    user_id: Annotated[str, Depends(require_investor)],
    two_fa_service: Annotated[InvestorTwoFAService, Depends(get_two_fa_service)],
):
    success = await two_fa_service.use_recovery_code(
        user_id=user_id,
        code=recovery_code,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    if not success:
        raise ValidationException("Invalid recovery code")
    return api_response(message="Recovery code accepted. 2FA disabled. Re-enroll within 24 hours.")


@router.get("/investors/2fa/status", summary="Get 2FA status")
async def get_2fa_status(
    user_id: Annotated[str, Depends(require_investor)],
    two_fa_service: Annotated[InvestorTwoFAService, Depends(get_two_fa_service)],
):
    data = await two_fa_service.get_status(user_id)
    return api_response(message="2FA status retrieved.", data=data)


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN REGISTRATION (temporary — replace with invite-based flow later)
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/admins/register", status_code=status.HTTP_201_CREATED, summary="Register admin (temp)")
async def register_admin(
    body: AdminRegisterRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
):
    """
    Temporary admin registration endpoint.
    TODO: Replace with invite-based admin onboarding secured by existing super-admin auth.
    """
    try:
        user, admin, access_token, refresh_token = await admin_service.register_admin(
            email=body.email,
            username=body.username,
            password=body.password,
            full_name=body.full_name,
            phone_number=body.phone_number,
            department=body.department,
            position=body.position,
            is_super_admin=body.is_super_admin,
        )
    except ValueError as e:
        raise ConflictException(str(e))

    return api_response(
        message="Admin registration successful. Verify your email with the OTP sent to your inbox.",
        data={
            "user": UserResponse.model_validate(user).model_dump(),
            "admin": AdminResponse.model_validate(admin).model_dump(),
            "tokens": TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=admin_service.token_service.get_token_expiry(),
            ).model_dump(),
        },
        code=HTTP_201_CREATED,
    )
