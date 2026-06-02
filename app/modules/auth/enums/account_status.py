"""Account status enumeration."""

import enum


class AccountStatus(str, enum.Enum):
    NEEDS_EMAIL_VERIFICATION = "needs_email_verification"
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
