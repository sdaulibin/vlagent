from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class CompareTask(SQLModel, table=True):
    """合同比对任务"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_a_name: str = Field(description="原文档文件名")
    file_a_path: str = Field(description="原文档路径")
    file_b_name: str = Field(description="比对文档文件名")
    file_b_path: str = Field(description="比对文档路径")
    status: str = Field(default="pending", description="任务状态: pending, processing, done, failed")
    error_msg: Optional[str] = Field(default=None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class DiffRecord(SQLModel, table=True):
    """差异记录"""
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="comparetask.id", description="所属比对任务ID")
    diff_type: str = Field(description="差异类型: added, deleted, modified")
    original_text: str = Field(default="", description="原文内容")
    comparison_text: str = Field(default="", description="比对文内容")
    location: str = Field(default="", description="位置信息")
    status: str = Field(default="pending", description="状态: pending, ignored")
    created_at: datetime = Field(default_factory=datetime.now)
