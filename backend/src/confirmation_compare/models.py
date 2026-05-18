"""
询证函格式比对 - 数据模型

拆分为两张表：
- FormatCompareFile: 上传文件元数据
- FormatCompareResult: 比对结果
"""
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional, List, Any


class FormatCompareFile(SQLModel, table=True):
    """格式比对文件记录"""
    __tablename__ = "format_compare_files"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True)
    filename: str = Field(index=True)
    file_path: str
    status: str = Field(default="pending")  # pending, processing, done, failed
    error_msg: Optional[str] = None
    duration_ms: Optional[float] = Field(default=None, description="比对耗时(ms)")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FormatCompareResult(SQLModel, table=True):
    """格式比对结果"""
    __tablename__ = "format_compare_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True)
    file_id: int = Field(index=True, foreign_key="format_compare_files.id")
    format_type: Optional[str] = Field(default=None, description="识别的格式类型: format_1/format_2/capital_verification")
    passed: Optional[bool] = Field(default=None, description="比对是否通过")
    mismatches_json: Optional[str] = Field(default=None, description="差异JSON")
    extracted_content_json: Optional[str] = Field(default=None, description="AI提取的结构化内容JSON")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FormatMismatchItem(SQLModel):
    """单条格式差异"""
    section: str = ""
    item: str = ""
    location: str = ""  # section / description / table_field
    expected: str = ""
    actual: str = ""
    severity: str = "high"  # high / medium / low


class FormatCompareTaskDTO(SQLModel):
    """比对任务返回 DTO"""
    id: int
    filename: str
    format_type: Optional[str] = None
    status: str
    passed: Optional[bool] = None
    mismatches: List[FormatMismatchItem] = Field(default_factory=list)
    extracted_content: Optional[List[Any]] = Field(default=None, description="AI提取的结构化内容")
    template_content: Optional[List[Any]] = Field(default=None, description="模板的结构化内容")
    error_msg: Optional[str] = None
    duration_ms: Optional[float] = None
    created_at: datetime


class TemplateInfo(SQLModel):
    """模板信息"""
    format_key: str
    format_name: str
    pdf_filename: str
