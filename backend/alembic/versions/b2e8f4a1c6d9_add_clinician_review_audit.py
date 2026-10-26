"""add clinician review, verification, and audit trail

Revision ID: b2e8f4a1c6d9
Revises: d4c9f2a81e70
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2e8f4a1c6d9"
down_revision: Union[str, Sequence[str], None] = "d4c9f2a81e70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SUMMARY_STATUSES = (
    "'pending_doctor_approval', 'approved', 'rejected', 'needs_correction'"
)
_DOCUMENT_STATUSES = "'unverified', 'verified', 'rejected'"


def upgrade() -> None:
    # 1) Reviewer tracking columns on clinical_summaries.
    op.add_column(
        "clinical_summaries",
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "clinical_summaries",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "clinical_summaries",
        sa.Column("review_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "clinical_summaries",
        sa.Column("corrected_by_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "clinical_summaries",
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_clinical_summaries_reviewed_by_user_id_users",
        "clinical_summaries",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_clinical_summaries_corrected_by_user_id_users",
        "clinical_summaries",
        "users",
        ["corrected_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_clinical_summaries_reviewed_by_user_id",
        "clinical_summaries",
        ["reviewed_by_user_id"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_clinical_summaries_review_status",
        "clinical_summaries",
        f"review_status IN ({_SUMMARY_STATUSES})",
    )

    # 2) Reviewer tracking columns on clinical_red_flags.
    op.add_column(
        "clinical_red_flags",
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "clinical_red_flags",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "clinical_red_flags",
        sa.Column("review_notes", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_clinical_red_flags_reviewed_by_user_id_users",
        "clinical_red_flags",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_clinical_red_flags_reviewed_by_user_id",
        "clinical_red_flags",
        ["reviewed_by_user_id"],
        unique=False,
    )

    # 3) Verification tracking columns on medical_documents.
    op.add_column(
        "medical_documents",
        sa.Column("verified_by_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "medical_documents",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "medical_documents",
        sa.Column("verification_notes", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_medical_documents_verified_by_user_id_users",
        "medical_documents",
        "users",
        ["verified_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_medical_documents_verified_by_user_id",
        "medical_documents",
        ["verified_by_user_id"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_medical_documents_verification_status",
        "medical_documents",
        f"verification_status IN ({_DOCUMENT_STATUSES})",
    )

    # 4) Audit trail.
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("consultation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "details",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["consultation_id"],
            ["consultations.id"],
            name="fk_audit_events_consultation_id_consultations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_events_actor_user_id",
        "audit_events",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_consultation_id",
        "audit_events",
        ["consultation_id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_entity",
        "audit_events",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_created_at",
        "audit_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_entity", table_name="audit_events")
    op.drop_index("ix_audit_events_consultation_id", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_constraint(
        "ck_medical_documents_verification_status",
        "medical_documents",
        type_="check",
    )
    op.drop_index(
        "ix_medical_documents_verified_by_user_id",
        table_name="medical_documents",
    )
    op.drop_constraint(
        "fk_medical_documents_verified_by_user_id_users",
        "medical_documents",
        type_="foreignkey",
    )
    op.drop_column("medical_documents", "verification_notes")
    op.drop_column("medical_documents", "verified_at")
    op.drop_column("medical_documents", "verified_by_user_id")

    op.drop_index(
        "ix_clinical_red_flags_reviewed_by_user_id",
        table_name="clinical_red_flags",
    )
    op.drop_constraint(
        "fk_clinical_red_flags_reviewed_by_user_id_users",
        "clinical_red_flags",
        type_="foreignkey",
    )
    op.drop_column("clinical_red_flags", "review_notes")
    op.drop_column("clinical_red_flags", "reviewed_at")
    op.drop_column("clinical_red_flags", "reviewed_by_user_id")

    op.drop_constraint(
        "ck_clinical_summaries_review_status",
        "clinical_summaries",
        type_="check",
    )
    op.drop_index(
        "ix_clinical_summaries_reviewed_by_user_id",
        table_name="clinical_summaries",
    )
    op.drop_constraint(
        "fk_clinical_summaries_corrected_by_user_id_users",
        "clinical_summaries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_clinical_summaries_reviewed_by_user_id_users",
        "clinical_summaries",
        type_="foreignkey",
    )
    op.drop_column("clinical_summaries", "corrected_at")
    op.drop_column("clinical_summaries", "corrected_by_user_id")
    op.drop_column("clinical_summaries", "review_notes")
    op.drop_column("clinical_summaries", "reviewed_at")
    op.drop_column("clinical_summaries", "reviewed_by_user_id")