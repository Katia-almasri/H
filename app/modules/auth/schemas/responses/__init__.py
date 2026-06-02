"""Auth response schemas."""

from app.modules.auth.schemas.responses.user import UserResponse
from app.modules.auth.schemas.responses.token import TokenResponse
from app.modules.auth.schemas.responses.register import RegisterResponse
from app.modules.auth.schemas.responses.login import LoginResponse
from app.modules.auth.schemas.responses.logout import LogoutResponse
from app.modules.auth.schemas.responses.admin import AdminResponse

__all__ = [
    "UserResponse",
    "TokenResponse",
    "RegisterResponse",
    "LoginResponse",
    "LogoutResponse",
    "AdminResponse",
]
