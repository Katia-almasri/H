"""Real estate allocation bracket answer enumeration for Q3 of the suitability questionnaire."""

from enum import StrEnum


class AllocationBracket(StrEnum):
    OVER_50PCT = "over_50pct"
    BETWEEN_20_50PCT = "between_20_50pct"
    UNDER_20PCT = "under_20pct"
