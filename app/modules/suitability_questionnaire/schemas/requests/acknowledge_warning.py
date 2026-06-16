"""Request schema for acknowledging an ELIGIBLE_WITH_WARNING risk warning."""

from pydantic import BaseModel, ConfigDict


class AcknowledgeWarningRequest(BaseModel):
    """Request body for ``POST /api/v1/suitability/properties/{property_id}/acknowledge``.

    The body is intentionally empty: ``property_id`` is supplied as the URL
    path parameter, the acting investor is resolved from the authenticated
    session, and the tenant comes from the ``X-Tenant-ID`` header. Strict mode
    plus ``extra="forbid"`` ensure that any non-empty body is rejected at the
    validation layer.
    """

    model_config = ConfigDict(strict=True, extra="forbid")
