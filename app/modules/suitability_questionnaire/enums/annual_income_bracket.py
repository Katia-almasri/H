"""Annual income bracket answer enumeration for Q2 of the suitability questionnaire."""

from enum import StrEnum


class AnnualIncomeBracket(StrEnum):
    UNDER_50K = "under_50k"
    BETWEEN_50K_200K = "between_50k_200k"
    OVER_200K = "over_200k"
