"""
通用 PDF 提取数据模型

分为两张表：
- PdfExtractTask: 提取任务（文件 + 字段定义）
- PdfExtractResult: 提取结果
"""
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional, List, Any, Dict
from enum import Enum


class OutputFormat(str, Enum):
    """导出格式"""
    JSON = "json"
    CSV = "csv"
    XLSX = "xlsx"


class PdfExtractTask(SQLModel, table=True):
    """PDF 提取任务"""
    __tablename__ = "pdf_extract_tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(index=True)
    file_path: str
    status: str = Field(default="pending")  # pending, processing, done, failed
    fields_json: str = Field(description="用户定义的提取字段列表 JSON")
    output_format: str = Field(default="json")
    page_count: Optional[int] = Field(default=0)
    processing_duration: Optional[float] = Field(default=None, description="处理耗时(s)")
    error_msg: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class PdfExtractResult(SQLModel, table=True):
    """PDF 提取结果"""
    __tablename__ = "pdf_extract_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(index=True, foreign_key="pdf_extract_tasks.id")
    extracted_data: str = Field(default="{}", description="提取结果 JSON 字符串")
    error_msg: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PdfExtractTaskListItem(SQLModel):
    """API 返回 - 任务列表项"""
    id: int
    filename: str
    status: str
    output_format: str = "json"
    page_count: Optional[int] = None
    processing_duration: Optional[float] = None
    error_msg: Optional[str] = None
    created_at: Optional[datetime] = None


class PdfExtractTaskResponse(SQLModel):
    """API 返回 - 任务详情"""
    id: int
    filename: str
    status: str
    output_format: str = "json"
    page_count: Optional[int] = None
    processing_duration: Optional[float] = None
    fields: List[Dict[str, Any]] = []
    result: Optional[Dict[str, Any]] = None
    error_msg: Optional[str] = None
