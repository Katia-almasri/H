from enum import StrEnum


class UserRole(StrEnum):
    """User role enumeration"""
    INVESTOR = "investor"
    ADMIN = "admin"
    DEVELOPER = "developer"
    GUEST = "guest"


class AccountStatus(StrEnum):
    """Account status enumeration"""
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    LOCKED = "locked"
    CLOSED = "closed"


class AuditAction(StrEnum):
    """Audit action types"""
    USER_REGISTERED = "user_registered"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    TOKEN_REFRESHED = "token_refreshed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    EMAIL_VERIFIED = "email_verified"
    TWO_FA_ENABLED = "two_fa_enabled"
    TWO_FA_DISABLED = "two_fa_disabled"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
