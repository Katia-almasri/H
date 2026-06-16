"""Add partial unique index unique_active_suitability

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-06-08 09:20:00.000000

Enforces at most one active ``investor_suitability`` record per
``(tenant_id, user_id)`` at the database layer. The ``WHERE
superseded_by IS NULL`` predicate restricts the uniqueness to the
"active" row of the supersession chain, allowing the historical chain
of prior submissions to coexist for the same investor.

This is the database-level guarantee for Requirement 9.6 / 9.7 — the
service layer's supersede-and-insert atomicity is the primary path,
this index is the defence-in-depth backstop.

Requirements: 3.9, 9.6, 9.7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'unique_active_suitability',
        'investor_suitability',
        ['tenant_id', 'user_id'],
        unique=True,
        postgresql_where=sa.text('superseded_by IS NULL'),
    )


def downgrade() -> None:
    op.drop_index(
        'unique_active_suitability',
        table_name='investor_suitability',
    )
