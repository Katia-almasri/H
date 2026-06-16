"""Investment experience answer enumeration for Q5 of the suitability questionnaire."""

from enum import StrEnum


class InvestmentExperience(StrEnum):
    NONE = "none"
    STOCKS_BONDS = "stocks_bonds"
    REAL_ESTATE = "real_estate"
