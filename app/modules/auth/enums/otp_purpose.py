"""OTP purpose enumeration."""

import enum


class OTPPurpose(str, enum.Enum):
    EMAIL_VERIFICATION = "email_verification"
    TWO_FACTOR_AUTH = "two_factor_auth"
    PASSWORD_RESET = "password_reset"
    PHONE_VERIFICATION = "phone_verification"
    TRANSACTION_CONFIRMATION = "transaction_confirmation"
