from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.files.models import FileRecord


class CmbSummary(SQLModel, table=True):
    """招商银行流水汇总信息"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    account_number: Optional[str] = None     # 账号
    account_name: Optional[str] = None       # 账号名
    start_date: Optional[str] = None         # 开始日期
    end_date: Optional[str] = None           # 结束日期
    debit_count: Optional[str] = None        # 出账总笔数
    credit_count: Optional[str] = None       # 入账总笔数
    debit_total: Optional[str] = None        # 出账总金额
    credit_total: Optional[str] = None       # 入账总金额
    total_count: Optional[str] = None        # 笔数
    bank_name: str = "招商银行"              # 开户行
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="cmb_summary")


class CmbTransaction(SQLModel, table=True):
    """招商银行交易明细"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    serial_no: Optional[str] = None          # 交易流水号
    transaction_date: Optional[str] = None   # 交易日期
    debit_amount: Optional[str] = None       # 借方出账
    credit_amount: Optional[str] = None      # 贷方入账
    balance: Optional[str] = None            # 余额
    counterparty_name: Optional[str] = None  # 收付方名称
    counterparty_account: Optional[str] = None  # 收付方账号
    description: Optional[str] = None        # 摘要
    transaction_type: Optional[str] = None   # 交易类型
    card_no: Optional[str] = None            # 公司一卡通号
    print_instance_no: Optional[str] = None  # 打印实例号
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="cmb_transactions")
