"""Liquidity horizon answer enumeration for Q4 of the suitability questionnaire."""

from enum import StrEnum


class LiquidityHorizon(StrEnum):
    UNDER_2YR = "under_2yr"
    BETWEEN_2_5YR = "between_2_5yr"
    OVER_5YR = "over_5yr"
