"""add composite timeline indexes

Revision ID: d1e2f3a4b5c6
Revises: c9a1b2c3d4e5
Create Date: 2026-10-26
"""
from typing import Sequence, Union
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c9a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_index("ix_history_consultation_time", "clinical_history_submissions", ["consultation_id", "created_at", "version"])
    op.create_index("ix_summaries_consultation_time", "clinical_summaries", ["consultation_id", "created_at", "version"])
    op.create_index("ix_documents_consultation_time", "medical_documents", ["consultation_id", "created_at", "id"])
    op.create_index("ix_audit_consultation_time", "audit_events", ["consultation_id", "created_at", "id"])

def downgrade() -> None:
    op.drop_index("ix_audit_consultation_time", table_name="audit_events")
    op.drop_index("ix_documents_consultation_time", table_name="medical_documents")
    op.drop_index("ix_summaries_consultation_time", table_name="clinical_summaries")
    op.drop_index("ix_history_consultation_time", table_name="clinical_history_submissions")
