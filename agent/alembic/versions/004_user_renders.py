"""Add user_renders table for tracking renders with thread association.

Revision ID: 004_user_renders
Revises: 003_render_notifications
Create Date: 2024-12-13
"""
from alembic import op
import sqlalchemy as sa


revision = '004_user_renders'
down_revision = '003_render_notifications'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_renders table
    op.create_table(
        'user_renders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('thread_id', sa.String(), nullable=False),
        sa.Column('render_id', sa.String(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('template', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('result_url', sa.String(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['thread_id'], ['threads.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_renders_user_id', 'user_renders', ['user_id'])
    op.create_index('ix_user_renders_thread_id', 'user_renders', ['thread_id'])
    op.create_index('ix_user_renders_render_id', 'user_renders', ['render_id'], unique=True)
    op.create_index('ix_user_renders_user_status', 'user_renders', ['user_id', 'status'])


def downgrade():
    op.drop_index('ix_user_renders_user_status', table_name='user_renders')
    op.drop_index('ix_user_renders_render_id', table_name='user_renders')
    op.drop_index('ix_user_renders_thread_id', table_name='user_renders')
    op.drop_index('ix_user_renders_user_id', table_name='user_renders')
    op.drop_table('user_renders')
