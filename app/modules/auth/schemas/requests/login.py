"""Login request schema."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Request schema for user login."""
    
    email: str = Field(..., description="Email or username")
    password: str = Field(..., description="User password")
    remember_me: bool = Field(default=False, description="Extended session duration")

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "investor@example.com",
                "password": "SecurePass123!",
                "remember_me": False
            }
        }
    }
