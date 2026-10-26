"""add patient consents

Revision ID: c9a1b2c3d4e5
Revises: b2e8f4a1c6d9
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "b2e8f4a1c6d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("consented_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("consent_version", sa.String(length=32), server_default="1.0", nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["consented_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_patient_consents_patient_id"), "patient_consents", ["patient_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_patient_consents_patient_id"), table_name="patient_consents")
    op.drop_table("patient_consents")