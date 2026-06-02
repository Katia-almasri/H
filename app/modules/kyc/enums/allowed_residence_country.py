"""Allowed residence countries for KYC eligibility."""

import enum


class AllowedResidenceCountry(str, enum.Enum):
    """Countries where investors are allowed to reside and invest from."""
    UAE = "AE"
    BAHRAIN = "BH"
    SAUDI_ARABIA = "SA"
    OMAN = "OM"
    KUWAIT = "KW"
    QATAR = "QA"
    JORDAN = "JO"
    EGYPT = "EG"
    UNITED_KINGDOM = "GB"
    UNITED_STATES = "US"
    CANADA = "CA"
    AUSTRALIA = "AU"
    GERMANY = "DE"
    FRANCE = "FR"
    SINGAPORE = "SG"
    INDIA = "IN"
    PAKISTAN = "PK"
