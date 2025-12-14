"""Fix users.id sequence for auto-increment

The 002 migration added the id column with autoincrement=True, but in PostgreSQL
that doesn't create a sequence when adding to an existing table. This migration
creates the sequence and sets up the default properly.

Revision ID: 005_fix_users_id_seq
Revises: 004_user_renders
Create Date: 2024-12-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '005_fix_users_id_seq'
down_revision: Union[str, None] = '004_user_renders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sequence for users.id
    op.execute("CREATE SEQUENCE IF NOT EXISTS users_id_seq")

    # Set sequence value to max existing id + 1
    op.execute("""
        SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 0) + 1, false)
    """)

    # Set default for id column to use the sequence
    op.execute("ALTER TABLE users ALTER COLUMN id SET DEFAULT nextval('users_id_seq')")

    # Link sequence to the column (so it gets dropped with the column)
    op.execute("ALTER SEQUENCE users_id_seq OWNED BY users.id")


def downgrade() -> None:
    # Remove default
    op.execute("ALTER TABLE users ALTER COLUMN id DROP DEFAULT")

    # Drop sequence
    op.execute("DROP SEQUENCE IF EXISTS users_id_seq")
