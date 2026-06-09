"""add section_summary_a and section_summary_b to document_compare_tasks

Revision ID: c3f7b2a91d04
Revises: a1f3c8d92e47
Create Date: 2026-06-08 10:45:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = 'c3f7b2a91d04'
down_revision: str | Sequence[str] | None = 'a1f3c8d92e47'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE document_compare_tasks ADD COLUMN IF NOT EXISTS section_summary_a VARCHAR")
    op.execute("ALTER TABLE document_compare_tasks ADD COLUMN IF NOT EXISTS section_summary_b VARCHAR")


def downgrade() -> None:
    op.drop_column('document_compare_tasks', 'section_summary_b')
    op.drop_column('document_compare_tasks', 'section_summary_a')
