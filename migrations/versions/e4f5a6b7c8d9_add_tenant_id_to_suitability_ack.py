"""Add tenant_id to suitability_acknowledgements

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-08 09:15:00.000000

The legacy ``suitability_acknowledgements`` table from ``aec47ab74cb0``
omitted the ``tenant_id`` discriminator. Add it now so every read and
write can filter by tenant per the multi-tenancy rule, plus the unique
key on ``(suitability_id, user_id, property_id, tenant_id)`` that turns
repeated acknowledgement submissions into a no-op (Req 4.5).

Steps:
    1. Add ``tenant_id`` with a backfill server default of ``harvest-uae``
       so existing rows acquire the default tenant.
    2. Drop the server default once existing rows are backfilled — new
       writes must set ``tenant_id`` explicitly via the resolved request
       tenant.
    3. Add a B-tree index on ``tenant_id`` for tenant-scoped scans.
    4. Add the unique key on ``(suitability_id, user_id, property_id,
       tenant_id)`` enabling ``ON CONFLICT DO NOTHING`` idempotency.

Requirements: 4.5, 9.1, 9.6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Add the column with a backfill default for existing rows.
    op.add_column(
        'suitability_acknowledgements',
        sa.Column(
            'tenant_id',
            sa.Text(),
            nullable=False,
            server_default='harvest-uae',
        ),
    )
    # 2) Drop the server default once existing rows are backfilled.
    op.alter_column(
        'suitability_acknowledgements',
        'tenant_id',
        server_default=None,
    )
    # 3) B-tree index on tenant_id for tenant-scoped scans.
    op.create_index(
        'ix_suitability_acknowledgements_tenant_id',
        'suitability_acknowledgements',
        ['tenant_id'],
        unique=False,
    )
    # 4) Idempotent unique key for ON CONFLICT DO NOTHING (Req 4.5).
    op.create_unique_constraint(
        'uq_suitability_acknowledgement_idempotent',
        'suitability_acknowledgements',
        ['suitability_id', 'user_id', 'property_id', 'tenant_id'],
    )


def downgrade() -> None:
    # Reverse in opposite order: unique → index → column.
    op.drop_constraint(
        'uq_suitability_acknowledgement_idempotent',
        'suitability_acknowledgements',
        type_='unique',
    )
    op.drop_index(
        'ix_suitability_acknowledgements_tenant_id',
        table_name='suitability_acknowledgements',
    )
    op.drop_column('suitability_acknowledgements', 'tenant_id')
