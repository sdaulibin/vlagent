"""add permission_required to modules

Revision ID: e9c4a1f7b203
Revises: c3f7b2a91d04
Create Date: 2026-06-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e9c4a1f7b203'
down_revision: Union[str, Sequence[str], None] = 'c3f7b2a91d04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # modules 表：新增 permission_required 字段（幂等）
    # True=需权限(仅授权用户可见)，False=公开(所有用户可见)。
    # 默认 True 保持现状；其值由 sync_modules 从上游 hi_agent_list.permissions 同步。
    # 注意：asyncpg 不支持多条 SQL 在一个 op.execute() 中，必须逐条执行
    op.execute("ALTER TABLE modules ADD COLUMN IF NOT EXISTS permission_required BOOLEAN DEFAULT TRUE")


def downgrade() -> None:
    """Downgrade schema."""
    # 注意：asyncpg 不支持多条 SQL 在一个 op.execute() 中
    op.execute("ALTER TABLE modules DROP COLUMN IF EXISTS permission_required")
