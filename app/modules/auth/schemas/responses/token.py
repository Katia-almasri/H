"""Token response schema."""

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """Response schema for authentication tokens."""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "550e8400-e29b-41d4-a716-446655440000",
                "token_type": "bearer",
                "expires_in": 900
            }
        }
    }
