"""Suitability questionnaire lifecycle outcome enumeration."""

from enum import StrEnum


class SuitabilityOutcome(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    ELIGIBLE_WITH_WARNING = "ELIGIBLE_WITH_WARNING"
    NOT_SUITABLE = "NOT_SUITABLE"
