"""Suitability retake request status enumeration."""

import enum


class RetakeStatus(str, enum.Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETED = "COMPLETED"
