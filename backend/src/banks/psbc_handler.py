"""
邮储银行处理器
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete

from src.banks.base import BankHandler, register_bank
from src.transactions.models import PsbcSummary, PsbcTransaction
from src.transactions.service import (
    create_psbc_transaction_records,
    create_psbc_summary_record,
)


@register_bank
class PsbcHandler(BankHandler):
    """邮储银行处理器"""
    
    bank_type = "psbc"
    
    async def get_transactions(
        self, 
        session: AsyncSession, 
        file_id: int, 
        summary_id: int = None
    ) -> List[Dict[str, Any]]:
        statement = select(PsbcTransaction).where(PsbcTransaction.file_id == file_id)
        result = await session.execute(statement)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "serial_no": r.serial_no,
                "global_route_no": r.global_route_no,
                "transaction_time": r.transaction_time,
                "transaction_date": r.transaction_date,
                "income": r.income,
                "expense": r.expense,
                "balance": r.balance,
                "counterparty_account": r.counterparty_account,
                "counterparty_name": r.counterparty_name,
                "counterparty_bank": r.counterparty_bank,
                "purpose": r.purpose,
                "postscript": r.postscript,
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
        statement = select(PsbcSummary).where(PsbcSummary.file_id == file_id)
        result = await session.execute(statement)
        summary = result.scalar_one_or_none()
        if summary:
            return {
                "account_name": summary.account_name,
                "account_number": summary.account_number,
                "start_date": summary.start_date,
                "end_date": summary.end_date,
                "income_total": summary.income_total,
                "expense_total": summary.expense_total,
                "income_count": summary.income_count,
                "expense_count": summary.expense_count,
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
        summary_stmt = select(PsbcSummary).where(PsbcSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["户名", summary.account_name])
            ws.append(["账号", summary.account_number])
            ws.append(["起始日期", summary.start_date])
            ws.append(["结束日期", summary.end_date])
            ws.append(["收入总金额", summary.income_total])
            ws.append(["支出总金额", summary.expense_total])
            ws.append(["收入总笔数", summary.income_count])
            ws.append(["支出总笔数", summary.expense_count])
            ws.append([])
        
        # 交易明细
        headers = ["交易时间", "记账日期", "支出金额", "收入金额", "余额", "对方账号", "对方户名", "对方行名", "用途", "附言", "摘要", "交易流水号", "全局路由号"]
        ws.append(headers)
        tx_stmt = select(PsbcTransaction).where(PsbcTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([
                tx.transaction_time, tx.transaction_date, tx.expense, tx.income, 
                tx.balance, tx.counterparty_account, tx.counterparty_name, 
                tx.counterparty_bank, tx.purpose, tx.postscript, 
                tx.description, tx.serial_no, tx.global_route_no
            ])
    
    def create_records(
        self, 
        file_id: int, 
        transactions_data: List[Dict], 
        summary_data: Dict
    ) -> tuple:
        transactions = create_psbc_transaction_records(file_id, transactions_data)
        summary = create_psbc_summary_record(file_id, summary_data)
        return transactions, summary
    
    async def delete_records(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> None:
        await session.execute(
            delete(PsbcTransaction).where(PsbcTransaction.file_id == file_id)
        )
        await session.execute(
            delete(PsbcSummary).where(PsbcSummary.file_id == file_id)
        )
