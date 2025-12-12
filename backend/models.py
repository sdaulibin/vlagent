from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, Relationship, SQLModel

class FileRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_path: str
    status: str = Field(default="pending")  # pending, processing, done, failed
    created_at: datetime = Field(default_factory=datetime.now)
    error_msg: Optional[str] = None
    
    transactions: List["TransactionRecord"] = Relationship(back_populates="file_record")

class TransactionRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    sequence: Optional[str] = None # 序号
    transaction_time: Optional[str] = None # 交易时间
    channel: Optional[str] = None # 交易渠道
    income: Optional[str] = None # 收入
    expense: Optional[str] = None # 支出
    balance: Optional[str] = None # 账户余额
    currency: Optional[str] = None # 币种
    counterparty_account: Optional[str] = None # 对方账号
    counterparty_name: Optional[str] = None # 对方户名
    description: Optional[str] = None # 摘要备注
    
    file_record: Optional[FileRecord] = Relationship(back_populates="transactions")
