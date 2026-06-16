"""Suitability completion marker model.

A small flag table indicating that an Investor's first KYC approval has
established the requirement to complete the Suitability Questionnaire.

Lifecycle:
    * Inserted idempotently inside the KYC approval transaction using
      ``ON CONFLICT (user_id, tenant_id) DO NOTHING`` so repeated KYC
      approvals never produce duplicate markers (Requirement 1.1).
    * Deleted inside the suitability submission transaction once the
      Investor completes the questionnaire (Requirement 1.4).

The composite primary key ``(user_id, tenant_id)`` enforces at most one
marker per Investor per tenant and provides the conflict target needed
for the idempotent upsert.
"""

from sqlalchemy import Column, String, Text, ForeignKey, TIMESTAMP, func

from app.database import Base


class SuitabilityCompletionMarker(Base):
    """Marker row signalling that the Suitability Questionnaire is required.

    Created when the Investor's KYC is first approved; removed when the
    Investor submits the questionnaire. Composite PK ``(user_id, tenant_id)``
    guarantees uniqueness per Investor per tenant.
    """

    __tablename__ = "suitability_completion_markers"

    user_id = Column(String, primary_key=True, nullable=False)
    tenant_id = Column(Text, primary_key=True, nullable=False)

    kyc_submission_id = Column(
        String,
        ForeignKey("kyc_submissions.id"),
        nullable=False,
    )

    marked_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
