"""User response schema."""

from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserResponse(BaseModel):
    """Response schema for user data."""
    
    id: str
    email: EmailStr
    username: str
    full_name: str | None
    phone_number: str | None
    role: str
    account_status: str
    is_active: bool
    is_email_verified: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "investor@example.com",
                "username": "investor123",
                "full_name": "John Doe",
                "phone_number": "+971501234567",
                "role": "investor",
                "account_status": "active",
                "is_active": True,
                "is_email_verified": True,
                "created_at": "2024-01-01T00:00:00Z",
                "last_login_at": "2024-01-15T10:30:00Z"
            }
        }
    }
