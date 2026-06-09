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
    op.execute("""
        CREATE TABLE IF NOT EXISTS document_sections (
            id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL REFERENCES document_compare_tasks(id),
            user_id VARCHAR,
            doc_type VARCHAR NOT NULL,
            role VARCHAR NOT NULL,
            title VARCHAR,
            text_content VARCHAR,
            source_indices VARCHAR,
            parent_id INTEGER REFERENCES document_sections(id),
            order_index INTEGER,
            diff_type VARCHAR,
            page_number INTEGER,
            created_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_sections_task_id ON document_sections (task_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_sections_user_id ON document_sections (user_id)")


def downgrade() -> None:
    op.drop_index(op.f('ix_document_sections_user_id'), table_name='document_sections')
    op.drop_index(op.f('ix_document_sections_task_id'), table_name='document_sections')
    op.drop_table('document_sections')
