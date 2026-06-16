"""Questionnaire response schema.

Returned by ``GET /suitability/questionnaire``. Carries the ordered set of
questions (Q1..Q7), each with its enumerated answer values, plus the active
questionnaire version so clients can echo it back on submission for
optimistic version locking.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.modules.suitability_questionnaire.enums import QuestionId


class QuestionDescriptor(BaseModel):
    """Single questionnaire question with its allowed answer values.

    The ``prompt`` is a short human-readable label rendered by the client.
    The router pulls the prompt text from a constants table; the schema only
    declares the field shape.
    """

    model_config = ConfigDict(extra="forbid")

    id: QuestionId = Field(..., description="Question identifier (Q1..Q7).")
    prompt: str = Field(
        ...,
        description="Short human-readable label for the question.",
    )
    answers: list[str] = Field(
        ...,
        description=(
            "Case-sensitive enumerated answer values for the question, in "
            "presentation order."
        ),
    )


class QuestionnaireResponse(BaseModel):
    """Payload returned by ``GET /suitability/questionnaire``."""

    model_config = ConfigDict(extra="forbid")

    questionnaire_version: int = Field(
        ...,
        description="Active questionnaire version. Clients echo this on submit.",
    )
    questions: list[QuestionDescriptor] = Field(
        ...,
        description="Ordered list of questions Q1..Q7.",
    )
