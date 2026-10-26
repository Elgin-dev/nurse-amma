"""Add persistent medical document records and extraction results.

Revision ID: d4c9f2a81e70
Revises: f741b1d8c903
Create Date: 2026-10-25
"""

from alembic import op
import sqlalchemy as sa


revision = "d4c9f2a81e70"
down_revision = "f741b1d8c903"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medical_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultation_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_extension", sa.String(length=10), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("file_content", sa.LargeBinary(), nullable=False),
        sa.Column("processing_status", sa.String(length=32), server_default="processing", nullable=False),
        sa.Column("extraction_method", sa.String(length=100), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("entities", sa.JSON(), nullable=False),
        sa.Column("verification_status", sa.String(length=32), server_default="unverified", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_medical_documents_consultation_id"), "medical_documents", ["consultation_id"], unique=False)
    op.create_index(op.f("ix_medical_documents_uploaded_by_user_id"), "medical_documents", ["uploaded_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_medical_documents_uploaded_by_user_id"), table_name="medical_documents")
    op.drop_index(op.f("ix_medical_documents_consultation_id"), table_name="medical_documents")
    op.drop_table("medical_documents")
