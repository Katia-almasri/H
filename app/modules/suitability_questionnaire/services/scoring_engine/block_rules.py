"""
Block-reason computation for the suitability scoring engine.

Implements the block rules defined in Appendix A.4 of the suitability
questionnaire requirements. A block reason is only produced when the
outcome is ``NOT_SUITABLE``; for all other outcomes the function returns
``None``.

Priority order (first match wins):
    1. Investment horizon < 2 years
    2. Concentration > 50%
    3. No experience AND would sell immediately
    4. Generic fallback

This module is **pure**: no database access, no I/O, no side effects.
"""

from app.modules.suitability_questionnaire.enums import (
    QuestionId,
    SuitabilityOutcome,
)

# ---------------------------------------------------------------------------
# Verbatim block-reason text (Appendix A.4)
# ---------------------------------------------------------------------------

BLOCK_REASON_SHORT_HORIZON: str = (
    "Your intended investment horizon is less than 2 years, which is below "
    "the minimum recommended for fractional real estate investments."
)

BLOCK_REASON_HIGH_CONCENTRATION: str = (
    "Allocating more than 50% of your investable assets to this platform "
    "exceeds the recommended concentration limit."
)

BLOCK_REASON_NO_EXPERIENCE: str = (
    "You have indicated no prior investment experience and would sell "
    "immediately in a downturn, which suggests this product may not be "
    "appropriate."
)

BLOCK_REASON_GENERIC: str = (
    "Based on your responses, this investment product does not appear "
    "suitable for your current financial profile."
)


# ---------------------------------------------------------------------------
# Block-reason logic
# ---------------------------------------------------------------------------


def compute_block_reason(
    answers: dict[QuestionId, str],
    outcome: SuitabilityOutcome,
) -> str | None:
    """Compute the block reason for a NOT_SUITABLE outcome.

    Returns ``None`` unless ``outcome`` is
    :attr:`SuitabilityOutcome.NOT_SUITABLE`. When it is, applies the
    priority rules from Appendix A.4 and returns the **first** matching
    reason string:

    1. Q4 == "under_2yr" → short horizon
    2. Q3 == "over_50pct" → high concentration
    3. Q5 == "none" AND Q6 == "sell_immediately" → no experience
    4. Otherwise → generic fallback

    Args:
        answers: Mapping of question identifiers to answer value strings.
        outcome: The classified suitability outcome for this submission.

    Returns:
        A human-readable block reason string, or ``None`` if the outcome
        is not NOT_SUITABLE.
    """
    if outcome != SuitabilityOutcome.NOT_SUITABLE:
        return None

    # Priority 1: short investment horizon
    if answers.get(QuestionId.Q4) == "under_2yr":
        return BLOCK_REASON_SHORT_HORIZON

    # Priority 2: high concentration
    if answers.get(QuestionId.Q3) == "over_50pct":
        return BLOCK_REASON_HIGH_CONCENTRATION

    # Priority 3: no experience + panic seller
    if (
        answers.get(QuestionId.Q5) == "none"
        and answers.get(QuestionId.Q6) == "sell_immediately"
    ):
        return BLOCK_REASON_NO_EXPERIENCE

    # Priority 4: generic fallback
    return BLOCK_REASON_GENERIC


__all__ = [
    "compute_block_reason",
    "BLOCK_REASON_SHORT_HORIZON",
    "BLOCK_REASON_HIGH_CONCENTRATION",
    "BLOCK_REASON_NO_EXPERIENCE",
    "BLOCK_REASON_GENERIC",
]
