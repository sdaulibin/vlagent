"""
解析结果数据模型

定义银行流水 PDF 解析的输出结构。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class Transaction:
    """单条交易记录"""
    # 基础字段
    sequence: Optional[str] = None              # 序号
    transaction_time: Optional[str] = None      # 交易时间
    transaction_date: Optional[str] = None      # 交易日期
    serial_no: Optional[str] = None             # 流水号

    # 金额字段
    income: Optional[str] = None                # 收入/贷方
    expense: Optional[str] = None               # 支出/借方
    balance: Optional[str] = None               # 余额
    currency: Optional[str] = None              # 币种

    # 对方信息
    counterparty_account: Optional[str] = None  # 对方账号
    counterparty_name: Optional[str] = None     # 对方户名
    counterparty_bank: Optional[str] = None     # 对方开户行
    counterparty_bank_code: Optional[str] = None  # 对方行号

    # 交易详情
    description: Optional[str] = None           # 摘要
    purpose: Optional[str] = None               # 用途
    remark: Optional[str] = None                # 备注
    transaction_type: Optional[str] = None      # 交易类型
    channel: Optional[str] = None               # 交易渠道

    # 其他字段
    voucher_no: Optional[str] = None            # 凭证号
    debit_credit: Optional[str] = None          # 借贷标志
    value_date: Optional[str] = None            # 起息日

    # 扩展字段（用于存储银行特有字段）
    extra: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "sequence": self.sequence,
            "transaction_time": self.transaction_time,
            "transaction_date": self.transaction_date,
            "serial_no": self.serial_no,
            "income": self.income,
            "expense": self.expense,
            "balance": self.balance,
            "currency": self.currency,
            "counterparty_account": self.counterparty_account,
            "counterparty_name": self.counterparty_name,
            "counterparty_bank": self.counterparty_bank,
            "counterparty_bank_code": self.counterparty_bank_code,
            "description": self.description,
            "purpose": self.purpose,
            "remark": self.remark,
            "transaction_type": self.transaction_type,
            "channel": self.channel,
            "voucher_no": self.voucher_no,
            "debit_credit": self.debit_credit,
            "value_date": self.value_date,
        }
        # 添加扩展字段
        result.update(self.extra)
        # 过滤空值
        return {k: v for k, v in result.items() if v is not None}


@dataclass
class Summary:
    """汇总信息"""
    account_name: Optional[str] = None          # 户名
    account_number: Optional[str] = None        # 账号
    bank_name: Optional[str] = None             # 开户行
    currency: Optional[str] = None              # 币种
    date_range: Optional[str] = None            # 起止日期
    start_date: Optional[str] = None            # 起始日期
    end_date: Optional[str] = None              # 结束日期
    income_total: Optional[str] = None          # 收入总金额
    expense_total: Optional[str] = None         # 支出总金额
    income_count: Optional[str] = None          # 收入总笔数
    expense_count: Optional[str] = None         # 支出总笔数

    # 扩展字段
    extra: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "account_name": self.account_name,
            "account_number": self.account_number,
            "bank_name": self.bank_name,
            "currency": self.currency,
            "date_range": self.date_range,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "income_total": self.income_total,
            "expense_total": self.expense_total,
            "income_count": self.income_count,
            "expense_count": self.expense_count,
        }
        result.update(self.extra)
        return {k: v for k, v in result.items() if v is not None}


@dataclass
class ParseResult:
    """解析结果"""
    is_native: bool = True                      # 是否为原生 PDF
    bank_type: str = "unknown"                  # 银行类型
    summary: Summary = field(default_factory=Summary)  # 汇总信息
    transactions: List[Transaction] = field(default_factory=list)  # 交易记录
    headers: List[str] = field(default_factory=list)   # 标准表头
    raw_headers: List[str] = field(default_factory=list)  # 原始表头
    page_count: int = 0                         # 页数
    total_rows: int = 0                         # 总行数
    extraction_strategy: str = ""               # 使用的提取策略
    error: Optional[str] = None                 # 错误信息

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（兼容旧 API）"""
        return {
            "is_native": self.is_native,
            "bank_type": self.bank_type,
            "summary": self.summary.to_dict(),
            "transactions": [t.to_dict() for t in self.transactions],
            "headers": self.headers,
            "raw_headers": self.raw_headers,
            "page_count": self.page_count,
            "total_rows": self.total_rows,
            "extraction_strategy": self.extraction_strategy,
            "error": self.error,
        }
