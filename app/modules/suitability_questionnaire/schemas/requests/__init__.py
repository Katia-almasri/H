"""Suitability questionnaire request schemas."""

from app.modules.suitability_questionnaire.schemas.requests.submit_questionnaire import (
    SubmitQuestionnaireRequest,
)
from app.modules.suitability_questionnaire.schemas.requests.acknowledge_warning import (
    AcknowledgeWarningRequest,
)

__all__ = [
    "SubmitQuestionnaireRequest",
    "AcknowledgeWarningRequest",
]
