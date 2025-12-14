"""Rename threads to chats and chat_id to telegram_id

This migration:
1. Renames 'threads' table to 'chats'
2. Renames 'user_renders' table to 'renders'
3. Renames users.chat_id to users.telegram_id
4. Renames users.current_thread_id to users.current_chat_id
5. Renames messages.thread_id to messages.chat_id
6. Renames user_renders.thread_id to renders.chat_id
7. Updates foreign key constraints
8. Updates indexes

Revision ID: 006_rename_threads_to_chats
Revises: 005_fix_users_id_seq
Create Date: 2024-12-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '006_rename_threads_to_chats'
down_revision: Union[str, None] = '005_fix_users_id_seq'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename threads table to chats
    op.rename_table('threads', 'chats')

    # 2. Rename user_renders table to renders
    op.rename_table('user_renders', 'renders')

    # 3. Rename users.chat_id to users.telegram_id
    # First drop the index on users.chat_id
    op.drop_index('ix_users_chat_id', table_name='users')
    op.alter_column('users', 'chat_id', new_column_name='telegram_id')
    # Create index with new name
    op.create_index('ix_users_telegram_id', 'users', ['telegram_id'])

    # 4. Rename users.current_thread_id to users.current_chat_id
    # First drop the foreign key constraint (actual name from DB: fk_users_current_thread_id)
    op.drop_constraint('fk_users_current_thread_id', 'users', type_='foreignkey')
    op.alter_column('users', 'current_thread_id', new_column_name='current_chat_id')
    # Re-create foreign key with new name
    op.create_foreign_key('fk_users_current_chat_id', 'users', 'chats', ['current_chat_id'], ['id'])

    # 5. Rename messages.thread_id to messages.chat_id
    # First, drop the old chat_id column (was BigInt Telegram chat ID, no longer needed)
    op.drop_column('messages', 'chat_id')
    # Drop old foreign key
    op.drop_constraint('messages_thread_id_fkey', 'messages', type_='foreignkey')
    # Drop old index
    op.drop_index('ix_messages_thread_id', table_name='messages')
    # Rename column
    op.alter_column('messages', 'thread_id', new_column_name='chat_id')
    # Create new foreign key
    op.create_foreign_key('messages_chat_id_fkey', 'messages', 'chats', ['chat_id'], ['id'])
    # Create new index
    op.create_index('ix_messages_chat_id', 'messages', ['chat_id'])

    # 6. Rename renders.thread_id to renders.chat_id (was user_renders)
    # Drop old foreign keys (user_renders had FK on both thread_id and user_id)
    op.drop_constraint('user_renders_thread_id_fkey', 'renders', type_='foreignkey')
    op.drop_constraint('user_renders_user_id_fkey', 'renders', type_='foreignkey')
    # Drop old indexes
    op.drop_index('ix_user_renders_thread_id', table_name='renders')
    # Rename column
    op.alter_column('renders', 'thread_id', new_column_name='chat_id')
    # Create new foreign keys
    op.create_foreign_key('renders_chat_id_fkey', 'renders', 'chats', ['chat_id'], ['id'])
    op.create_foreign_key('renders_user_id_fkey', 'renders', 'users', ['user_id'], ['user_id'])
    # Create new index
    op.create_index('ix_renders_chat_id', 'renders', ['chat_id'])

    # Update other renamed indexes in renders table
    op.drop_index('ix_user_renders_user_id', table_name='renders')
    op.create_index('ix_renders_user_id', 'renders', ['user_id'])
    op.drop_index('ix_user_renders_render_id', table_name='renders')
    op.create_index('ix_renders_render_id', 'renders', ['render_id'])
    op.drop_index('ix_user_renders_user_status', table_name='renders')
    op.create_index('ix_renders_user_status', 'renders', ['user_id', 'status'])

    # Rename indexes on chats table
    op.drop_index('ix_threads_updated_at', table_name='chats')
    op.create_index('ix_chats_updated_at', 'chats', ['updated_at'])
    op.drop_index('ix_threads_user_id', table_name='chats')
    op.create_index('ix_chats_user_id', 'chats', ['user_id'])
    # Also drop the ix_threads_chat_id index (legacy)
    op.drop_index('ix_threads_chat_id', table_name='chats')

    # 7. Add new columns to messages (status, error, updated_at)
    op.add_column('messages', sa.Column('status', sa.String(), nullable=False, server_default='complete'))
    op.add_column('messages', sa.Column('error', sa.Text(), nullable=True))
    op.add_column('messages', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.create_index('ix_messages_status', 'messages', ['status'])


def downgrade() -> None:
    # Remove new columns from messages
    op.drop_index('ix_messages_status', table_name='messages')
    op.drop_column('messages', 'updated_at')
    op.drop_column('messages', 'error')
    op.drop_column('messages', 'status')

    # Recreate ix_threads_chat_id index before renaming table
    op.create_index('ix_threads_chat_id', 'chats', ['id'])

    # Rename chats table back to threads
    op.drop_index('ix_chats_user_id', table_name='chats')
    op.create_index('ix_threads_user_id', 'chats', ['user_id'])
    op.drop_index('ix_chats_updated_at', table_name='chats')
    op.create_index('ix_threads_updated_at', 'chats', ['updated_at'])
    op.rename_table('chats', 'threads')

    # Rename renders table back to user_renders
    op.drop_index('ix_renders_user_status', table_name='renders')
    op.create_index('ix_user_renders_user_status', 'renders', ['user_id', 'status'])
    op.drop_index('ix_renders_render_id', table_name='renders')
    op.create_index('ix_user_renders_render_id', 'renders', ['render_id'])
    op.drop_index('ix_renders_user_id', table_name='renders')
    op.create_index('ix_user_renders_user_id', 'renders', ['user_id'])
    op.drop_constraint('renders_chat_id_fkey', 'renders', type_='foreignkey')
    op.drop_constraint('renders_user_id_fkey', 'renders', type_='foreignkey')
    op.drop_index('ix_renders_chat_id', table_name='renders')
    op.alter_column('renders', 'chat_id', new_column_name='thread_id')
    op.create_index('ix_user_renders_thread_id', 'renders', ['thread_id'])
    op.create_foreign_key('user_renders_thread_id_fkey', 'renders', 'threads', ['thread_id'], ['id'])
    op.create_foreign_key('user_renders_user_id_fkey', 'renders', 'users', ['user_id'], ['user_id'])
    op.rename_table('renders', 'user_renders')

    # Rename messages.chat_id back to thread_id
    op.drop_constraint('messages_chat_id_fkey', 'messages', type_='foreignkey')
    op.drop_index('ix_messages_chat_id', table_name='messages')
    op.alter_column('messages', 'chat_id', new_column_name='thread_id')
    op.create_index('ix_messages_thread_id', 'messages', ['thread_id'])
    op.create_foreign_key('messages_thread_id_fkey', 'messages', 'threads', ['thread_id'], ['id'])
    # Re-add the old chat_id column (BigInt Telegram chat ID)
    op.add_column('messages', sa.Column('chat_id', sa.BigInteger(), nullable=True))

    # Rename users.current_chat_id back to current_thread_id
    op.drop_constraint('fk_users_current_chat_id', 'users', type_='foreignkey')
    op.alter_column('users', 'current_chat_id', new_column_name='current_thread_id')
    op.create_foreign_key('fk_users_current_thread_id', 'users', 'threads', ['current_thread_id'], ['id'])

    # Rename users.telegram_id back to chat_id
    op.drop_index('ix_users_telegram_id', table_name='users')
    op.alter_column('users', 'telegram_id', new_column_name='chat_id')
    op.create_index('ix_users_chat_id', 'users', ['chat_id'])
