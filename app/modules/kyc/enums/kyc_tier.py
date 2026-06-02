"""KYC verification tier enumeration."""

import enum


class KYCTier(str, enum.Enum):
    UNVERIFIED = "unverified"
    BASIC = "basic"
    FULL = "full"
