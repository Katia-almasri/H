"""
Suitability questionnaire definition table.

This module is the authoritative encoding of the seven-question suitability
questionnaire described in Appendix A.1 of
``.kiro/specs/suitability-questionnaire/requirements.md`` (and mirrored in
``design.md`` under "Scoring Engine (pure)").

The table fixes, for the current ``QUESTIONNAIRE_VERSION``:

* the set of questions (``QuestionId.Q1`` .. ``QuestionId.Q7``),
* the weight applied to each question's per-answer score, and
* the integer score awarded for every allowed answer string.

Per requirement 2.7, *any* change to this matrix (adding or removing a question,
changing a weight, or changing a per-answer score) MUST be accompanied by an
increment of ``QUESTIONNAIRE_VERSION`` so that previously-submitted
``InvestorSuitability`` rows remain attributable to the questionnaire revision
they were scored against.

Module-level invariants (sum of weights, exhaustive answer coverage,
per-answer score range) are validated at import time so that any drift between
this table and the per-question answer enums fails loudly the moment the module
is loaded.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.modules.suitability_questionnaire.enums import (
    AllocationBracket,
    AnnualIncomeBracket,
    InvestmentExperience,
    InvestmentObjective,
    LiquidityHorizon,
    NetWorthBracket,
    QuestionId,
    RiskResponse,
)

# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

#: Current questionnaire revision. Bump on ANY change to ``QUESTION_DEFINITIONS``
#: (questions, weights, or per-answer scores) per requirement 2.7.
QUESTIONNAIRE_VERSION: int = 1


# ---------------------------------------------------------------------------
# Definition dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuestionDefinition:
    """Immutable description of one questionnaire question.

    Attributes:
        id: The :class:`QuestionId` this definition applies to.
        weight: The weight applied to ``answer_scores[answer]`` when the
            weighted total is computed by the scoring engine. Weights across
            ``QUESTION_DEFINITIONS`` sum to ``1.30`` (see
            ``Appendix A.1`` and the import-time check below).
        answer_scores: Read-only mapping from the answer enum's ``.value``
            string to its integer score in ``[0, 100]``. The mapping itself
            is wrapped in :class:`types.MappingProxyType` so it cannot be
            mutated through the dataclass.
    """

    id: QuestionId
    weight: float
    answer_scores: Mapping[str, int]


# ---------------------------------------------------------------------------
# Authoritative question matrix (Appendix A.1)
# ---------------------------------------------------------------------------

QUESTION_DEFINITIONS: tuple[QuestionDefinition, ...] = (
    QuestionDefinition(
        id=QuestionId.Q1,
        weight=0.10,
        answer_scores=MappingProxyType(
            {"under_100k": 0, "between_100k_500k": 50, "over_500k": 100}
        ),
    ),
    QuestionDefinition(
        id=QuestionId.Q2,
        weight=0.10,
        answer_scores=MappingProxyType(
            {"under_50k": 0, "between_50k_200k": 50, "over_200k": 100}
        ),
    ),
    QuestionDefinition(
        id=QuestionId.Q3,
        weight=0.25,
        answer_scores=MappingProxyType(
            {"over_50pct": 0, "between_20_50pct": 50, "under_20pct": 100}
        ),
    ),
    QuestionDefinition(
        id=QuestionId.Q4,
        weight=0.30,
        answer_scores=MappingProxyType(
            {"under_2yr": 0, "between_2_5yr": 50, "over_5yr": 100}
        ),
    ),
    QuestionDefinition(
        id=QuestionId.Q5,
        weight=0.20,
        answer_scores=MappingProxyType(
            {"none": 0, "stocks_bonds": 60, "real_estate": 100}
        ),
    ),
    QuestionDefinition(
        id=QuestionId.Q6,
        weight=0.25,
        answer_scores=MappingProxyType(
            {"sell_immediately": 0, "wait_and_monitor": 60, "buy_more": 100}
        ),
    ),
    QuestionDefinition(
        id=QuestionId.Q7,
        weight=0.10,
        answer_scores=MappingProxyType(
            {"income": 100, "capital_growth": 80, "both": 100}
        ),
    ),
)


# ---------------------------------------------------------------------------
# Import-time validation
#
# These checks make any drift between this table, the per-question answer
# enums, and the documented invariants in Appendix A.1 a hard import error.
# We use ``AssertionError`` (not a custom exception) so the failure is loud
# and immediate at process start.
# ---------------------------------------------------------------------------

# 1. Question count and uniqueness ------------------------------------------
assert len(QUESTION_DEFINITIONS) == 7, (
    f"QUESTION_DEFINITIONS must contain exactly 7 entries (one per QuestionId); "
    f"found {len(QUESTION_DEFINITIONS)}."
)

_seen_ids: set[QuestionId] = {qd.id for qd in QUESTION_DEFINITIONS}
assert _seen_ids == set(QuestionId), (
    "QUESTION_DEFINITIONS must cover every QuestionId exactly once. "
    f"Missing: {set(QuestionId) - _seen_ids}; "
    f"Extra/duplicated: {len(QUESTION_DEFINITIONS) - len(_seen_ids)} duplicate(s)."
)

# 2. Weight sum (Appendix A.1) ----------------------------------------------
_weight_sum = sum(qd.weight for qd in QUESTION_DEFINITIONS)
assert abs(_weight_sum - 1.30) < 1e-9, (
    f"Sum of weights in QUESTION_DEFINITIONS must be 1.30 per Appendix A.1; "
    f"got {_weight_sum!r}."
)

# 3. Per-answer score range (integers in [0, 100]) --------------------------
for _qd in QUESTION_DEFINITIONS:
    for _answer, _score in _qd.answer_scores.items():
        assert isinstance(_score, int) and not isinstance(_score, bool), (
            f"answer_scores[{_qd.id.value!r}][{_answer!r}] must be an int; "
            f"got {type(_score).__name__}."
        )
        assert 0 <= _score <= 100, (
            f"answer_scores[{_qd.id.value!r}][{_answer!r}] must be in [0, 100]; "
            f"got {_score}."
        )

# 4. Answer-key coverage matches the per-question answer enum ---------------
_answer_enum_by_question: dict[QuestionId, type] = {
    QuestionId.Q1: NetWorthBracket,
    QuestionId.Q2: AnnualIncomeBracket,
    QuestionId.Q3: AllocationBracket,
    QuestionId.Q4: LiquidityHorizon,
    QuestionId.Q5: InvestmentExperience,
    QuestionId.Q6: RiskResponse,
    QuestionId.Q7: InvestmentObjective,
}

for _qd in QUESTION_DEFINITIONS:
    _enum = _answer_enum_by_question[_qd.id]
    _expected_keys = {a.value for a in _enum}
    _actual_keys = set(_qd.answer_scores.keys())
    assert _actual_keys == _expected_keys, (
        f"answer_scores keys for {_qd.id.value} must exactly match "
        f"{_enum.__name__} values. "
        f"Missing: {_expected_keys - _actual_keys}; "
        f"Unexpected: {_actual_keys - _expected_keys}."
    )

# Tidy up loop variables so they don't leak as module attributes.
del _seen_ids, _weight_sum, _qd, _answer, _score, _enum, _expected_keys, _actual_keys
del _answer_enum_by_question


__all__ = [
    "QUESTIONNAIRE_VERSION",
    "QuestionDefinition",
    "QUESTION_DEFINITIONS",
]
