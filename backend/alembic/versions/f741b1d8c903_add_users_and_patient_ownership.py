"""add users and patient ownership for authenticated clinical access

Revision ID: f741b1d8c903
Revises: c81a7e4f6b20
Create Date: 2026-10-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f741b1d8c903"
down_revision: Union[str, Sequence[str], None] = "c81a7e4f6b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=24), server_default="clinician", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'clinician')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.add_column("patients", sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_patients_created_by_user_id_users",
        "patients",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_patients_created_by_user_id", "patients", ["created_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_patients_created_by_user_id", table_name="patients")
    op.drop_constraint("fk_patients_created_by_user_id_users", "patients", type_="foreignkey")
    op.drop_column("patients", "created_by_user_id")
    op.drop_table("users")
