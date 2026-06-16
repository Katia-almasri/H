"""Auth request schemas."""

from app.modules.auth.schemas.requests.register import RegisterRequest
from app.modules.auth.schemas.requests.login import LoginRequest
from app.modules.auth.schemas.requests.forgot_password import ForgotPasswordRequest
from app.modules.auth.schemas.requests.reset_password import ResetPasswordRequest
from app.modules.auth.schemas.requests.admin_register import AdminRegisterRequest
from app.modules.auth.schemas.requests.update_profile import UpdateInvestorProfileRequest

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "AdminRegisterRequest",
    "UpdateInvestorProfileRequest",
]
