"""Add maintenance_windows table

Revision ID: 001
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add maintenance_windows table for alert suppression during maintenance."""
    op.create_table(
        'maintenance_windows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.String(length=32), nullable=False),
        sa.Column('end_time', sa.String(length=32), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('maintenance_type', sa.String(length=32), nullable=False, server_default='scheduled'),
        sa.Column('created_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('suppress_alert_sources', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(
        'ix_maint_window_cluster_times',
        'maintenance_windows',
        ['cluster_id', 'start_time', 'end_time'],
        unique=False
    )
    op.create_index(
        'ix_maint_window_active',
        'maintenance_windows',
        ['is_active'],
        unique=False
    )


def downgrade() -> None:
    """Remove maintenance_windows table."""
    op.drop_index('ix_maint_window_active', table_name='maintenance_windows')
    op.drop_index('ix_maint_window_cluster_times', table_name='maintenance_windows')
    op.drop_table('maintenance_windows')
