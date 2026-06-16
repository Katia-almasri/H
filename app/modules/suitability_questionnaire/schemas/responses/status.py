"""Suitability status response schema.

Returned by ``GET /suitability/status``. Exposes the investor's current
suitability lifecycle state: whether they may invest, the most recent
outcome and total score, any active warning reasons, expiry / renewal
flags, the cool-off retake timestamp (when ``NOT_SUITABLE``), and the
minimum share-size hint surfaced when the investor cannot invest.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.suitability_questionnaire.enums import (
    SuitabilityOutcome,
    WarningReasonCode,
)


class SuitabilityStatusResponse(BaseModel):
    """Payload returned by ``GET /suitability/status``."""

    model_config = ConfigDict(extra="forbid")

    state: Literal[
        "SUITABILITY_REQUIRED",
        "ELIGIBLE",
        "ELIGIBLE_WITH_WARNING",
        "NOT_SUITABLE",
    ] = Field(
        ...,
        description="High-level UI state derived from the active record + KYC marker.",
    )
    can_invest: bool = Field(
        ...,
        description="Whether the investor may currently start an investment flow.",
    )
    outcome: Optional[SuitabilityOutcome] = Field(
        None,
        description="Outcome of the active suitability record, if one exists.",
    )
    total_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Total score of the active suitability record, if one exists.",
    )
    warning_reasons: list[WarningReasonCode] = Field(
        default_factory=list,
        description=(
            "Active warning reason codes. Empty when not "
            "``ELIGIBLE_WITH_WARNING`` or no active record exists."
        ),
    )
    block_reason: Optional[str] = Field(
        None,
        description="Verbatim block reason text when the outcome is ``NOT_SUITABLE``.",
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="UTC expiry timestamp of the active suitability record.",
    )
    renewal_due: bool = Field(
        ...,
        description="True within the 30-day window before ``expires_at``.",
    )
    renewal_required: bool = Field(
        ...,
        description="True once ``expires_at`` has passed and a new questionnaire is required.",
    )
    retake_allowed_at: Optional[datetime] = Field(
        None,
        description=(
            "When the investor may retake the questionnaire after a "
            "``NOT_SUITABLE`` outcome (cool-off end)."
        ),
    )
    minimum_share_size_aed: Optional[int] = Field(
        None,
        description=(
            "Minimum share size hint in AED. Populated only when "
            "``state == 'NOT_SUITABLE'``."
        ),
    )
    questionnaire_version: int = Field(
        ...,
        description="Active questionnaire version the client should use on submit.",
    )
    message: str = Field(
        ...,
        description="Human-readable message tailored to the current state.",
    )
