"""Audit action enumeration."""

import enum


class AuditAction(str, enum.Enum):
    USER_REGISTERED = "user_registered"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_LOGIN_FAILED = "user_login_failed"
    TOKEN_REFRESHED = "token_refreshed"
    EMAIL_VERIFICATION_SENT = "email_verification_sent"
    EMAIL_VERIFIED = "email_verified"
    EMAIL_VERIFICATION_FAILED = "email_verification_failed"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    PASSWORD_RESET_FAILED = "password_reset_failed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    NEW_DEVICE_DETECTED = "new_device_detected"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    TWO_FA_ENABLED = "two_fa_enabled"
    TWO_FA_DISABLED = "two_fa_disabled"
    TWO_FA_VERIFIED = "two_fa_verified"
    TWO_FA_FAILED = "two_fa_failed"
    SESSION_CREATED = "session_created"
    SESSION_TERMINATED = "session_terminated"
    ALL_SESSIONS_TERMINATED = "all_sessions_terminated"
    PROFILE_UPDATED = "profile_updated"
    EMAIL_CHANGED = "email_changed"
    PHONE_CHANGED = "phone_changed"

    # Suitability
    SUITABILITY_SUBMITTED = "SUITABILITY_SUBMITTED"
    SUITABILITY_ACKNOWLEDGED = "SUITABILITY_ACKNOWLEDGED"
    SUITABILITY_INVALIDATED = "SUITABILITY_INVALIDATED"
    SUITABILITY_GATE_BLOCKED = "SUITABILITY_GATE_BLOCKED"
