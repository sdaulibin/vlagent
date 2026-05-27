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
    comparison_mode: Optional[str] = Field(default=None, description="管线类型: structured 或 page")
    section_summary_a: Optional[str] = Field(default=None, description="文件A section 结构汇总（Markdown）")
    section_summary_b: Optional[str] = Field(default=None, description="文件B section 结构汇总（Markdown）")
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


class DocumentSection(SQLModel, table=True):
    """文档 section 结构记录"""
    __tablename__ = "document_sections"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(index=True, foreign_key="document_compare_tasks.id")
    user_id: Optional[str] = Field(default=None, index=True)
    doc_type: str = Field(description="'a' 或 'b'")
    role: str = Field(description="h1/h2/h3/h4/body/table/toc_item")
    title: str = Field(default="")
    text_content: str = Field(default="")
    source_indices: Optional[str] = Field(default=None, description="JSON array of InputLine source_index")
    parent_id: Optional[int] = Field(default=None, foreign_key="document_sections.id")
    order_index: int = Field(default=0)
    diff_type: Optional[str] = Field(default=None, description="equal/modified/added/deleted")
    diff_ops_json: Optional[str] = Field(default=None, description="文本级 diff 操作 JSON")
    page_number: Optional[int] = Field(default=None, description="映射到的 PDF 页码")
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
    comparison_mode: Optional[str] = None
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


class DocumentSectionItem(SQLModel):
    """Section 结构项"""
    id: int
    doc_type: str
    role: str
    title: str = ""
    text_content: str = ""
    source_indices: Optional[str] = None
    parent_id: Optional[int] = None
    order_index: int = 0
    diff_type: Optional[str] = None
    diff_ops_json: Optional[str] = None
    page_number: Optional[int] = None


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
    comparison_mode: Optional[str] = None
    created_at: datetime
    pages: List[DocumentPageDiffItem] = []
    sections: List[DocumentSectionItem] = []
