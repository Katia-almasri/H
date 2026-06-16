"""Warning acknowledgement response schemas.

Two related payloads grouped into one file:

* ``AcknowledgementStatusResponse`` — returned by
  ``GET /suitability/properties/{property_id}/acknowledgement``. Reports
  whether the investor has already acknowledged the warning reasons of
  their active ``ELIGIBLE_WITH_WARNING`` record for the given property.
* ``AcknowledgementResponse`` — returned by
  ``POST /suitability/properties/{property_id}/acknowledge``. Confirms the
  acknowledgement record (idempotent insert).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.suitability_questionnaire.enums import WarningReasonCode


class AcknowledgementStatusResponse(BaseModel):
    """Payload returned by ``GET /suitability/properties/{property_id}/acknowledgement``."""

    model_config = ConfigDict(extra="forbid")

    acknowledged: bool = Field(
        ...,
        description="Whether an acknowledgement exists for the active record + property.",
    )
    acknowledgement_id: Optional[str] = Field(
        None,
        description="UUID of the existing acknowledgement record, when ``acknowledged`` is True.",
    )
    property_id: str = Field(
        ...,
        description="Property the acknowledgement applies to.",
    )
    warning_reasons: list[WarningReasonCode] = Field(
        default_factory=list,
        description=(
            "Active warning reason codes the investor must acknowledge. "
            "Empty when no active ``ELIGIBLE_WITH_WARNING`` record exists."
        ),
    )
    acknowledged_at: Optional[datetime] = Field(
        None,
        description="UTC timestamp the acknowledgement was recorded.",
    )


class AcknowledgementResponse(BaseModel):
    """Payload returned by ``POST /suitability/properties/{property_id}/acknowledge``."""

    model_config = ConfigDict(extra="forbid")

    acknowledgement_id: str = Field(
        ...,
        description="UUID of the acknowledgement record (existing or newly created).",
    )
    suitability_id: str = Field(
        ...,
        description="UUID of the suitability record the acknowledgement is bound to.",
    )
    property_id: str = Field(
        ...,
        description="Property the acknowledgement applies to.",
    )
    acknowledged_at: datetime = Field(
        ...,
        description="UTC timestamp the acknowledgement was recorded.",
    )
    message: str = Field(
        ...,
        description="Human-readable confirmation message.",
    )
