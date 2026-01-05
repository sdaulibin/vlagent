from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from src.transactions.models import (
        ShandongLocalSummary, ShandongLocalTransaction,
        EverbrightSummary, EverbrightTransaction,
        CmbSummary, CmbTransaction,
        JiningSummary, JiningTransaction,
        CgbSummary, CgbTransaction,
        PsbcSummary, PsbcTransaction,
    )


class FileRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_path: str
    status: str = "pending"
    bank_type: Optional[str] = None  # 银行模板类型: shandong_local, everbright, cmb
    created_at: datetime = Field(default_factory=datetime.now)
    recognition_duration: Optional[float] = None  # 识别耗时（毫秒）
    error_msg: Optional[str] = None
    
    # 山东地方银行关联（保持向后兼容）
    transactions: List["ShandongLocalTransaction"] = Relationship(back_populates="file_record")
    summary: Optional["ShandongLocalSummary"] = Relationship(back_populates="file_record")
    
    # 光大银行关联
    everbright_transactions: List["EverbrightTransaction"] = Relationship(back_populates="file_record")
    everbright_summary: Optional["EverbrightSummary"] = Relationship(back_populates="file_record")
    
    # 招商银行关联
    cmb_transactions: List["CmbTransaction"] = Relationship(back_populates="file_record")
    cmb_summary: Optional["CmbSummary"] = Relationship(back_populates="file_record")
    
    # 济宁银行关联
    jining_transactions: List["JiningTransaction"] = Relationship(back_populates="file_record")
    jining_summary: Optional["JiningSummary"] = Relationship(back_populates="file_record")
    
    # 广发银行关联（一对多：一个文件可以有多个汇总）
    cgb_transactions: List["CgbTransaction"] = Relationship(back_populates="file_record")
    cgb_summary: List["CgbSummary"] = Relationship(back_populates="file_record")
    
    # 邮储银行关联
    psbc_transactions: List["PsbcTransaction"] = Relationship(back_populates="file_record")
    psbc_summary: Optional["PsbcSummary"] = Relationship(back_populates="file_record")


# 从 transactions 模块导入模型（向后兼容）
from src.transactions.models import (
    ShandongLocalSummary, ShandongLocalTransaction,
    EverbrightSummary, EverbrightTransaction,
    CmbSummary, CmbTransaction,
    JiningSummary, JiningTransaction,
    CgbSummary, CgbTransaction,
    PsbcSummary, PsbcTransaction,
    SummaryRecord, TransactionRecord,
)

__all__ = [
    "FileRecord",
    "ShandongLocalSummary", "ShandongLocalTransaction",
    "EverbrightSummary", "EverbrightTransaction",
    "CmbSummary", "CmbTransaction",
    "JiningSummary", "JiningTransaction",
    "CgbSummary", "CgbTransaction",
    "PsbcSummary", "PsbcTransaction",
    "SummaryRecord", "TransactionRecord",
]
