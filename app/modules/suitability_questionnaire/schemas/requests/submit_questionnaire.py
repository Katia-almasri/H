"""Request schema for submitting the suitability questionnaire."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

# Static lookup mapping each QuestionId to its corresponding answer enum class.
# Mirrors Appendix A.1 of the spec and the lookup used by the scoring engine
# (see services/scoring_engine/questionnaire_definition.py — task 5.1).
_ANSWER_ENUM_BY_QUESTION: dict[QuestionId, type[StrEnum]] = {
    QuestionId.Q1: NetWorthBracket,
    QuestionId.Q2: AnnualIncomeBracket,
    QuestionId.Q3: AllocationBracket,
    QuestionId.Q4: LiquidityHorizon,
    QuestionId.Q5: InvestmentExperience,
    QuestionId.Q6: RiskResponse,
    QuestionId.Q7: InvestmentObjective,
}


class SubmitQuestionnaireRequest(BaseModel):
    """Request body for ``POST /api/v1/suitability/submit``.

    Contract (Requirements 2.1 - 2.6, 2.8):
      * ``questionnaire_version`` is the integer version the client believes is
        current. The service rejects the submission when it does not match the
        engine's ``QUESTIONNAIRE_VERSION``.
      * ``answers`` MUST contain exactly one entry per :class:`QuestionId`
        member. Missing keys, extra keys, or duplicate keys are rejected.
      * Every value in ``answers`` MUST be a case-sensitive match for one of
        the enumerated answer strings defined for that question in Appendix A.
      * Strict mode and ``extra="forbid"`` ensure that unexpected top-level
        fields and silent type coercions are rejected at the validation layer.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    questionnaire_version: int = Field(
        ...,
        ge=1,
        description="Questionnaire version identifier the client is submitting against.",
    )
    answers: dict[QuestionId, str] = Field(
        ...,
        description=(
            "One entry per QuestionId (Q1..Q7); each value must be one of the "
            "enumerated strings for that question's answer enum."
        ),
    )

    @model_validator(mode="after")
    def _validate_answers_shape_and_values(self) -> "SubmitQuestionnaireRequest":
        """Enforce complete coverage and per-question value membership."""
        expected_keys = set(QuestionId)
        actual_keys = set(self.answers.keys())
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        if missing or extra:
            missing_list = sorted(q.value for q in missing)
            extra_list = sorted(
                k.value if isinstance(k, QuestionId) else str(k) for k in extra
            )
            raise ValueError(
                "answers must contain exactly one entry per QuestionId "
                f"(Q1..Q7). Missing: {missing_list}. Extra: {extra_list}."
            )

        invalid_pairs: list[tuple[str, str]] = []
        for question_id, value in self.answers.items():
            answer_enum = _ANSWER_ENUM_BY_QUESTION[question_id]
            allowed_values = {member.value for member in answer_enum}
            if value not in allowed_values:
                invalid_pairs.append((question_id.value, value))
        if invalid_pairs:
            formatted = ", ".join(
                f"{question_id}={value!r}" for question_id, value in invalid_pairs
            )
            raise ValueError(
                "answers contains invalid values for the following questions: "
                f"{formatted}."
            )
        return self
