"""User role enumeration."""

import enum


class UserRole(str, enum.Enum):
    INVESTOR = "investor"
    ADMIN = "admin"
    DEVELOPER = "developer"
