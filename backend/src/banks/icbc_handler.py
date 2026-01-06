"""
工商银行处理器
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete

from src.banks.base import BankHandler, register_bank
from src.models.icbc_models import IcbcSummary, IcbcTransaction
from src.transactions.service import (
    create_icbc_transaction_records,
    create_icbc_summary_record,
)


@register_bank
class IcbcHandler(BankHandler):
    """工商银行处理器"""
    
    bank_type = "icbc"
    
    async def get_transactions(
        self, 
        session: AsyncSession, 
        file_id: int, 
        summary_id: int = None
    ) -> List[Dict[str, Any]]:
        statement = select(IcbcTransaction).where(IcbcTransaction.file_id == file_id)
        result = await session.execute(statement)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "transaction_time": r.transaction_time,
                "income": r.income,
                "expense": r.expense,
                "counterparty_account": r.counterparty_account,
                "debit_credit": r.debit_credit,
                "counterparty_name": r.counterparty_name,
                "counterparty_bank_code": r.counterparty_bank_code,
                "description": r.description,
                "purpose": r.purpose,
                "bank_type": self.bank_type
            }
            for r in records
        ]
    
    async def get_summary(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> Optional[Dict[str, Any]]:
        statement = select(IcbcSummary).where(IcbcSummary.file_id == file_id)
        result = await session.execute(statement)
        summary = result.scalar_one_or_none()
        if summary:
            return {
                "account_number": summary.account_number,
                "account_name": summary.account_name,
                "currency": summary.currency,
                "bank_name": summary.bank_name,
                "date_range": summary.date_range,
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
        summary_stmt = select(IcbcSummary).where(IcbcSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["账号", summary.account_number])
            ws.append(["本方账号户名", summary.account_name])
            ws.append(["币种", summary.currency])
            ws.append(["本方账号开户行", summary.bank_name])
            ws.append(["财务日期范围", summary.date_range])
            ws.append([])
        
        # 交易明细
        headers = ["交易时间", "转入金额", "转出金额", "对方账号", "借贷标志", "对方单位", "对方行号", "摘要", "用途"]
        ws.append(headers)
        tx_stmt = select(IcbcTransaction).where(IcbcTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([
                tx.transaction_time, tx.income, tx.expense, 
                tx.counterparty_account, tx.debit_credit, tx.counterparty_name,
                tx.counterparty_bank_code, tx.description, tx.purpose
            ])
    
    def create_records(
        self, 
        file_id: int, 
        transactions_data: List[Dict], 
        summary_data: Dict
    ) -> tuple:
        transactions = create_icbc_transaction_records(file_id, transactions_data)
        summary = create_icbc_summary_record(file_id, summary_data)
        return transactions, summary
    
    async def delete_records(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> None:
        await session.execute(
            delete(IcbcTransaction).where(IcbcTransaction.file_id == file_id)
        )
        await session.execute(
            delete(IcbcSummary).where(IcbcSummary.file_id == file_id)
        )
    
    # ============================================================
    # 识别配置相关方法
    # ============================================================
    
    def get_bank_names(self) -> List[str]:
        return ["中国工商银行", "工商银行", "工行", "ICBC"]
    
    def get_summary_schema(self) -> Dict[str, Any]:
        return {
            "账号": "",
            "本方账号户名": "",
            "币种": "",
            "本方账号开户行": "",
            "财务日期范围": ""
        }
    
    def get_transaction_schema(self) -> Dict[str, Any]:
        return {
            "交易时间": "",
            "转入金额": "",
            "转出金额": "",
            "对方账号": "",
            "借贷标志": "",
            "对方单位": "",
            "对方行号": "",
            "用途": "",
            "摘要": ""
        }
