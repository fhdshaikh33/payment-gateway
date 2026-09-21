"""add_updated_at_columns

Revision ID: a1f2e3d4b5c6
Revises: 9ce5124ac88f
Create Date: 2026-09-21 16:16:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1f2e3d4b5c6'
down_revision = '9ce5124ac88f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add updated_at column to users table if missing
    op.add_column('users', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    # Add updated_at column to merchants table if missing
    op.add_column('merchants', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    # Add updated_at column to roles table if missing
    op.add_column('roles', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column('roles', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    # Add updated_at column to merchant_members table if missing
    op.add_column('merchant_members', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column('merchant_members', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    op.drop_column('merchant_members', 'created_at')
    op.drop_column('merchant_members', 'updated_at')
    op.drop_column('roles', 'created_at')
    op.drop_column('roles', 'updated_at')
    op.drop_column('merchants', 'updated_at')
    op.drop_column('users', 'updated_at')
