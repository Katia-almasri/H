"""Net worth bracket answer enumeration for Q1 of the suitability questionnaire."""

from enum import StrEnum


class NetWorthBracket(StrEnum):
    UNDER_100K = "under_100k"
    BETWEEN_100K_500K = "between_100k_500k"
    OVER_500K = "over_500k"
