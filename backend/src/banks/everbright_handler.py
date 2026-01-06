"""
光大银行处理器
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete

from src.banks.base import BankHandler, register_bank
from src.models.everbright_models import EverbrightSummary, EverbrightTransaction
from src.transactions.service import (
    create_everbright_transaction_records,
    create_everbright_summary_record,
)


@register_bank
class EverbrightHandler(BankHandler):
    """光大银行处理器"""
    
    bank_type = "everbright"
    
    async def get_transactions(
        self, 
        session: AsyncSession, 
        file_id: int, 
        summary_id: int = None
    ) -> List[Dict[str, Any]]:
        statement = select(EverbrightTransaction).where(
            EverbrightTransaction.file_id == file_id
        )
        result = await session.execute(statement)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "sequence": r.sequence,
                "transaction_date": r.transaction_date,
                "time": r.transaction_time,
                "debit_credit": r.debit_credit,
                "amount": r.amount,
                "balance": r.balance,
                "counterparty_account": r.counterparty_account,
                "counterparty_name": r.counterparty_name,
                "voucher_no": r.voucher_no,
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
        statement = select(EverbrightSummary).where(
            EverbrightSummary.file_id == file_id
        )
        result = await session.execute(statement)
        summary = result.scalar_one_or_none()
        if summary:
            return {
                "account_name": summary.account_name,
                "account_number": summary.account_number,
                "date_range": summary.date_range,
                "debit_amount": summary.debit_amount,
                "credit_amount": summary.credit_amount,
                "debit_count": summary.debit_count,
                "credit_count": summary.credit_count,
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
        summary_stmt = select(EverbrightSummary).where(
            EverbrightSummary.file_id == file_id
        )
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["账户名称", summary.account_name])
            ws.append(["账号", summary.account_number])
            ws.append(["交易日期", summary.date_range])
            ws.append(["借方发生额", summary.debit_amount])
            ws.append(["贷方发生额", summary.credit_amount])
            ws.append(["借方笔数", summary.debit_count])
            ws.append(["贷方笔数", summary.credit_count])
            ws.append([])
        
        # 交易明细
        headers = ["序号", "交易日期", "时间", "借/贷", "交易金额", "账户余额", "对方账号", "对方名称", "凭证号", "摘要", "流水号"]
        ws.append(headers)
        tx_stmt = select(EverbrightTransaction).where(
            EverbrightTransaction.file_id == file_id
        )
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([
                tx.sequence, tx.transaction_date, tx.transaction_time, 
                tx.debit_credit, tx.amount, tx.balance,
                tx.counterparty_account, tx.counterparty_name, 
                tx.voucher_no, tx.description, tx.serial_no
            ])
    
    def create_records(
        self, 
        file_id: int, 
        transactions_data: List[Dict], 
        summary_data: Dict
    ) -> tuple:
        transactions = create_everbright_transaction_records(file_id, transactions_data)
        summary = create_everbright_summary_record(file_id, summary_data)
        return transactions, summary
    
    async def delete_records(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> None:
        await session.execute(
            delete(EverbrightTransaction).where(
                EverbrightTransaction.file_id == file_id
            )
        )
        await session.execute(
            delete(EverbrightSummary).where(
                EverbrightSummary.file_id == file_id
            )
        )
    
    # ============================================================
    # 识别配置相关方法
    # ============================================================
    
    def get_bank_names(self) -> List[str]:
        return ["光大银行", "中国光大银行"]
    
    def get_summary_schema(self) -> Dict[str, Any]:
        return {
            "账户名称": "",
            "账号": "",
            "交易日期": "",
            "借方发生额": "",
            "贷方发生额": "",
            "借方笔数": "",
            "贷方笔数": ""
        }
    
    def get_transaction_schema(self) -> Dict[str, Any]:
        return [{
            "序号": "",
            "交易日期": "",
            "时间": "",
            "借/贷": "",
            "交易金额": "",
            "账户余额": "",
            "对方账号": "",
            "对方名称": "",
            "凭证号": "",
            "摘要": "",
            "流水号": ""
        }]
    
    def get_vertical_line_config(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "lines": [
                {"x_position": 750, "description": "对方账号"},
                {"x_position": 880, "description": "对方名称"},
                {"x_position": 1000, "description": "凭证号"},
                {"x_position": 1130, "description": "摘要"},
                {"x_position": 1300, "description": "流水号"}
            ]
        }
