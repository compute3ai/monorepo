"""Add user_id as primary identifier, make chat_id nullable

This migration changes the schema to support both Telegram and web users:
- Adds user_id (String) as the main identifier for all users
- Makes chat_id (BigInteger) nullable - only set for Telegram users
- Updates threads and messages to reference user_id instead of chat_id
- Adds telegram_message_id to messages (renamed from message_id for clarity)

Revision ID: 002_user_id
Revises: 001_initial
Create Date: 2024-12-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002_user_id'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add new columns to users table
    op.add_column('users', sa.Column('id', sa.Integer(), autoincrement=True, nullable=True))
    op.add_column('users', sa.Column('user_id', sa.String(), nullable=True))

    # Step 2: Populate user_id from chat_id for existing users (tg_{chat_id} format)
    op.execute("UPDATE users SET user_id = 'tg_' || CAST(chat_id AS VARCHAR)")

    # Step 3: Populate id with sequential values for existing users
    op.execute("""
        UPDATE users SET id = subq.row_num
        FROM (SELECT chat_id, ROW_NUMBER() OVER (ORDER BY created_at) as row_num FROM users) subq
        WHERE users.chat_id = subq.chat_id
    """)

    # Step 4: Make user_id and id not null
    op.alter_column('users', 'user_id', nullable=False)
    op.alter_column('users', 'id', nullable=False)

    # Step 5: Drop foreign key constraints that reference users.chat_id
    op.drop_constraint('fk_users_current_thread_id', 'users', type_='foreignkey')
    op.drop_constraint('threads_chat_id_fkey', 'threads', type_='foreignkey')
    op.drop_constraint('messages_chat_id_fkey', 'messages', type_='foreignkey')

    # Step 6: Drop the primary key on chat_id and create new one on id
    op.drop_constraint('users_pkey', 'users', type_='primary')
    op.create_primary_key('users_pkey', 'users', ['id'])

    # Step 7: Add indexes for user_id and chat_id
    op.create_index('ix_users_user_id', 'users', ['user_id'], unique=True)
    op.create_index('ix_users_chat_id', 'users', ['chat_id'], unique=True)

    # Step 8: Make users.chat_id nullable (for web-only users) - NOW this works
    op.alter_column('users', 'chat_id', nullable=True)

    # Step 9: Recreate foreign key constraint from users to threads
    op.create_foreign_key('fk_users_current_thread_id', 'users', 'threads', ['current_thread_id'], ['id'])

    # Step 10: Add user_id column to threads
    op.add_column('threads', sa.Column('user_id', sa.String(), nullable=True))

    # Step 11: Populate threads.user_id from users
    op.execute("""
        UPDATE threads SET user_id = users.user_id
        FROM users WHERE threads.chat_id = users.chat_id
    """)

    # Step 12: Make threads.user_id not null and add index
    op.alter_column('threads', 'user_id', nullable=False)
    op.create_index('ix_threads_user_id', 'threads', ['user_id'], unique=False)

    # Step 13: Make threads.chat_id nullable
    op.alter_column('threads', 'chat_id', nullable=True)

    # Step 14: Add user_id column to messages
    op.add_column('messages', sa.Column('user_id', sa.String(), nullable=True))

    # Step 15: Rename message_id to telegram_message_id for clarity
    op.alter_column('messages', 'message_id', new_column_name='telegram_message_id')

    # Step 16: Populate messages.user_id from users
    op.execute("""
        UPDATE messages SET user_id = users.user_id
        FROM users WHERE messages.chat_id = users.chat_id
    """)

    # Step 17: Make messages.user_id not null and add index
    op.alter_column('messages', 'user_id', nullable=False)
    op.create_index('ix_messages_user_id', 'messages', ['user_id'], unique=False)

    # Step 18: Make messages.chat_id nullable
    op.alter_column('messages', 'chat_id', nullable=True)


def downgrade() -> None:
    # This is a destructive downgrade - web-only users would be lost
    # First, delete any users without chat_id
    op.execute("DELETE FROM messages WHERE chat_id IS NULL")
    op.execute("DELETE FROM threads WHERE chat_id IS NULL")
    op.execute("DELETE FROM users WHERE chat_id IS NULL")

    # Revert nullable changes for messages and threads
    op.alter_column('messages', 'chat_id', nullable=False)
    op.alter_column('threads', 'chat_id', nullable=False)

    # Drop user_id columns and indexes from messages
    op.drop_index('ix_messages_user_id', table_name='messages')
    op.drop_column('messages', 'user_id')

    # Rename telegram_message_id back to message_id
    op.alter_column('messages', 'telegram_message_id', new_column_name='message_id')

    # Drop user_id from threads
    op.drop_index('ix_threads_user_id', table_name='threads')
    op.drop_column('threads', 'user_id')

    # Drop the FK from users to threads
    op.drop_constraint('fk_users_current_thread_id', 'users', type_='foreignkey')

    # Revert users.chat_id to not null
    op.alter_column('users', 'chat_id', nullable=False)

    # Drop indexes on users
    op.drop_index('ix_users_chat_id', table_name='users')
    op.drop_index('ix_users_user_id', table_name='users')

    # Restore primary key from id back to chat_id
    op.drop_constraint('users_pkey', 'users', type_='primary')
    op.create_primary_key('users_pkey', 'users', ['chat_id'])

    # Drop new columns
    op.drop_column('users', 'user_id')
    op.drop_column('users', 'id')

    # Recreate foreign key constraints referencing users.chat_id
    op.create_foreign_key('fk_users_current_thread_id', 'users', 'threads', ['current_thread_id'], ['id'])
    op.create_foreign_key('threads_chat_id_fkey', 'threads', 'users', ['chat_id'], ['chat_id'])
    op.create_foreign_key('messages_chat_id_fkey', 'messages', 'users', ['chat_id'], ['chat_id'])
