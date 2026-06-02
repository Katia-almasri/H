"""Register response schema."""

from pydantic import BaseModel
from app.modules.auth.schemas.responses.user import UserResponse
from app.modules.auth.schemas.responses.token import TokenResponse


class RegisterResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse
    message: str = "Registration successful. Please verify your email."
