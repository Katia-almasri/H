"""Remove duplicate users and enforce unique constraints

Revision ID: a1b2c3d4e5f6
Revises: 4fb7302d7516
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '4fb7302d7516'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove duplicate emails — keep the oldest row (earliest created_at)
    op.execute("""
        DELETE FROM users
        WHERE id NOT IN (
            SELECT DISTINCT ON (email) id
            FROM users
            ORDER BY email, created_at ASC
        )
    """)

    # Remove duplicate usernames — keep the oldest row (earliest created_at)
    op.execute("""
        DELETE FROM users
        WHERE id NOT IN (
            SELECT DISTINCT ON (username) id
            FROM users
            ORDER BY username, created_at ASC
        )
    """)

    # Ensure unique indexes exist (idempotent — will skip if already present)
    # Drop and recreate to guarantee they are unique
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute("DROP INDEX IF EXISTS ix_users_username")
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)


def downgrade() -> None:
    # No downgrade needed — we don't want to re-introduce duplicates
    pass
