"""Add RLS policies denying UPDATE/DELETE on suitability_acknowledgements

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-06-08 09:25:00.000000

The ``suitability_acknowledgements`` table is append-only by design (Req
4.4) — once an Investor's informed consent for a property is recorded
under a given Active_Suitability_Record it must remain immutable legal
evidence. Mirror the pattern used by ``audit_logs``,
``governance_votes``, and ``user_agreements`` and enforce
append-only-ness at the database layer using restrictive Row Level
Security policies.

Restrictive policies in PostgreSQL combine via AND across all
restrictive policies of a given command, so ``USING (false)`` /
``WITH CHECK (false)`` makes the operation impossible for every role,
regardless of any permissive policies that may be added later.

Requirements: 4.4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6b7c8d9e0f1'
down_revision: Union[str, None] = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE suitability_acknowledgements ENABLE ROW LEVEL SECURITY;"
    )
    op.execute(
        "CREATE POLICY no_update_suitability_ack "
        "ON suitability_acknowledgements "
        "AS RESTRICTIVE FOR UPDATE "
        "USING (false) WITH CHECK (false);"
    )
    op.execute(
        "CREATE POLICY no_delete_suitability_ack "
        "ON suitability_acknowledgements "
        "AS RESTRICTIVE FOR DELETE "
        "USING (false);"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS no_delete_suitability_ack "
        "ON suitability_acknowledgements;"
    )
    op.execute(
        "DROP POLICY IF EXISTS no_update_suitability_ack "
        "ON suitability_acknowledgements;"
    )
    op.execute(
        "ALTER TABLE suitability_acknowledgements DISABLE ROW LEVEL SECURITY;"
    )
