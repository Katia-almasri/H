"""Investor suitability submission model.

One row per questionnaire submission. Effectively immutable after insert — the
only fields ever mutated are `superseded_by` (set when a newer submission
replaces this one) and `expires_at` (set to ``now()`` when a material KYC
change invalidates the record). The historical chain of submissions for a
given investor is recovered by walking ``superseded_by``.

Schema reference: design.md → "Tables → investor_suitability".
Requirements: 3.6, 3.7, 5.4, 6.1, 9.1.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    TIMESTAMP,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB

from app.database import Base


class InvestorSuitability(Base):
    """Core suitability submission. Immutable except for ``superseded_by`` / ``expires_at``."""

    __tablename__ = "investor_suitability"

    # Primary key — UUID4 generated in the service layer, stored as a string
    # to match the project-wide convention (see app/modules/auth/models/user.py).
    id = Column(String, primary_key=True)

    # Multi-tenant discriminator. Every read and write filters on this column.
    tenant_id = Column(Text, nullable=False)

    # Investor — references users.id. Stored as String/UUID4 for consistency.
    user_id = Column(String, nullable=False)

    # Snapshot of the approved KYC submission at the time the questionnaire
    # was completed. References kyc_submissions.id.
    kyc_submission_id = Column(
        String,
        ForeignKey("kyc_submissions.id"),
        nullable=False,
    )

    # Raw answers as submitted: ``{"Q1": "under_100k", ..., "Q7": "income"}``.
    answers = Column(JSONB, nullable=False)

    # Per-question weighted score breakdown:
    # ``{"Q1": 0, "Q2": 50, ..., "Q7": 100}``.
    per_question_scores = Column(JSONB, nullable=False)

    # Final 0..100 score (CHECK-constrained below).
    total_score = Column(SmallInteger, nullable=False)

    # SuitabilityOutcome enum value: ELIGIBLE | ELIGIBLE_WITH_WARNING | NOT_SUITABLE.
    outcome = Column(String, nullable=False)

    # WarningReasonCode values; empty array unless ``outcome == ELIGIBLE_WITH_WARNING``.
    warning_reasons = Column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'"),
    )

    # Verbatim block-reason text. Populated only when ``outcome == NOT_SUITABLE``
    # (enforced by the CHECK constraint below).
    block_reason = Column(Text, nullable=True)

    # Snapshot of the Appendix-A revision used to score this submission.
    questionnaire_version = Column(SmallInteger, nullable=False)

    # Forensic metadata captured from the originating HTTP request.
    submission_ip = Column(INET, nullable=True)
    submission_user_agent = Column(Text, nullable=True)

    # Lifecycle timestamps. All TIMESTAMPTZ to preserve UTC semantics.
    completed_at = Column(TIMESTAMP(timezone=True), nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    # NOT_SUITABLE only: completed_at + 30 days. NULL for ELIGIBLE / ELIGIBLE_WITH_WARNING
    # (enforced by the CHECK constraint below).
    retake_allowed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Supersession pointer — NULL means this is the active record for the
    # (tenant_id, user_id) pair. Self-referential FK.
    superseded_by = Column(
        String,
        ForeignKey("investor_suitability.id"),
        nullable=True,
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        # Score must lie in the inclusive 0..100 range.
        CheckConstraint(
            "total_score BETWEEN 0 AND 100",
            name="ck_investor_suitability_total_score_range",
        ),
        # block_reason is populated iff outcome is NOT_SUITABLE.
        CheckConstraint(
            "(outcome = 'NOT_SUITABLE') = (block_reason IS NOT NULL)",
            name="ck_investor_suitability_block_reason_iff_not_suitable",
        ),
        # retake_allowed_at is populated iff outcome is NOT_SUITABLE.
        CheckConstraint(
            "(outcome = 'NOT_SUITABLE') = (retake_allowed_at IS NOT NULL)",
            name="ck_investor_suitability_retake_iff_not_suitable",
        ),
        # Tenant-scoped lookup by user (active-record fetch, history walk).
        Index(
            "ix_investor_suitability_tenant_user",
            "tenant_id",
            "user_id",
        ),
        # Tenant-scoped renewal scan ordered by expiry.
        Index(
            "ix_investor_suitability_tenant_expires",
            "tenant_id",
            "expires_at",
        ),
    )
