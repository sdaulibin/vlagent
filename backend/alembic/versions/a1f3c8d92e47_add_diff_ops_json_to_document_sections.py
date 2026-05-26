"""add diff_ops_json to document_sections

Revision ID: a1f3c8d92e47
Revises: 923edb9a7545
Create Date: 2026-05-26 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = 'a1f3c8d92e47'
down_revision: Union[str, Sequence[str], None] = '923edb9a7545'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('document_sections', sa.Column('diff_ops_json', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    op.drop_column('document_sections', 'diff_ops_json')
