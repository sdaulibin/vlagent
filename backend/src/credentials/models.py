"""
类凭证识别数据模型

分为两张表：
- CredentialRecord: 提取记录（文件 + 凭证类型）
- CredentialResult: 提取结果（JSON）
"""
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional, Dict, Any


class CredentialRecord(SQLModel, table=True):
    """类凭证提取记录"""
    __tablename__ = "credential_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(index=True)
    file_path: str
    credential_type: str = Field(description="凭证类型: id_card, bank_card, etc.")
    status: str = Field(default="pending")  # pending, processing, done, failed
    processing_duration: Optional[float] = Field(default=None, description="处理耗时(s)")
    error_msg: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CredentialResult(SQLModel, table=True):
    """类凭证提取结果"""
    __tablename__ = "credential_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    record_id: int = Field(index=True, foreign_key="credential_records.id")
    credential_type: str
    extracted_data: str = Field(default="{}", description="提取结果 JSON 字符串")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CredentialRecordListItem(SQLModel):
    """API 返回 - 记录列表项"""
    id: int
    filename: str
    credential_type: str
    status: str
    processing_duration: Optional[float] = None
    error_msg: Optional[str] = None
    created_at: Optional[datetime] = None


class CredentialRecordResponse(SQLModel):
    """API 返回 - 记录详情"""
    id: int
    filename: str
    credential_type: str
    status: str
    processing_duration: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error_msg: Optional[str] = None
