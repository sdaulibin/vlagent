"""add_comparison_mode_to_document_compare_tasks

Revision ID: b415ad1a512e
Revises: 0d8ea47502f4
Create Date: 2026-05-25 14:56:37.656022

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = 'b415ad1a512e'
down_revision: Union[str, Sequence[str], None] = '0d8ea47502f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('document_compare_tasks', sa.Column('comparison_mode', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    op.drop_column('document_compare_tasks', 'comparison_mode')
