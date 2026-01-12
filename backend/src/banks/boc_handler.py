"""
中国银行处理器（中英双语表头）
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete

from src.banks.base import BankHandler, register_bank
from src.models.boc_models import BocSummary, BocTransaction
from src.transactions.service import (
    create_boc_transaction_records,
    create_boc_summary_record,
)


@register_bank
class BocHandler(BankHandler):
    """中国银行处理器
    
    特点：
    - 中英双语表头（如 账号 Account No.、记账日 Bk.D.）
    - 汇总信息仅在首页顶部
    """
    
    bank_type = "boc"
    
    async def get_transactions(
        self, 
        session: AsyncSession, 
        file_id: int, 
        summary_id: int = None
    ) -> List[Dict[str, Any]]:
        statement = select(BocTransaction).where(BocTransaction.file_id == file_id)
        result = await session.execute(statement)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "sequence": r.sequence,
                "booking_date": r.booking_date,
                "value_date": r.value_date,
                "transaction_type": r.transaction_type,
                "voucher": r.voucher,
                "transaction_details": r.transaction_details,
                "debit_amount": r.debit_amount,
                "credit_amount": r.credit_amount,
                "balance": r.balance,
                "reference_no": r.reference_no,
                "notes": r.notes,
                "bank_type": self.bank_type
            }
            for r in records
        ]
    
    async def get_summary(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> Optional[Dict[str, Any]]:
        statement = select(BocSummary).where(BocSummary.file_id == file_id)
        result = await session.execute(statement)
        summary = result.scalar_one_or_none()
        if summary:
            return {
                "account_number": summary.account_number,
                "account_name": summary.account_name,
                "currency": summary.currency,
                "account_type": summary.account_type,
                "bank_name": summary.bank_name,
                "start_date": summary.start_date,
                "end_date": summary.end_date,
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
        summary_stmt = select(BocSummary).where(BocSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["账号 Account No.", summary.account_number])
            ws.append(["账户名称 Account Name", summary.account_name])
            ws.append(["币种 Currency", summary.currency])
            ws.append(["账户类型 Account Type", summary.account_type])
            ws.append(["开户行 Bank Name", summary.bank_name])
            ws.append(["起始日期 From", summary.start_date])
            ws.append(["截止日期 To", summary.end_date])
            ws.append([])
        
        # 交易明细表头
        headers = [
            "序号", "记账日", "起息日", "交易类型", "凭证", 
            "凭证号/业务号/用途/摘要", "借方发生额", "贷方发生额", 
            "余额", "机构/柜员/流水", "备注"
        ]
        ws.append(headers)
        tx_stmt = select(BocTransaction).where(BocTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([
                tx.sequence, tx.booking_date, tx.value_date, tx.transaction_type,
                tx.voucher, tx.transaction_details, tx.debit_amount, tx.credit_amount,
                tx.balance, tx.reference_no, tx.notes
            ])
    
    def create_records(
        self, 
        file_id: int, 
        transactions_data: List[Dict], 
        summary_data: Dict
    ) -> tuple:
        transactions = create_boc_transaction_records(file_id, transactions_data)
        summary = create_boc_summary_record(file_id, summary_data)
        return transactions, summary
    
    async def delete_records(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> None:
        await session.execute(
            delete(BocTransaction).where(BocTransaction.file_id == file_id)
        )
        await session.execute(
            delete(BocSummary).where(BocSummary.file_id == file_id)
        )
    
    # ============================================================
    # 识别配置相关方法
    # ============================================================
    
    def get_bank_names(self) -> List[str]:
        return ["中国银行", "中行", "BOC", "Bank of China"]
    
    def get_summary_schema(self) -> Dict[str, Any]:
        return {
            "账号": "",
            "账户名称": "",
            "币种": "",
            "账户类型": "",
            "开户行": "",
            "起始日期": "",
            "截止日期": ""
        }
    
    def get_transaction_schema(self) -> Dict[str, Any]:
        return [{
            "序号": "",
            "记账日": "",
            "起息日": "",
            "交易类型": "",
            "凭证": "",
            "凭证号业务号用途摘要": "",
            "借方发生额": "",
            "贷方发生额": "",
            "余额": "",
            "机构柜员流水": "",
            "备注": ""
        }]
