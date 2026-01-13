"""
交通银行处理器
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete

from src.banks.base import BankHandler, register_bank
from src.models.bocom_models import BocomSummary, BocomTransaction
from src.transactions.service import (
    create_bocom_transaction_records,
    create_bocom_summary_record,
)


@register_bank
class BocomHandler(BankHandler):
    """交通银行处理器
    
    特点：
    - 标准页面布局，顶部汇总信息
    - 含会计日期和交易日期双日期字段
    - 流水号以 EBP 开头
    """
    
    bank_type = "bocom"
    
    async def get_transactions(
        self, 
        session: AsyncSession, 
        file_id: int, 
        summary_id: int = None
    ) -> List[Dict[str, Any]]:
        statement = select(BocomTransaction).where(BocomTransaction.file_id == file_id)
        result = await session.execute(statement)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "sequence": r.sequence,
                "accounting_date": r.accounting_date,
                "transaction_date": r.transaction_date,
                "transaction_name": r.transaction_name,
                "voucher_type": r.voucher_type,
                "voucher_number": r.voucher_number,
                "debit_amount": r.debit_amount,
                "credit_amount": r.credit_amount,
                "balance": r.balance,
                "card_number": r.card_number,
                "transaction_location": r.transaction_location,
                "counterparty_account": r.counterparty_account,
                "counterparty_name": r.counterparty_name,
                "counterparty_bank": r.counterparty_bank,
                "description": r.description,
                "serial_no": r.serial_no,
                "bank_type": self.bank_type
            }
            for r in records
        ]
    
    async def get_summary(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> Optional[Dict[str, Any]]:
        statement = select(BocomSummary).where(BocomSummary.file_id == file_id)
        result = await session.execute(statement)
        summary = result.scalar_one_or_none()
        if summary:
            return {
                "bank_branch": summary.bank_branch,
                "account_number": summary.account_number,
                "account_name": summary.account_name,
                "currency": summary.currency,
                "year": summary.year,
                "month": summary.month,
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
        summary_stmt = select(BocomSummary).where(BocomSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["开户机构", summary.bank_branch])
            ws.append(["账号", summary.account_number])
            ws.append(["户名", summary.account_name])
            ws.append(["币种", summary.currency])
            ws.append(["年份", summary.year])
            ws.append(["月份", summary.month])
            ws.append([])
        
        # 交易明细表头
        headers = [
            "序号", "会计日期", "交易日期", "交易名称", "凭证种类", "凭证号码",
            "借方发生额", "贷方发生额", "余额", "卡号", "交易地点",
            "对方账号", "对方户名", "对方行名", "摘要", "流水号"
        ]
        ws.append(headers)
        tx_stmt = select(BocomTransaction).where(BocomTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([
                tx.sequence, tx.accounting_date, tx.transaction_date,
                tx.transaction_name, tx.voucher_type, tx.voucher_number,
                tx.debit_amount, tx.credit_amount, tx.balance,
                tx.card_number, tx.transaction_location,
                tx.counterparty_account, tx.counterparty_name, tx.counterparty_bank,
                tx.description, tx.serial_no
            ])
    
    def create_records(
        self, 
        file_id: int, 
        transactions_data: List[Dict], 
        summary_data: Dict
    ) -> tuple:
        transactions = create_bocom_transaction_records(file_id, transactions_data)
        summary = create_bocom_summary_record(file_id, summary_data)
        return transactions, summary
    
    async def delete_records(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> None:
        await session.execute(
            delete(BocomTransaction).where(BocomTransaction.file_id == file_id)
        )
        await session.execute(
            delete(BocomSummary).where(BocomSummary.file_id == file_id)
        )
    
    # ============================================================
    # 识别配置相关方法
    # ============================================================
    
    def get_bank_names(self) -> List[str]:
        return ["交通银行", "交行", "BOCOM", "Bank of Communications"]
    
    def get_summary_schema(self) -> Dict[str, Any]:
        return {
            "开户机构": "",
            "账号": "",
            "户名": "",
            "币种": "",
            "年份": "",
            "月份": ""
        }
    
    def get_transaction_schema(self) -> Dict[str, Any]:
        return [{
            "序号": "",
            "会计日期": "",
            "交易日期": "",
            "交易名称": "",
            "凭证种类": "",
            "凭证号码": "",
            "借方发生额": "",
            "贷方发生额": "",
            "余额": "",
            "卡号": "",
            "交易地点": "",
            "对方账号": "",
            "对方户名": "",
            "对方行名": "",
            "摘要": "",
            "流水号": ""
        }]
