"""
Warning-reason computation for the suitability scoring engine.

Implements the three warning rules defined in Appendix A.3 of the
suitability questionnaire requirements. Warning reasons are only produced
when the outcome is ``ELIGIBLE_WITH_WARNING``; for all other outcomes the
function returns an empty list.

This module is **pure**: no database access, no I/O, no side effects.
"""

from app.modules.suitability_questionnaire.enums import (
    QuestionId,
    SuitabilityOutcome,
    WarningReasonCode,
)

__all__ = ["compute_warning_reasons"]


def compute_warning_reasons(
    answers: dict[QuestionId, str],
    outcome: SuitabilityOutcome,
    total_score: int,
) -> list[WarningReasonCode]:
    """Compute applicable warning reason codes from answers and outcome.

    Returns an empty list unless ``outcome`` is
    :attr:`SuitabilityOutcome.ELIGIBLE_WITH_WARNING`. When it is, applies
    the three rules from Appendix A.3:

    1. ``SHORT_HORIZON`` — Q4 == "between_2_5yr" AND total_score < 65
    2. ``HIGH_CONCENTRATION`` — Q3 == "between_20_50pct"
    3. ``LOW_EXPERIENCE`` — Q5 in {"none", "stocks_bonds"}

    At most three codes are returned when all rules match.

    Args:
        answers: Mapping of question identifiers to answer value strings.
        outcome: The classified suitability outcome for this submission.
        total_score: The computed total score (0–100 inclusive).

    Returns:
        A list of :class:`WarningReasonCode` values (may be empty).
    """
    if outcome != SuitabilityOutcome.ELIGIBLE_WITH_WARNING:
        return []

    reasons: list[WarningReasonCode] = []

    # Rule 1: SHORT_HORIZON
    if answers.get(QuestionId.Q4) == "between_2_5yr" and total_score < 65:
        reasons.append(WarningReasonCode.SHORT_HORIZON)

    # Rule 2: HIGH_CONCENTRATION
    if answers.get(QuestionId.Q3) == "between_20_50pct":
        reasons.append(WarningReasonCode.HIGH_CONCENTRATION)

    # Rule 3: LOW_EXPERIENCE
    if answers.get(QuestionId.Q5) in {"none", "stocks_bonds"}:
        reasons.append(WarningReasonCode.LOW_EXPERIENCE)

    return reasons
