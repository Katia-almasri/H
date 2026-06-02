"""Auth module schemas."""

from app.modules.auth.schemas.requests import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    AdminRegisterRequest,
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
    "UserResponse",
    "TokenResponse",
    "RegisterResponse",
    "LoginResponse",
    "LogoutResponse",
    "AdminResponse",
]
