"""
文档比对数据模型

两张表：
- DocumentCompareTask: 比对任务
- DocumentPageDiff: 页级差异记录
"""
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional, List


class DocumentCompareTask(SQLModel, table=True):
    """文档比对任务"""
    __tablename__ = "document_compare_tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True)
    file_a_name: str
    file_a_path: str
    file_b_name: str
    file_b_path: str
    file_a_page_count: Optional[int] = None
    file_b_page_count: Optional[int] = None
    status: str = Field(default="pending")  # pending, processing, done, failed
    error_msg: Optional[str] = None
    comparison_duration: Optional[float] = Field(default=None, description="比对耗时(秒)")
    created_at: datetime = Field(default_factory=datetime.now)


class DocumentPageDiff(SQLModel, table=True):
    """页级差异记录"""
    __tablename__ = "document_page_diffs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True)
    task_id: int = Field(index=True, foreign_key="document_compare_tasks.id")
    page_a: Optional[int] = Field(default=None, description="文档A页码(1-based)，整页新增时为null")
    page_b: Optional[int] = Field(default=None, description="文档B页码(1-based)，整页删除时为null")
    diff_type: str = Field(description="equal/modified/added/deleted")
    text_a: Optional[str] = Field(default=None, description="文档A该页纯文本（用于 diff 计算）")
    text_b: Optional[str] = Field(default=None, description="文档B该页纯文本")
    html_a: Optional[str] = Field(default=None, description="文档A该页 HTML（用于格式化展示）")
    html_b: Optional[str] = Field(default=None, description="文档B该页 HTML")
    diff_ops_json: Optional[str] = Field(default=None, description="diff-match-patch 操作 JSON")
    created_at: datetime = Field(default_factory=datetime.now)


# ---- DTO 模型（非数据库，用于 API 响应）----

class DocumentTaskListItem(SQLModel):
    """任务列表项"""
    id: int
    file_a_name: str
    file_b_name: str
    file_a_page_count: Optional[int] = None
    file_b_page_count: Optional[int] = None
    status: str
    error_msg: Optional[str] = None
    comparison_duration: Optional[float] = None
    created_at: datetime


class DocumentTaskStatusResponse(SQLModel):
    """轮询用轻量状态"""
    id: int
    status: str
    error_msg: Optional[str] = None


class DocumentPageDiffItem(SQLModel):
    """单页比对结果"""
    id: int
    page_a: Optional[int] = None
    page_b: Optional[int] = None
    diff_type: str
    text_a: Optional[str] = None
    text_b: Optional[str] = None
    html_a: Optional[str] = None
    html_b: Optional[str] = None
    diff_ops_json: Optional[str] = None


class DocumentCompareResponse(SQLModel):
    """完整任务详情"""
    id: int
    file_a_name: str
    file_b_name: str
    file_a_page_count: Optional[int] = None
    file_b_page_count: Optional[int] = None
    status: str
    error_msg: Optional[str] = None
    comparison_duration: Optional[float] = None
    created_at: datetime
    pages: List[DocumentPageDiffItem] = []
