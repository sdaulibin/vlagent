"""
济宁银行处理器
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete

from src.banks.base import BankHandler, register_bank
from src.transactions.models import JiningSummary, JiningTransaction
from src.transactions.service import (
    create_jining_transaction_records,
    create_jining_summary_record,
)


@register_bank
class JiningHandler(BankHandler):
    """济宁银行处理器"""
    
    bank_type = "jining"
    
    async def get_transactions(
        self, 
        session: AsyncSession, 
        file_id: int, 
        summary_id: int = None
    ) -> List[Dict[str, Any]]:
        statement = select(JiningTransaction).where(JiningTransaction.file_id == file_id)
        result = await session.execute(statement)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "sequence": r.sequence,
                "transaction_date": r.transaction_date,
                "channel": r.channel,
                "income": r.income,
                "expense": r.expense,
                "balance": r.balance,
                "description": r.description,
                "counterparty_info": r.counterparty_info,
                "bank_type": self.bank_type
            }
            for r in records
        ]
    
    async def get_summary(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> Optional[Dict[str, Any]]:
        statement = select(JiningSummary).where(JiningSummary.file_id == file_id)
        result = await session.execute(statement)
        summary = result.scalar_one_or_none()
        if summary:
            return {
                "account_name": summary.account_name,
                "account_number": summary.account_number,
                "date_range": summary.date_range,
                "currency": summary.currency,
                "income_total": summary.income_total,
                "expense_total": summary.expense_total,
                "bank_name": summary.bank_name,
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
        summary_stmt = select(JiningSummary).where(JiningSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["账号", summary.account_number])
            ws.append(["账户名称", summary.account_name])
            ws.append(["起止日期", summary.date_range])
            ws.append(["币种", summary.currency])
            ws.append(["收入金额合计", summary.income_total])
            ws.append(["支出金额合计", summary.expense_total])
            ws.append(["开户机构", summary.bank_name])
            ws.append([])
        
        # 交易明细
        headers = ["序号", "记账日期", "交易渠道", "收入", "支出", "账户余额", "摘要备注", "交易对手信息"]
        ws.append(headers)
        tx_stmt = select(JiningTransaction).where(JiningTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([
                tx.sequence, tx.transaction_date, tx.channel, 
                tx.income, tx.expense, tx.balance, 
                tx.description, tx.counterparty_info
            ])
    
    def create_records(
        self, 
        file_id: int, 
        transactions_data: List[Dict], 
        summary_data: Dict
    ) -> tuple:
        transactions = create_jining_transaction_records(file_id, transactions_data)
        summary = create_jining_summary_record(file_id, summary_data)
        return transactions, summary
    
    async def delete_records(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> None:
        await session.execute(
            delete(JiningTransaction).where(JiningTransaction.file_id == file_id)
        )
        await session.execute(
            delete(JiningSummary).where(JiningSummary.file_id == file_id)
        )
