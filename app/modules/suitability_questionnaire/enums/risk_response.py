"""Risk response answer enumeration for Q6 of the suitability questionnaire."""

from enum import StrEnum


class RiskResponse(StrEnum):
    SELL_IMMEDIATELY = "sell_immediately"
    WAIT_AND_MONITOR = "wait_and_monitor"
    BUY_MORE = "buy_more"
