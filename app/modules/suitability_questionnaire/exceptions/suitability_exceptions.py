"""Domain-specific exceptions for the suitability questionnaire module.

All exceptions extend ``AppException`` so they are handled by the global
exception handler and serialised into the standard API response envelope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from packages.core.exceptions import AppException

if TYPE_CHECKING:
    from app.modules.suitability_questionnaire.services.suitability_gate_service import (
        GateDecision,
    )


class SuitabilityGateBlocked(AppException):
    """Raised by the Investment module when the gate blocks a purchase.

    Carries the full ``GateDecision`` so the caller can inspect the
    blocking reason, re-take window, or required acknowledgement details.
    """

    def __init__(self, decision: "GateDecision") -> None:
        self.decision = decision
        super().__init__(
            status_code=403,
            message=f"Investment blocked: {decision.kind.value}",
        )
