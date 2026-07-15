"""KYC metrics period enumeration."""

import enum


class KYCMetricPeriod(str, enum.Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
