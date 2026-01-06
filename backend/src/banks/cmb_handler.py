"""
招商银行处理器
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete

from src.banks.base import BankHandler, register_bank
from src.models.cmb_models import CmbSummary, CmbTransaction
from src.transactions.service import (
    create_cmb_transaction_records,
    create_cmb_summary_record,
)


@register_bank
class CmbHandler(BankHandler):
    """招商银行处理器"""
    
    bank_type = "cmb"
    
    async def get_transactions(
        self, 
        session: AsyncSession, 
        file_id: int, 
        summary_id: int = None
    ) -> List[Dict[str, Any]]:
        statement = select(CmbTransaction).where(CmbTransaction.file_id == file_id)
        result = await session.execute(statement)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "serial_no": r.serial_no,
                "transaction_date": r.transaction_date,
                "debit_amount": r.debit_amount,
                "credit_amount": r.credit_amount,
                "balance": r.balance,
                "counterparty_name": r.counterparty_name,
                "counterparty_account": r.counterparty_account,
                "description": r.description,
                "transaction_type": r.transaction_type,
                "card_no": r.card_no,
                "print_instance_no": r.print_instance_no,
                "bank_type": self.bank_type
            }
            for r in records
        ]
    
    async def get_summary(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> Optional[Dict[str, Any]]:
        statement = select(CmbSummary).where(CmbSummary.file_id == file_id)
        result = await session.execute(statement)
        summary = result.scalar_one_or_none()
        if summary:
            return {
                "account_name": summary.account_name,
                "account_number": summary.account_number,
                "start_date": summary.start_date,
                "end_date": summary.end_date,
                "debit_count": summary.debit_count,
                "credit_count": summary.credit_count,
                "debit_total": summary.debit_total,
                "credit_total": summary.credit_total,
                "total_count": summary.total_count,
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
        summary_stmt = select(CmbSummary).where(CmbSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["账号", summary.account_number])
            ws.append(["账号名", summary.account_name])
            ws.append(["开始日期", summary.start_date])
            ws.append(["结束日期", summary.end_date])
            ws.append(["出账总笔数", summary.debit_count])
            ws.append(["入账总笔数", summary.credit_count])
            ws.append(["出账总金额", summary.debit_total])
            ws.append(["入账总金额", summary.credit_total])
            ws.append([])
        
        # 交易明细
        headers = ["交易流水号", "交易日期", "借方出账", "贷方入账", "余额", "收付方名称", "收付方账号", "摘要", "交易类型", "公司一卡通号", "打印实例号"]
        ws.append(headers)
        tx_stmt = select(CmbTransaction).where(CmbTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([
                tx.serial_no, tx.transaction_date, tx.debit_amount, 
                tx.credit_amount, tx.balance, tx.counterparty_name,
                tx.counterparty_account, tx.description, tx.transaction_type, 
                tx.card_no, tx.print_instance_no
            ])
    
    def create_records(
        self, 
        file_id: int, 
        transactions_data: List[Dict], 
        summary_data: Dict
    ) -> tuple:
        transactions = create_cmb_transaction_records(file_id, transactions_data)
        summary = create_cmb_summary_record(file_id, summary_data)
        return transactions, summary
    
    async def delete_records(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> None:
        await session.execute(
            delete(CmbTransaction).where(CmbTransaction.file_id == file_id)
        )
        await session.execute(
            delete(CmbSummary).where(CmbSummary.file_id == file_id)
        )
    
    # ============================================================
    # 识别配置相关方法
    # ============================================================
    
    def get_bank_names(self) -> List[str]:
        return ["招商银行"]
    
    def get_summary_schema(self) -> Dict[str, Any]:
        return {
            "账号": "",
            "账号名": "",
            "开始日期": "",
            "结束日期": "",
            "出账总笔数": "",
            "入账总笔数": "",
            "出账总金额": "",
            "入账总金额": "",
            "笔数": ""
        }
    
    def get_transaction_schema(self) -> Dict[str, Any]:
        return [{
            "交易流水号": "",
            "交易日期": "",
            "借方(出账)": "",
            "贷方(入账)": "",
            "余额": "",
            "收(付)方名称": "",
            "收(付)方账号": "",
            "摘要": "",
            "交易类型": "",
            "公司一卡通号": "",
            "打印实例号": ""
        }]
    
    def get_vertical_line_config(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "lines": [
                {"x_position": 122, "description": "交易日期"},
                {"x_position": 190, "description": "借方(出账)"},
                {"x_position": 310, "description": "贷方(入账)"},
                {"x_position": 430, "description": "余额"},
                {"x_position": 553, "description": "收(付)方名称"},
                {"x_position": 774, "description": "收(付)方账号"},
                {"x_position": 872, "description": "摘要"},
                {"x_position": 1125, "description": "交易类型"},
                {"x_position": 1238, "description": "公司一卡通号"},
                {"x_position": 1290, "description": "打印实例号"}
            ]
        }
