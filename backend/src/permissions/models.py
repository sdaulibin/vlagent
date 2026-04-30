from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class UserPermission(SQLModel, table=True):
    __tablename__ = "user_permissions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    module: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.now)
