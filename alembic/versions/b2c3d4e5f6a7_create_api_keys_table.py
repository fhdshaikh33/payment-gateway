"""create_api_keys_table

Revision ID: b2c3d4e5f6a7
Revises: a1f2e3d4b5c6
Create Date: 2026-09-21 17:35:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1f2e3d4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("merchant_id", sa.Uuid(), nullable=False),
        sa.Column("key_id", sa.String(length=100), nullable=False),
        sa.Column("key_secret_hash", sa.String(length=255), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["merchant_id"], ["merchants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_id"),
    )
    op.create_index(
        op.f("ix_api_keys_key_id"), "api_keys", ["key_id"], unique=True
    )
    op.create_index(
        op.f("ix_api_keys_merchant_id"),
        "api_keys",
        ["merchant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_api_keys_merchant_id"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_key_id"), table_name="api_keys")
    op.drop_table("api_keys")
