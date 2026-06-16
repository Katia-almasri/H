"""Suitability questionnaire warning reason code enumeration."""

from enum import StrEnum


class WarningReasonCode(StrEnum):
    SHORT_HORIZON = "SHORT_HORIZON"
    HIGH_CONCENTRATION = "HIGH_CONCENTRATION"
    LOW_EXPERIENCE = "LOW_EXPERIENCE"
