"""Add render_notifications table.

Revision ID: 003_render_notifications
Revises: 002_user_id
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '003_render_notifications'
down_revision = '002_user_id'
branch_labels = None
depends_on = None


def upgrade():
    # Create render_notifications table
    op.create_table(
        'render_notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('render_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('result_url', sa.String(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('read', sa.Integer(), default=0, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_render_notifications_user_unread', 'render_notifications', ['user_id', 'read'])


def downgrade():
    op.drop_index('ix_render_notifications_user_unread', table_name='render_notifications')
    op.drop_table('render_notifications')
