"""Login response schema."""

from pydantic import BaseModel
from app.modules.auth.schemas.responses.user import UserResponse
from app.modules.auth.schemas.responses.token import TokenResponse


class LoginResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse
    requires_2fa: bool = False
