"""
建设银行处理器
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete

from src.banks.base import BankHandler, register_bank
from src.models.ccb_models import CcbSummary, CcbTransaction
from src.transactions.service import (
    create_ccb_transaction_records,
    create_ccb_summary_record,
)


@register_bank
class CcbHandler(BankHandler):
    """建设银行处理器"""
    
    bank_type = "ccb"
    
    async def get_transactions(
        self, 
        session: AsyncSession, 
        file_id: int, 
        summary_id: int = None
    ) -> List[Dict[str, Any]]:
        statement = select(CcbTransaction).where(CcbTransaction.file_id == file_id)
        result = await session.execute(statement)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "account_number": r.account_number,
                "transaction_time": r.transaction_time,
                "debit_amount": r.debit_amount,
                "credit_amount": r.credit_amount,
                "balance": r.balance,
                "currency": r.currency,
                "counterparty_name": r.counterparty_name,
                "counterparty_account": r.counterparty_account,
                "counterparty_bank": r.counterparty_bank,
                "booking_date": r.booking_date,
                "description": r.description,
                "remark": r.remark,
                "transaction_serial": r.transaction_serial,
                "enterprise_serial": r.enterprise_serial,
                "voucher_type": r.voucher_type,
                "voucher_number": r.voucher_number,
                "transaction_medium": r.transaction_medium,
                "bank_type": self.bank_type
            }
            for r in records
        ]
    
    async def get_summary(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> Optional[Dict[str, Any]]:
        statement = select(CcbSummary).where(CcbSummary.file_id == file_id)
        result = await session.execute(statement)
        summary = result.scalar_one_or_none()
        if summary:
            return {
                "account_name": summary.account_name,
                "print_date": summary.print_date,
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
        summary_stmt = select(CcbSummary).where(CcbSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["本方户名", summary.account_name])
            ws.append(["打印日期", summary.print_date])
            ws.append([])
        
        # 交易明细
        headers = [
            "账号", "交易时间", "借方发生额", "贷方发生额", "余额", "币种",
            "对方户名", "对方账号", "对方开户机构", "记账日期", "摘要", "备注",
            "账户明细编号-交易流水号", "企业流水号", "凭证种类", "凭证号", "交易介质编号"
        ]
        ws.append(headers)
        tx_stmt = select(CcbTransaction).where(CcbTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([
                tx.account_number, tx.transaction_time, tx.debit_amount, tx.credit_amount,
                tx.balance, tx.currency, tx.counterparty_name, tx.counterparty_account,
                tx.counterparty_bank, tx.booking_date, tx.description, tx.remark,
                tx.transaction_serial, tx.enterprise_serial, tx.voucher_type,
                tx.voucher_number, tx.transaction_medium
            ])
    
    def create_records(
        self, 
        file_id: int, 
        transactions_data: List[Dict], 
        summary_data: Dict
    ) -> tuple:
        transactions = create_ccb_transaction_records(file_id, transactions_data)
        summary = create_ccb_summary_record(file_id, summary_data)
        return transactions, summary
    
    async def delete_records(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> None:
        await session.execute(
            delete(CcbTransaction).where(CcbTransaction.file_id == file_id)
        )
        await session.execute(
            delete(CcbSummary).where(CcbSummary.file_id == file_id)
        )
    
    # ============================================================
    # 识别配置相关方法
    # ============================================================
    
    def get_bank_names(self) -> List[str]:
        return ["中国建设银行", "建设银行", "建行", "CCB"]
    
    def get_summary_schema(self) -> Dict[str, Any]:
        return {
            "本方户名": "",
            "打印日期": ""
        }
    
    def get_transaction_schema(self) -> Dict[str, Any]:
        return [{
            "账号": "",
            "交易时间": "",
            "借方发生额": "",
            "贷方发生额": "",
            "余额": "",
            "币种": "",
            "对方户名": "",
            "对方账号": "",
            "对方开户机构": "",
            "记账日期": "",
            "摘要": "",
            "备注": "",
            "账户明细编号-交易流水号": "",
            "企业流水号": "",
            "凭证种类": "",
            "凭证号": "",
            "交易介质编号": ""
        }]
