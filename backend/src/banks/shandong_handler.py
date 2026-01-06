"""
山东地方银行处理器
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete

from src.banks.base import BankHandler, register_bank
from src.models.shandong_models import ShandongLocalSummary, ShandongLocalTransaction
from src.transactions.service import (
    create_shandong_transaction_records,
    create_shandong_summary_record,
)


@register_bank
class ShandongHandler(BankHandler):
    """山东地方银行处理器"""
    
    bank_type = "shandong_local"
    
    async def get_transactions(
        self, 
        session: AsyncSession, 
        file_id: int, 
        summary_id: int = None
    ) -> List[Dict[str, Any]]:
        statement = select(ShandongLocalTransaction).where(
            ShandongLocalTransaction.file_id == file_id
        )
        result = await session.execute(statement)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "sequence": r.sequence,
                "transaction_time": r.transaction_time,
                "channel": r.channel,
                "income": r.income,
                "expense": r.expense,
                "balance": r.balance,
                "currency": r.currency,
                "counterparty_account": r.counterparty_account,
                "counterparty_name": r.counterparty_name,
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
        statement = select(ShandongLocalSummary).where(
            ShandongLocalSummary.file_id == file_id
        )
        result = await session.execute(statement)
        summary = result.scalar_one_or_none()
        if summary:
            return {
                "account_name": summary.account_name,
                "account_number": summary.account_number,
                "date_range": summary.date_range,
                "income_count": summary.income_count,
                "income_total": summary.income_total,
                "expense_count": summary.expense_count,
                "expense_total": summary.expense_total,
                "has_stamp": summary.has_stamp,
                "bank_name": summary.bank_name,
                "stamp_type": summary.stamp_type,
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
        summary_stmt = select(ShandongLocalSummary).where(
            ShandongLocalSummary.file_id == file_id
        )
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["账户名称", summary.account_name])
            ws.append(["账(卡)号", summary.account_number])
            ws.append(["开户行", summary.bank_name])
            ws.append(["起止日期", summary.date_range])
            ws.append(["收入笔数", summary.income_count])
            ws.append(["收入总额", summary.income_total])
            ws.append(["支出笔数", summary.expense_count])
            ws.append(["支出总额", summary.expense_total])
            ws.append([])
        
        # 交易明细
        headers = ["序号", "交易时间", "交易渠道", "收入", "支出", "账户余额", "币种", "对方账号", "对方户名", "摘要备注"]
        ws.append(headers)
        tx_stmt = select(ShandongLocalTransaction).where(
            ShandongLocalTransaction.file_id == file_id
        )
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([
                tx.sequence, tx.transaction_time, tx.channel, 
                tx.income, tx.expense, tx.balance, tx.currency,
                tx.counterparty_account, tx.counterparty_name, tx.description
            ])
    
    def create_records(
        self, 
        file_id: int, 
        transactions_data: List[Dict], 
        summary_data: Dict
    ) -> tuple:
        transactions = create_shandong_transaction_records(file_id, transactions_data)
        summary = create_shandong_summary_record(file_id, summary_data)
        return transactions, summary
    
    async def delete_records(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> None:
        await session.execute(
            delete(ShandongLocalTransaction).where(
                ShandongLocalTransaction.file_id == file_id
            )
        )
        await session.execute(
            delete(ShandongLocalSummary).where(
                ShandongLocalSummary.file_id == file_id
            )
        )
    
    # ============================================================
    # 识别配置相关方法
    # ============================================================
    
    def get_bank_names(self) -> List[str]:
        return ["潍坊银行", "莱商银行", "齐鲁银行"]
    
    def get_summary_schema(self) -> Dict[str, Any]:
        return {
            "账户名称": "",
            "账(卡)号": "",
            "起止日期": "",
            "收入总笔数": "",
            "收入总金额": "",
            "支出总笔数": "",
            "支出总金额": "",
            "开户行": "",
            "盖章类型": ""
        }
    
    def get_transaction_schema(self) -> Dict[str, Any]:
        return [{
            "序号": "",
            "交易时间": "",
            "交易渠道": "",
            "收入": "",
            "支出": "",
            "账户余额": "",
            "币种": "",
            "对方账号": "",
            "对方户名": "",
            "摘要备注": ""
        }]
    
    def get_vertical_line_config(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "lines": [
                {"x_position": 1175, "description": "摘要备注"}
            ]
        }
