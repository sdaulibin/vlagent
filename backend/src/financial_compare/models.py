"""财务报告比对数据模型。"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class FinancialCompareTask(SQLModel, table=True):
    """财务报告比对任务"""
    __tablename__ = "financial_compare_tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True)

    # 文件信息
    docx_file_path: str = Field(description="基准 DOCX 文件路径")
    docx_file_name: str = Field(description="基准 DOCX 文件名")
    pdf_file_path: str = Field(description="年度报告 PDF 文件路径")
    pdf_file_name: str = Field(description="年度报告 PDF 文件名")

    # 比对页码范围（传给引擎的 PageRange）
    docx_start_page: int = Field(default=1, description="DOCX 起始页")
    docx_end_page: Optional[int] = Field(default=None, description="DOCX 结束页（空=到末尾）")
    pdf_start_page: int = Field(default=1, description="PDF 起始页")
    pdf_end_page: Optional[int] = Field(default=None, description="PDF 结束页（空=到末尾）")

    # 状态
    status: str = Field(default="pending")  # pending, processing, done, failed
    error_msg: Optional[str] = Field(default=None)
    duration: Optional[float] = Field(default=None, description="比对耗时(秒)")

    # 比对结果（引擎输出）
    diff_stats: Optional[str] = Field(default=None, description="差异汇总统计 JSON")
    diff_blocks: Optional[str] = Field(default=None, description="引擎 DiffRecord 列表 JSON")

    created_at: datetime = Field(default_factory=datetime.now)


# ---- DTO（非数据库表）----

class FinancialCompareStatusResponse(SQLModel):
    """轮询状态响应"""
    id: int
    status: str
    error_msg: Optional[str] = None
    duration: Optional[float] = None


class FinancialCompareTaskItem(SQLModel):
    """任务列表项（不含大字段）"""
    id: int
    docx_file_name: str
    pdf_file_name: str
    docx_start_page: int
    docx_end_page: Optional[int] = None
    pdf_start_page: int
    pdf_end_page: Optional[int] = None
    status: str
    duration: Optional[float] = None
    created_at: datetime


class FinancialCompareDetail(SQLModel):
    """任务详情（含比对结果）"""
    id: int
    docx_file_name: str
    pdf_file_name: str
    docx_start_page: int
    docx_end_page: Optional[int] = None
    pdf_start_page: int
    pdf_end_page: Optional[int] = None
    status: str
    error_msg: Optional[str] = None
    duration: Optional[float] = None
    diff_stats: Optional[str] = None
    diff_blocks: Optional[str] = None
    created_at: datetime
