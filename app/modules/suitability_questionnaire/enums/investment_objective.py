"""Investment objective answer enumeration for Q7 of the suitability questionnaire."""

from enum import StrEnum


class InvestmentObjective(StrEnum):
    INCOME = "income"
    CAPITAL_GROWTH = "capital_growth"
    BOTH = "both"
