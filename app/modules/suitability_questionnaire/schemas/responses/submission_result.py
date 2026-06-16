"""Suitability submission result response schema.

Returned by ``POST /suitability/submit``. Surfaces the resulting outcome,
the total score, any warning reasons, and — for ``NOT_SUITABLE`` — the
verbatim block reason and the cool-off ``retake_allowed_at`` timestamp.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.suitability_questionnaire.enums import (
    SuitabilityOutcome,
    WarningReasonCode,
)


class SubmissionResultResponse(BaseModel):
    """Payload returned by ``POST /suitability/submit``."""

    model_config = ConfigDict(extra="forbid")

    suitability_id: str = Field(
        ...,
        description="UUID of the newly created suitability record.",
    )
    outcome: SuitabilityOutcome = Field(
        ...,
        description="Outcome computed by the scoring engine.",
    )
    total_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Total score for the submission, in the range [0, 100].",
    )
    warning_reasons: list[WarningReasonCode] = Field(
        default_factory=list,
        description=(
            "Warning reason codes. Non-empty only when outcome is "
            "``ELIGIBLE_WITH_WARNING``."
        ),
    )
    block_reason: Optional[str] = Field(
        None,
        description="Verbatim block reason text when outcome is ``NOT_SUITABLE``.",
    )
    expires_at: datetime = Field(
        ...,
        description="UTC expiry timestamp assigned to the new record.",
    )
    retake_allowed_at: Optional[datetime] = Field(
        None,
        description=(
            "When the investor may retake the questionnaire after a "
            "``NOT_SUITABLE`` outcome. ``None`` for non-blocking outcomes."
        ),
    )
    questionnaire_version: int = Field(
        ...,
        description="Questionnaire version used to compute the outcome.",
    )
    message: str = Field(
        ...,
        description="Human-readable message summarising the outcome.",
    )
