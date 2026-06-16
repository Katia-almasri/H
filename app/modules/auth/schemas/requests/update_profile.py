"""Update investor profile request schema."""

from pydantic import BaseModel, Field, field_validator
import re


class UpdateInvestorProfileRequest(BaseModel):
    """Request schema for updating an investor's profile (user-level fields).

    All fields are optional — only the provided fields will be updated.
    Email is intentionally excluded: changing email requires a separate
    re-verification flow.
    """

    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
        description="New unique username (lowercased, alphanumeric, '-' or '_')",
    )
    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Full legal name",
    )
    phone_number: str | None = Field(
        default=None,
        max_length=20,
        description="Phone number in E.164 format (e.g. +971501234567)",
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Username can only contain letters, numbers, hyphens, and underscores"
            )
        return v.lower()

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        if not re.match(r"^\+?[0-9]{7,19}$", v):
            raise ValueError("Phone number must be 7-20 digits, optionally prefixed with '+'")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "investor123",
                "full_name": "John Doe",
                "phone_number": "+971501234567",
            }
        }
    }
