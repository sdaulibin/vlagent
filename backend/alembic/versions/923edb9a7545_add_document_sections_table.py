"""add_document_sections_table

Revision ID: 923edb9a7545
Revises: b415ad1a512e
Create Date: 2026-05-25 16:45:56.963149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '923edb9a7545'
down_revision: Union[str, Sequence[str], None] = 'b415ad1a512e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_sections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('doc_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('text_content', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('source_indices', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=True),
        sa.Column('diff_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['document_compare_tasks.id']),
        sa.ForeignKeyConstraint(['parent_id'], ['document_sections.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_document_sections_task_id'), 'document_sections', ['task_id'])
    op.create_index(op.f('ix_document_sections_user_id'), 'document_sections', ['user_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_document_sections_user_id'), table_name='document_sections')
    op.drop_index(op.f('ix_document_sections_task_id'), table_name='document_sections')
    op.drop_table('document_sections')
