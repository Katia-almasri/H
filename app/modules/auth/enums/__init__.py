"""Auth module enumerations."""

from app.modules.auth.enums.user_role import UserRole
from app.modules.auth.enums.account_status import AccountStatus
from app.modules.auth.enums.audit_action import AuditAction
from app.modules.auth.enums.notification_template import NotificationTemplate
from app.modules.auth.enums.otp_purpose import OTPPurpose

__all__ = [
    "UserRole",
    "AccountStatus",
    "AuditAction",
    "NotificationTemplate",
    "OTPPurpose",
]
