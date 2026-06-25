"""rebuild financial_compare_tasks for structured LLM engine

Revision ID: 4b0b262e3938
Revises: 3c219f1008d8
Create Date: 2026-06-23 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4b0b262e3938'
down_revision: Union[str, Sequence[str], None] = '3c219f1008d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    字段变更（适配结构化 LLM 比对引擎）：
    新增：docx_start_page / docx_end_page（DOCX 页码范围，传给引擎 PageRange）
    删除：docx_text_length / pdf_text_length / diff_ops_json / pdf_generated_docx_path
          / pdf_detected_start_page / alignment_check（旧字符级 diff 专用字段）
    保留：diff_stats / diff_blocks（语义重定义为引擎输出）
    """
    # 注意：asyncpg 不支持多条 SQL 在一个 op.execute() 中
    # 新增列
    op.execute("ALTER TABLE financial_compare_tasks ADD COLUMN IF NOT EXISTS docx_start_page INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE financial_compare_tasks ADD COLUMN IF NOT EXISTS docx_end_page INTEGER")

    # 删除旧列（IF EXISTS 保证幂等）
    for col in [
        "docx_text_length",
        "pdf_text_length",
        "diff_ops_json",
        "pdf_generated_docx_path",
        "pdf_detected_start_page",
        "alignment_check",
    ]:
        op.execute(f"ALTER TABLE financial_compare_tasks DROP COLUMN IF EXISTS {col}")


def downgrade() -> None:
    """Downgrade schema."""
    # 恢复旧列
    op.execute("ALTER TABLE financial_compare_tasks ADD COLUMN IF NOT EXISTS docx_text_length INTEGER")
    op.execute("ALTER TABLE financial_compare_tasks ADD COLUMN IF NOT EXISTS pdf_text_length INTEGER")
    op.execute("ALTER TABLE financial_compare_tasks ADD COLUMN IF NOT EXISTS diff_ops_json TEXT")
    op.execute("ALTER TABLE financial_compare_tasks ADD COLUMN IF NOT EXISTS pdf_generated_docx_path VARCHAR")
    op.execute("ALTER TABLE financial_compare_tasks ADD COLUMN IF NOT EXISTS pdf_detected_start_page INTEGER")
    op.execute("ALTER TABLE financial_compare_tasks ADD COLUMN IF NOT EXISTS alignment_check TEXT")
    # 删除新列
    op.execute("ALTER TABLE financial_compare_tasks DROP COLUMN IF EXISTS docx_start_page")
    op.execute("ALTER TABLE financial_compare_tasks DROP COLUMN IF EXISTS docx_end_page")
