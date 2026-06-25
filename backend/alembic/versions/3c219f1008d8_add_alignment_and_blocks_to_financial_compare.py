"""add alignment_check and diff_blocks to financial_compare_tasks

Revision ID: 3c219f1008d8
Revises: e9c4a1f7b203
Create Date: 2026-06-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3c219f1008d8'
down_revision: Union[str, Sequence[str], None] = 'e9c4a1f7b203'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # financial_compare_tasks 表：新增对齐校验与按页分块相关字段（幂等）
    # - pdf_detected_start_page: 自动定位到的财务报表正文起始页
    # - alignment_check: 对齐校验结果 JSON {overlap_ratio, threshold, passed}
    # - diff_blocks: 按 PDF 页切分的差异块 JSON 列表（替代旧版巨型 diff_ops_json）
    # 注意：asyncpg 不支持多条 SQL 在一个 op.execute() 中，必须逐条执行
    op.execute("ALTER TABLE financial_compare_tasks ADD COLUMN IF NOT EXISTS pdf_detected_start_page INTEGER")
    op.execute("ALTER TABLE financial_compare_tasks ADD COLUMN IF NOT EXISTS alignment_check TEXT")
    op.execute("ALTER TABLE financial_compare_tasks ADD COLUMN IF NOT EXISTS diff_blocks TEXT")


def downgrade() -> None:
    """Downgrade schema."""
    # 注意：asyncpg 不支持多条 SQL 在一个 op.execute() 中
    op.execute("ALTER TABLE financial_compare_tasks DROP COLUMN IF EXISTS diff_blocks")
    op.execute("ALTER TABLE financial_compare_tasks DROP COLUMN IF EXISTS alignment_check")
    op.execute("ALTER TABLE financial_compare_tasks DROP COLUMN IF EXISTS pdf_detected_start_page")
