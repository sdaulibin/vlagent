"""
询证函数据模型

分为两张表：
- ConfirmationFile: 文件上传信息
- ConfirmationResult: 识别结果字段
"""
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional, List


class ConfirmationFile(SQLModel, table=True):
    """询证函文件记录"""
    __tablename__ = "confirmation_files"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(index=True)
    file_path: str
    status: str = Field(default="pending")  # pending, processing, done, failed
    error_msg: Optional[str] = None
    recognition_duration: Optional[float] = Field(default=None, description="识别耗时(ms)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class ConfirmationResult(SQLModel, table=True):
    """询证函识别结果"""
    __tablename__ = "confirmation_results"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: int = Field(index=True, foreign_key="confirmation_files.id")
    
    # 识别字段（13项）
    confirmation_no: Optional[str] = Field(default=None, description="函证编号")
    accounting_firm: Optional[str] = Field(default=None, description="事务所名称")
    reply_address: Optional[str] = Field(default=None, description="回函地址")
    contact_person: Optional[str] = Field(default=None, description="联系人")
    phone: Optional[str] = Field(default=None, description="电话")
    postal_code: Optional[str] = Field(default=None, description="邮编")
    debit_account: Optional[str] = Field(default=None, description="扣费账号")
    cutoff_date: Optional[str] = Field(default=None, description="截止日期")
    start_date: Optional[str] = Field(default=None, description="起始日期")
    end_date: Optional[str] = Field(default=None, description="终止日期")
    seal_date: Optional[str] = Field(default=None, description="印章日期")
    seal_name: Optional[str] = Field(default=None, description="印章名称")
    signature_name: Optional[str] = Field(default=None, description="落款名称")
    format_type: Optional[str] = Field(default=None, description="格式类型")
    format_check_passed: Optional[bool] = Field(default=None, description="格式校验是否通过")
    format_mismatches_json: Optional[str] = Field(default=None, description="格式差异JSON")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class ConfirmationResultUpdate(SQLModel):
    """识别结果更新模型（用于人工修改）"""
    confirmation_no: Optional[str] = None
    accounting_firm: Optional[str] = None
    reply_address: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    postal_code: Optional[str] = None
    debit_account: Optional[str] = None
    cutoff_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    seal_date: Optional[str] = None
    seal_name: Optional[str] = None
    signature_name: Optional[str] = None


class FormatMismatch(SQLModel):
    item: str = ""
    expected: str = ""
    actual: str = ""
    severity: str = "high"


class ConfirmationRecognitionDTO(SQLModel):
    id: Optional[int] = None
    file_id: int
    confirmation_no: Optional[str] = None
    accounting_firm: Optional[str] = None
    reply_address: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    postal_code: Optional[str] = None
    debit_account: Optional[str] = None
    cutoff_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    seal_date: Optional[str] = None
    seal_name: Optional[str] = None
    signature_name: Optional[str] = None
    format_type: Optional[str] = None
    format_check_passed: Optional[bool] = None
    format_mismatches: List[FormatMismatch] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConfirmationFileDTO(SQLModel):
    id: int
    filename: str
    status: str
    error_msg: Optional[str] = None
    recognition_duration: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    recognition: Optional[ConfirmationRecognitionDTO] = None
