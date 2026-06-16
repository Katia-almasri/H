"""Suitability questionnaire repositories."""

from app.modules.suitability_questionnaire.repositories.investor_suitability_repository import (
    InvestorSuitabilityRepository,
)
from app.modules.suitability_questionnaire.repositories.suitability_acknowledgement_repository import (
    SuitabilityAcknowledgementRepository,
)
from app.modules.suitability_questionnaire.repositories.suitability_completion_marker_repository import (
    SuitabilityCompletionMarkerRepository,
)

__all__ = [
    "InvestorSuitabilityRepository",
    "SuitabilityAcknowledgementRepository",
    "SuitabilityCompletionMarkerRepository",
]
