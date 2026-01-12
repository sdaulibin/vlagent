"""
农业银行处理器
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete

from src.banks.base import BankHandler, register_bank
from src.models.abc_models import AbcSummary, AbcTransaction
from src.transactions.service import (
    create_abc_transaction_records,
    create_abc_summary_record,
)


@register_bank
class AbcHandler(BankHandler):
    """农业银行处理器
    
    特殊处理：农业银行的汇总信息分布在首页顶部和末页底部
    - 首页：账号、户名、币种、起止日期
    - 末页：总收入笔数、总收入金额、总支出笔数、总支出金额
    """
    
    bank_type = "abc"
    
    async def get_transactions(
        self, 
        session: AsyncSession, 
        file_id: int, 
        summary_id: int = None
    ) -> List[Dict[str, Any]]:
        statement = select(AbcTransaction).where(AbcTransaction.file_id == file_id)
        result = await session.execute(statement)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "transaction_time": r.transaction_time,
                "income": r.income,
                "expense": r.expense,
                "balance": r.balance,
                "counterparty_account": r.counterparty_account,
                "counterparty_name": r.counterparty_name,
                "counterparty_bank": r.counterparty_bank,
                "description": r.description,
                "bank_type": self.bank_type
            }
            for r in records
        ]
    
    async def get_summary(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> Optional[Dict[str, Any]]:
        statement = select(AbcSummary).where(AbcSummary.file_id == file_id)
        result = await session.execute(statement)
        summary = result.scalar_one_or_none()
        if summary:
            return {
                "account_number": summary.account_number,
                "account_name": summary.account_name,
                "currency": summary.currency,
                "date_range": summary.date_range,
                "income_count": summary.income_count,
                "income_total": summary.income_total,
                "expense_count": summary.expense_count,
                "expense_total": summary.expense_total,
                "bank_type": self.bank_type
            }
        return None
    
    async def export_to_excel(
        self, 
        session: AsyncSession, 
        file_id: int, 
        ws
    ) -> None:
        # 汇总信息
        summary_stmt = select(AbcSummary).where(AbcSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["账号", summary.account_number])
            ws.append(["户名", summary.account_name])
            ws.append(["币种", summary.currency])
            ws.append(["起止日期", summary.date_range])
            ws.append(["总收入笔数", summary.income_count])
            ws.append(["总收入金额", summary.income_total])
            ws.append(["总支出笔数", summary.expense_count])
            ws.append(["总支出金额", summary.expense_total])
            ws.append([])
        
        # 交易明细
        headers = ["交易时间", "收入金额", "支出金额", "账户余额", "对方账号", "对方户名", "对方开户行", "摘要"]
        ws.append(headers)
        tx_stmt = select(AbcTransaction).where(AbcTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([
                tx.transaction_time, tx.income, tx.expense, tx.balance,
                tx.counterparty_account, tx.counterparty_name,
                tx.counterparty_bank, tx.description
            ])
    
    def create_records(
        self, 
        file_id: int, 
        transactions_data: List[Dict], 
        summary_data: Dict
    ) -> tuple:
        transactions = create_abc_transaction_records(file_id, transactions_data)
        summary = create_abc_summary_record(file_id, summary_data)
        return transactions, summary
    
    async def delete_records(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> None:
        await session.execute(
            delete(AbcTransaction).where(AbcTransaction.file_id == file_id)
        )
        await session.execute(
            delete(AbcSummary).where(AbcSummary.file_id == file_id)
        )
    
    # ============================================================
    # 识别配置相关方法
    # ============================================================
    
    def get_bank_names(self) -> List[str]:
        return ["中国农业银行", "农业银行", "农行", "ABC"]
    
    def get_summary_schema(self) -> Dict[str, Any]:
        return {
            "账号": "",
            "户名": "",
            "币种": "",
            "起止日期": "",
            "总收入笔数": "",
            "总收入金额": "",
            "总支出笔数": "",
            "总支出金额": ""
        }
    
    def get_transaction_schema(self) -> Dict[str, Any]:
        return [{
            "交易时间": "",
            "收入金额": "",
            "支出金额": "",
            "账户余额": "",
            "对方账号": "",
            "对方户名": "",
            "对方开户行": "",
            "摘要": ""
        }]
    
    def get_summary_config(self) -> Dict[str, Any]:
        """返回汇总提取配置
        
        农业银行特殊：汇总信息分布在首页和末页
        """
        return {
            "first_page_only": False,
            "extract_from_last_page": True
        }
