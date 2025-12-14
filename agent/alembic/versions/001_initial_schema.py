"""Initial schema with Thread model

Revision ID: 001_initial
Revises:
Create Date: 2024-12-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table first (no FK dependencies)
    op.create_table(
        'users',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('api_key', sa.String(), nullable=True),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('current_thread_id', sa.String(), nullable=True),
        sa.Column('webhook_secret', sa.String(), nullable=True),
        sa.Column('free', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('chat_id'),
        sa.UniqueConstraint('webhook_secret')
    )

    # Create threads table (depends on users)
    op.create_table(
        'threads',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['chat_id'], ['users.chat_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_threads_chat_id', 'threads', ['chat_id'], unique=False)
    op.create_index('ix_threads_updated_at', 'threads', ['updated_at'], unique=False)

    # Add FK from users to threads (now that threads exists)
    op.create_foreign_key(
        'fk_users_current_thread_id',
        'users', 'threads',
        ['current_thread_id'], ['id']
    )

    # Create messages table (depends on users and threads)
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('thread_id', sa.String(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=True),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['chat_id'], ['users.chat_id'], ),
        sa.ForeignKeyConstraint(['thread_id'], ['threads.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messages_thread_id', 'messages', ['thread_id'], unique=False)
    op.create_index('ix_messages_chat_created', 'messages', ['chat_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_messages_chat_created', table_name='messages')
    op.drop_index('ix_messages_thread_id', table_name='messages')
    op.drop_table('messages')

    op.drop_constraint('fk_users_current_thread_id', 'users', type_='foreignkey')

    op.drop_index('ix_threads_updated_at', table_name='threads')
    op.drop_index('ix_threads_chat_id', table_name='threads')
    op.drop_table('threads')

    op.drop_table('users')
