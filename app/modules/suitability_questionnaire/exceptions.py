"""Backwards-compatible re-export shim.

The exceptions have been moved to the ``exceptions/`` package.
This file is kept so that any existing imports using the flat path
``app.modules.suitability_questionnaire.exceptions`` continue to work.
"""

from app.modules.suitability_questionnaire.exceptions.suitability_exceptions import (  # noqa: F401
    SuitabilityGateBlocked,
)

__all__ = ["SuitabilityGateBlocked"]
