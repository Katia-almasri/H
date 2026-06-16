"""Auth module schemas."""

from app.modules.auth.schemas.requests import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    AdminRegisterRequest,
    UpdateInvestorProfileRequest,
)
from app.modules.auth.schemas.responses import (
    UserResponse,
    TokenResponse,
    RegisterResponse,
    LoginResponse,
    LogoutResponse,
    AdminResponse,
)

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "AdminRegisterRequest",
    "UpdateInvestorProfileRequest",
    "UserResponse",
    "TokenResponse",
    "RegisterResponse",
    "LoginResponse",
    "LogoutResponse",
    "AdminResponse",
]
