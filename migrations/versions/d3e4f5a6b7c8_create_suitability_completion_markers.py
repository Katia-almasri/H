"""Create suitability_completion_markers table

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-08 09:10:00.000000

A small flag table indicating that an Investor's first KYC approval has
established the requirement to complete the Suitability Questionnaire.
Inserted idempotently inside the KYC approval transaction; deleted inside
the suitability submission transaction.

The composite primary key ``(user_id, tenant_id)`` enforces at most one
marker per Investor per tenant and provides the conflict target needed
for ``ON CONFLICT (user_id, tenant_id) DO NOTHING`` upserts.

Requirements: 1.1, 1.4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'suitability_completion_markers',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.Text(), nullable=False),
        sa.Column('kyc_submission_id', sa.String(), nullable=False),
        sa.Column(
            'marked_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['kyc_submission_id'], ['kyc_submissions.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'tenant_id'),
    )
    op.create_index(
        'ix_suitability_completion_markers_tenant_id',
        'suitability_completion_markers',
        ['tenant_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_suitability_completion_markers_tenant_id',
        table_name='suitability_completion_markers',
    )
    op.drop_table('suitability_completion_markers')
