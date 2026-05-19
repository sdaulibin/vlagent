from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class Module(SQLModel, table=True):
    __tablename__ = "modules"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    title: str
    description: str
    icon: str
    route: str
    gradient: str
    hover_class: str
    category: str = Field(default="")
    category_label: str = Field(default="")
    category_color: str = Field(default="")
    bg_color: str = Field(default="")
    name_en: str = Field(default="")
    sort_order: int = Field(default=0)
    status: bool = Field(default=True)
    agent_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.now)
