"""Suitability gate decision response schema.

Serialisable view of the ``GateDecision`` dataclass produced by
``services/suitability_gate_service.py`` (implemented in task 8.2). The
gate itself is consumed in-process by the future Investment module; this
schema exists so any future endpoint that needs to expose a gate
decision over HTTP has a stable, validated shape to return.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.suitability_questionnaire.enums import (
    GateDecisionKind,
    WarningReasonCode,
)


class GateDecisionResponse(BaseModel):
    """Serialisable mirror of the ``GateDecision`` service-layer dataclass."""

    model_config = ConfigDict(extra="forbid")

    kind: GateDecisionKind = Field(
        ...,
        description="Decision kind: ALLOW, SUITABILITY_REQUIRED, SUITABILITY_BLOCKED, "
        "SUITABILITY_ACK_REQUIRED, or INVALID_SUBJECT.",
    )
    suitability_id: Optional[str] = Field(
        None,
        description="UUID of the suitability record the decision was based on, when one exists.",
    )
    acknowledgement_id: Optional[str] = Field(
        None,
        description="UUID of the matching warning acknowledgement, when ``kind == ALLOW`` "
        "after an ``ELIGIBLE_WITH_WARNING`` outcome.",
    )
    block_reason: Optional[str] = Field(
        None,
        description="Verbatim block reason text when ``kind == SUITABILITY_BLOCKED``.",
    )
    retake_allowed_at: Optional[datetime] = Field(
        None,
        description="When the investor may retake the questionnaire after a block.",
    )
    warning_reasons: list[WarningReasonCode] = Field(
        default_factory=list,
        description="Warning reason codes the investor must acknowledge. Non-empty "
        "for ``SUITABILITY_ACK_REQUIRED``.",
    )
    reason_indicator: Optional[
        Literal["NO_RECORD", "EXPIRED", "INVALID_SUBJECT"]
    ] = Field(
        None,
        description="Sub-classifier for ``SUITABILITY_REQUIRED`` / ``INVALID_SUBJECT`` decisions.",
    )
    property_id: Optional[str] = Field(
        None,
        description="Property the gate decision was evaluated against, when applicable.",
    )
