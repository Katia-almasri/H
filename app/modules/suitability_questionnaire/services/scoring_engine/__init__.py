"""
Suitability scoring engine package.

Re-exports the public API of the pure scoring engine:

* :func:`score_submission` — compute outcome from answers.
* :class:`ScoringResult` — frozen result dataclass.
* :data:`QUESTIONNAIRE_VERSION` — current version identifier.
* :data:`QUESTION_DEFINITIONS` — authoritative question matrix.
"""

from app.modules.suitability_questionnaire.services.scoring_engine.questionnaire_definition import (
    QUESTIONNAIRE_VERSION,
    QUESTION_DEFINITIONS,
)
from app.modules.suitability_questionnaire.services.scoring_engine.scorer import (
    score_submission,
    ScoringResult,
)

__all__ = [
    "score_submission",
    "ScoringResult",
    "QUESTIONNAIRE_VERSION",
    "QUESTION_DEFINITIONS",
]
