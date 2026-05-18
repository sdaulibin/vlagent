"""initial baseline

Revision ID: 135eef68092d
Revises:
Create Date: 2026-05-18 10:06:59.116153

Baseline migration for existing databases.
- For existing DB: run `alembic stamp head` to mark current state
- For fresh DB: run `init_db()` first (via app startup), then `alembic stamp head`
- Future schema changes: use `alembic revision --autogenerate -m "description"`

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '135eef68092d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Baseline: existing databases already have all tables created by init_db()."""
    pass


def downgrade() -> None:
    """No-op: do not downgrade below baseline."""
    pass
