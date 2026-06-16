"""Drop legacy suitability_retake_requests table

Revision ID: b1c2d3e4f5a6
Revises: aec47ab74cb0
Create Date: 2026-06-08 09:00:00.000000

The 30-day retake cool-off is now encoded by ``retake_allowed_at`` on the
NOT_SUITABLE row of ``investor_suitability``, queried via
``InvestorSuitabilityRepository.get_latest_not_suitable``. The auxiliary
``suitability_retake_requests`` table introduces a second source of truth
and the risk of divergence; drop it.

Requirements: 5.7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'aec47ab74cb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('suitability_retake_requests')


def downgrade() -> None:
    # Verbatim recreation of the table from
    # aec47ab74cb0_add_suitability_questionnaire_tables.py.
    op.create_table(
        'suitability_retake_requests',
        sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('previous_suitability_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('allowed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['previous_suitability_id'], ['investor_suitability.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
