"""add persisted review status to clinical red flags

Revision ID: c81a7e4f6b20
Revises: 932ca1bdc5db
Create Date: 2026-10-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c81a7e4f6b20"
down_revision: Union[str, Sequence[str], None] = "932ca1bdc5db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ALLOWED_STATUSES = "'pending_review', 'acknowledged', 'verified', 'dismissed', 'corrected'"


def upgrade() -> None:
    """Add a constrained status for each red-flag finding."""
    op.add_column(
        "clinical_red_flags",
        sa.Column(
            "review_status",
            sa.String(length=24),
            server_default="pending_review",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_clinical_red_flags_review_status",
        "clinical_red_flags",
        f"review_status IN ({_ALLOWED_STATUSES})",
    )


def downgrade() -> None:
    """Remove the red-flag review status."""
    op.drop_constraint(
        "ck_clinical_red_flags_review_status",
        "clinical_red_flags",
        type_="check",
    )
    op.drop_column("clinical_red_flags", "review_status")
