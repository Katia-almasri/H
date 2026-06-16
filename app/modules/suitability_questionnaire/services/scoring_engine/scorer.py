"""
Suitability scoring engine — score computation and outcome classification.

This module implements the pure scoring logic described in Appendix A.2 of the
suitability questionnaire requirements. It exposes two public functions:

* ``classify_outcome`` — maps a total score (0..100) to a
  :class:`~app.modules.suitability_questionnaire.enums.SuitabilityOutcome`.
* ``score_submission`` — given a complete set of answers (one per question),
  computes the weighted total score, per-question raw scores, outcome,
  and placeholder warning/block fields (wired in task 5.4).

Both functions are **pure**: no database access, no clock, no network, no I/O.
Deterministic in their inputs.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.suitability_questionnaire.enums import (
    QuestionId,
    SuitabilityOutcome,
    WarningReasonCode,
)
from app.modules.suitability_questionnaire.services.scoring_engine.block_rules import (
    compute_block_reason,
)
from app.modules.suitability_questionnaire.services.scoring_engine.questionnaire_definition import (
    QUESTION_DEFINITIONS,
)
from app.modules.suitability_questionnaire.services.scoring_engine.warning_rules import (
    compute_warning_reasons,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoringResult:
    """Immutable result of scoring a suitability questionnaire submission.

    Attributes:
        total_score: Normalised total score in the inclusive range [0, 100].
        per_question_scores: Mapping from question id value (e.g. ``"Q1"``)
            to the raw integer answer score for that question.
        outcome: The :class:`SuitabilityOutcome` derived from ``total_score``.
        warning_reasons: List of applicable warning reason codes. Empty unless
            ``outcome == ELIGIBLE_WITH_WARNING``.
        block_reason: Human-readable block reason. ``None`` unless
            ``outcome == NOT_SUITABLE``.
    """

    total_score: int
    per_question_scores: dict[str, int]
    outcome: SuitabilityOutcome
    warning_reasons: list[WarningReasonCode]
    block_reason: str | None


# ---------------------------------------------------------------------------
# Outcome classification (Appendix A.2)
# ---------------------------------------------------------------------------


def classify_outcome(total_score: int) -> SuitabilityOutcome:
    """Classify a total score into a suitability outcome.

    Thresholds per Appendix A.2:
        * ``>= 65`` → ELIGIBLE
        * ``40..64`` → ELIGIBLE_WITH_WARNING
        * ``< 40`` → NOT_SUITABLE

    Args:
        total_score: Integer in [0, 100].

    Returns:
        The corresponding :class:`SuitabilityOutcome`.
    """
    if total_score >= 65:
        return SuitabilityOutcome.ELIGIBLE
    if total_score >= 40:
        return SuitabilityOutcome.ELIGIBLE_WITH_WARNING
    return SuitabilityOutcome.NOT_SUITABLE


# ---------------------------------------------------------------------------
# Score submission (pure)
# ---------------------------------------------------------------------------


def score_submission(answers: dict[QuestionId, str]) -> ScoringResult:
    """Compute the suitability scoring result from a complete answer set.

    This function is **pure**: it performs no database access, no network
    calls, no file I/O, and does not read the system clock. Given the same
    ``answers`` it always returns an identical :class:`ScoringResult`.

    The scoring formula (Appendix A.1):

    .. code-block:: text

        weight_sum = sum(qd.weight for qd in QUESTION_DEFINITIONS)  # 1.30
        raw = sum(answer_scores[ans] * qd.weight for each question)  # 0..130
        total = round(raw / weight_sum)                              # 0..100

    Args:
        answers: Mapping from :class:`QuestionId` to the selected answer
            value string (must be a valid key in the corresponding
            question's ``answer_scores``).

    Returns:
        A frozen :class:`ScoringResult` with the computed total score,
        per-question raw scores, outcome, warning reasons, and block
        reason.
    """
    weight_sum: float = sum(qd.weight for qd in QUESTION_DEFINITIONS)
    raw: float = 0.0
    per_question_scores: dict[str, int] = {}

    for qd in QUESTION_DEFINITIONS:
        answer_value: str = answers[qd.id]
        answer_score: int = qd.answer_scores[answer_value]
        per_question_scores[qd.id.value] = answer_score
        raw += answer_score * qd.weight

    total_score: int = round(raw / weight_sum)
    outcome: SuitabilityOutcome = classify_outcome(total_score)

    warning_reasons: list[WarningReasonCode] = compute_warning_reasons(
        answers, outcome, total_score
    )
    block_reason: str | None = compute_block_reason(answers, outcome)

    return ScoringResult(
        total_score=total_score,
        per_question_scores=per_question_scores,
        outcome=outcome,
        warning_reasons=warning_reasons,
        block_reason=block_reason,
    )


__all__ = [
    "ScoringResult",
    "classify_outcome",
    "score_submission",
]
