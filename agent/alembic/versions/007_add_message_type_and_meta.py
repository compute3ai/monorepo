"""Add type and meta columns to messages

This migration adds:
1. type column - Message type (text, selection, selection_response)
2. meta column - JSON field for additional message data

Revision ID: 007_add_message_type_and_meta
Revises: 006_rename_threads_to_chats
Create Date: 2024-12-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '007_add_message_type_and_meta'
down_revision: Union[str, None] = '006_rename_threads_to_chats'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add type column with default 'text' for existing messages
    op.add_column('messages', sa.Column('type', sa.String(), nullable=False, server_default='text'))

    # Add meta column (JSON, nullable)
    op.add_column('messages', sa.Column('meta', sa.JSON(), nullable=True))

    # Add index on type for efficient filtering
    op.create_index('ix_messages_type', 'messages', ['type'])


def downgrade() -> None:
    op.drop_index('ix_messages_type', table_name='messages')
    op.drop_column('messages', 'meta')
    op.drop_column('messages', 'type')
