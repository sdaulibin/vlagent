"""
询证函数据模型
"""
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class ConfirmationLetter(SQLModel, table=True):
    """询证函记录"""
    __tablename__ = "confirmation_letters"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(index=True)
    file_path: str
    status: str = Field(default="pending")  # pending, processing, done, failed
    error_msg: Optional[str] = None
    
    # 识别字段（12项）
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
    
    # 元数据
    recognition_duration: Optional[float] = Field(default=None, description="识别耗时(ms)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class ConfirmationLetterUpdate(SQLModel):
    """询证函更新模型（用于人工修改）"""
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
