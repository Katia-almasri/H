"""Create audit_logs append-only table

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-06-13 14:30:00.000000

The ``audit_logs`` table is referenced as core infrastructure by every
state-changing service (auth, KYC, suitability, future investment) but
was never actually created by any prior migration. This revision adds
it with the schema documented in ``.kiro/steering/tech.md`` and
``.kiro/steering/product.md``:

Required fields per the audit rules:
    - id (PK)
    - tenant_id
    - user_id
    - action (matches AuditAction enum string values)
    - ip_address
    - user_agent
    - timestamp_utc
    - metadata (JSONB)

The table is **append-only**: ``UPDATE`` and ``DELETE`` are denied via
RESTRICTIVE Row Level Security policies, mirroring the same pattern used
by ``suitability_acknowledgements``, ``governance_votes``, and
``user_agreements``.

Indexes:
    - ``(tenant_id, user_id, timestamp_utc DESC)`` — primary lookup pattern
      ("show me this user's recent actions in this tenant").
    - ``(tenant_id, action, timestamp_utc DESC)`` — secondary lookup
      ("show me all SUITABILITY_GATE_BLOCKED events recently").

Requirements: tech.md "Audit rules", product.md "Audit Rules".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "timestamp_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_audit_logs_tenant_user_time",
        "audit_logs",
        ["tenant_id", "user_id", sa.text("timestamp_utc DESC")],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_tenant_action_time",
        "audit_logs",
        ["tenant_id", "action", sa.text("timestamp_utc DESC")],
        unique=False,
    )

    # Append-only: deny UPDATE and DELETE for every role via restrictive RLS.
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY no_update_audit_logs "
        "ON audit_logs "
        "AS RESTRICTIVE FOR UPDATE "
        "USING (false) WITH CHECK (false);"
    )
    op.execute(
        "CREATE POLICY no_delete_audit_logs "
        "ON audit_logs "
        "AS RESTRICTIVE FOR DELETE "
        "USING (false);"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS no_delete_audit_logs ON audit_logs;")
    op.execute("DROP POLICY IF EXISTS no_update_audit_logs ON audit_logs;")
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_audit_logs_tenant_action_time", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_user_time", table_name="audit_logs")
    op.drop_table("audit_logs")
