"""Create canonical investor_suitability table

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-08 09:05:00.000000

Replaces the placeholder ``investor_suitability`` table scaffolded in
``aec47ab74cb0`` with the canonical schema from design.md and task 2.1.

The legacy schema used different column names (``kyc_profile_id``,
``scores``, ``version``, ``acknowledged_at``), made several lifecycle
timestamps nullable, and used PostgreSQL ``UUID`` columns instead of the
project-wide ``VARCHAR``/``TEXT`` UUID-string convention. This revision
drops the legacy table wholesale and recreates it with:

* ``kyc_submission_id`` FK to ``kyc_submissions.id`` (String).
* ``per_question_scores`` JSONB instead of ``scores``.
* ``questionnaire_version`` SmallInt instead of ``version``.
* NOT NULL ``completed_at`` and ``expires_at``.
* ``warning_reasons`` TEXT[] NOT NULL DEFAULT '{}'.
* CHECK constraints enforcing the score range and the
  ``outcome = 'NOT_SUITABLE'`` ↔ ``block_reason``/``retake_allowed_at``
  invariants.
* B-tree indexes on ``(tenant_id, user_id)`` and
  ``(tenant_id, expires_at)``.

The partial unique index ``unique_active_suitability`` is added in a
separate revision (3.5) so this migration creates only the table,
constraints, and the two non-unique B-tree indexes.

The ``suitability_acknowledgements`` UUID columns are converted to
``VARCHAR`` so the recreated FK on ``suitability_id`` has matching
column types with the new ``investor_suitability.id``.

Requirements: 3.6, 3.7, 9.6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Drop the FK from suitability_acknowledgements.suitability_id so the
    #    legacy investor_suitability table can be dropped cleanly and the FK
    #    can be re-added with matching column types after recreation.
    op.drop_constraint(
        'suitability_acknowledgements_suitability_id_fkey',
        'suitability_acknowledgements',
        type_='foreignkey',
    )

    # 2) Convert legacy UUID columns on suitability_acknowledgements to
    #    VARCHAR so the new FK to investor_suitability.id (VARCHAR) is type-
    #    compatible. The cast `uuid::text` produces a canonical 36-char form.
    op.alter_column(
        'suitability_acknowledgements', 'id',
        existing_type=postgresql.UUID(as_uuid=False),
        type_=sa.String(),
        postgresql_using='id::text',
    )
    op.alter_column(
        'suitability_acknowledgements', 'suitability_id',
        existing_type=postgresql.UUID(as_uuid=False),
        type_=sa.String(),
        postgresql_using='suitability_id::text',
    )
    op.alter_column(
        'suitability_acknowledgements', 'user_id',
        existing_type=postgresql.UUID(as_uuid=False),
        type_=sa.String(),
        postgresql_using='user_id::text',
    )
    op.alter_column(
        'suitability_acknowledgements', 'property_id',
        existing_type=postgresql.UUID(as_uuid=False),
        type_=sa.String(),
        postgresql_using='property_id::text',
    )

    # 3) Drop the legacy investor_suitability table and its indexes.
    op.drop_index('ix_investor_suitability_completed_at', table_name='investor_suitability')
    op.drop_index('ix_investor_suitability_expires_at', table_name='investor_suitability')
    op.drop_index('ix_investor_suitability_tenant_id', table_name='investor_suitability')
    op.drop_index('ix_investor_suitability_user_id', table_name='investor_suitability')
    op.drop_table('investor_suitability')

    # 4) Create the canonical investor_suitability table.
    op.create_table(
        'investor_suitability',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('kyc_submission_id', sa.String(), nullable=False),
        sa.Column('answers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('per_question_scores', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('total_score', sa.SmallInteger(), nullable=False),
        sa.Column('outcome', sa.Text(), nullable=False),
        sa.Column(
            'warning_reasons',
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column('block_reason', sa.Text(), nullable=True),
        sa.Column('questionnaire_version', sa.SmallInteger(), nullable=False),
        sa.Column('submission_ip', postgresql.INET(), nullable=True),
        sa.Column('submission_user_agent', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('retake_allowed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('superseded_by', sa.String(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['kyc_submission_id'], ['kyc_submissions.id'], ),
        sa.ForeignKeyConstraint(['superseded_by'], ['investor_suitability.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            'total_score BETWEEN 0 AND 100',
            name='ck_investor_suitability_total_score_range',
        ),
        sa.CheckConstraint(
            "(outcome = 'NOT_SUITABLE') = (block_reason IS NOT NULL)",
            name='ck_investor_suitability_block_reason_iff_not_suitable',
        ),
        sa.CheckConstraint(
            "(outcome = 'NOT_SUITABLE') = (retake_allowed_at IS NOT NULL)",
            name='ck_investor_suitability_retake_iff_not_suitable',
        ),
    )
    op.create_index(
        'ix_investor_suitability_tenant_user',
        'investor_suitability',
        ['tenant_id', 'user_id'],
        unique=False,
    )
    op.create_index(
        'ix_investor_suitability_tenant_expires',
        'investor_suitability',
        ['tenant_id', 'expires_at'],
        unique=False,
    )

    # 5) Re-add the FK on suitability_acknowledgements.suitability_id.
    op.create_foreign_key(
        'suitability_acknowledgements_suitability_id_fkey',
        'suitability_acknowledgements',
        'investor_suitability',
        ['suitability_id'],
        ['id'],
    )


def downgrade() -> None:
    # Reverse step 5: drop the FK to the new table.
    op.drop_constraint(
        'suitability_acknowledgements_suitability_id_fkey',
        'suitability_acknowledgements',
        type_='foreignkey',
    )

    # Reverse step 4: drop the canonical investor_suitability table.
    op.drop_index('ix_investor_suitability_tenant_expires', table_name='investor_suitability')
    op.drop_index('ix_investor_suitability_tenant_user', table_name='investor_suitability')
    op.drop_table('investor_suitability')

    # Reverse step 3: recreate the legacy investor_suitability schema verbatim
    # from aec47ab74cb0_add_suitability_questionnaire_tables.py.
    op.create_table(
        'investor_suitability',
        sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('tenant_id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('kyc_profile_id', sa.UUID(as_uuid=False), nullable=True),
        sa.Column('answers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('scores', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('total_score', sa.SmallInteger(), nullable=False),
        sa.Column('outcome', sa.String(), nullable=False),
        sa.Column('warning_reasons', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('block_reason', sa.Text(), nullable=True),
        sa.Column('version', sa.SmallInteger(), nullable=False),
        sa.Column('submission_ip', postgresql.INET(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retake_allowed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('superseded_by', sa.UUID(as_uuid=False), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['superseded_by'], ['investor_suitability.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_investor_suitability_completed_at',
        'investor_suitability',
        ['completed_at'],
        unique=False,
    )
    op.create_index(
        'ix_investor_suitability_expires_at',
        'investor_suitability',
        ['expires_at'],
        unique=False,
    )
    op.create_index(
        'ix_investor_suitability_tenant_id',
        'investor_suitability',
        ['tenant_id'],
        unique=False,
    )
    op.create_index(
        'ix_investor_suitability_user_id',
        'investor_suitability',
        ['user_id'],
        unique=False,
    )

    # Reverse step 2: convert suitability_acknowledgements columns back to UUID.
    op.alter_column(
        'suitability_acknowledgements', 'property_id',
        existing_type=sa.String(),
        type_=postgresql.UUID(as_uuid=False),
        postgresql_using='property_id::uuid',
    )
    op.alter_column(
        'suitability_acknowledgements', 'user_id',
        existing_type=sa.String(),
        type_=postgresql.UUID(as_uuid=False),
        postgresql_using='user_id::uuid',
    )
    op.alter_column(
        'suitability_acknowledgements', 'suitability_id',
        existing_type=sa.String(),
        type_=postgresql.UUID(as_uuid=False),
        postgresql_using='suitability_id::uuid',
    )
    op.alter_column(
        'suitability_acknowledgements', 'id',
        existing_type=sa.String(),
        type_=postgresql.UUID(as_uuid=False),
        postgresql_using='id::uuid',
    )

    # Reverse step 1: re-add the FK pointing at the legacy table.
    op.create_foreign_key(
        'suitability_acknowledgements_suitability_id_fkey',
        'suitability_acknowledgements',
        'investor_suitability',
        ['suitability_id'],
        ['id'],
    )
