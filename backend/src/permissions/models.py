from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint
from typing import Optional
from datetime import datetime


class UserPermission(SQLModel, table=True):
    __tablename__ = "user_permissions"
    __table_args__ = (UniqueConstraint("user_id", "module", name="uq_user_permission_module"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    module: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.now)
