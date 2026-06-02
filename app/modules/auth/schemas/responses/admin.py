"""Admin response schema."""

from pydantic import BaseModel
from datetime import datetime


class AdminResponse(BaseModel):
    """Response schema for admin profile data."""

    id: str
    user_id: str
    department: str | None
    position: str | None
    is_super_admin: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "department": "Operations",
                "position": "Platform Manager",
                "is_super_admin": False,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        }
    }
