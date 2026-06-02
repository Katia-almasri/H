"""Admin registration request schema."""

from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class AdminRegisterRequest(BaseModel):
    """Request schema for admin registration (temporary route)."""

    email: EmailStr = Field(..., description="Admin email address")
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=8, max_length=100, description="Admin password")
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name")
    phone_number: str | None = Field(None, description="Phone number (optional)")
    department: str | None = Field(None, max_length=100, description="Department")
    position: str | None = Field(None, max_length=100, description="Position/title")
    is_super_admin: bool = Field(False, description="Grant super admin privileges")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Username can only contain letters, numbers, hyphens, and underscores")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "admin@harvest.ae",
                "username": "admin_user",
                "password": "SecureAdmin123!",
                "full_name": "Admin User",
                "phone_number": "+971501234567",
                "department": "Operations",
                "position": "Platform Manager",
                "is_super_admin": False,
            }
        }
    }
