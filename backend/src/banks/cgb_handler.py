"""
广发银行处理器（支持多汇总场景）
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_
from sqlmodel import select, delete

from src.banks.base import BankHandler, register_bank
from src.transactions.models import CgbSummary, CgbTransaction
from src.transactions.service import (
    create_cgb_transaction_records,
    create_cgb_summary_record,
)


@register_bank
class CgbHandler(BankHandler):
    """广发银行处理器（支持多汇总场景）"""
    
    bank_type = "cgb"
    
    async def get_transactions(
        self, 
        session: AsyncSession, 
        file_id: int, 
        summary_id: int = None
    ) -> List[Dict[str, Any]]:
        # 广发银行：支持按 summary_id 过滤
        if summary_id:
            statement = select(CgbTransaction).where(
                CgbTransaction.file_id == file_id,
                CgbTransaction.summary_id == summary_id
            )
        else:
            statement = select(CgbTransaction).where(CgbTransaction.file_id == file_id)
        result = await session.execute(statement)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "summary_id": r.summary_id,
                "serial_no": r.serial_no,
                "transaction_time": r.transaction_time,
                "income": r.income,
                "expense": r.expense,
                "balance": r.balance,
                "currency": r.currency,
                "counterparty_account": r.counterparty_account,
                "counterparty_name": r.counterparty_name,
                "transaction_branch": r.transaction_branch,
                "counterparty_bank_code": r.counterparty_bank_code,
                "counterparty_bank": r.counterparty_bank,
                "voucher_no": r.voucher_no,
                "description": r.description,
                "remark": r.remark,
                "postscript": r.postscript,
                "bank_type": self.bank_type
            }
            for r in records
        ]
    
    async def get_summary(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> Optional[List[Dict[str, Any]]]:
        # 广发银行：返回汇总列表（支持多汇总场景）
        statement = select(CgbSummary).where(CgbSummary.file_id == file_id)
        result = await session.execute(statement)
        summaries = result.scalars().all()
        if summaries:
            return [
                {
                    "id": summary.id,
                    "account_name": summary.account_name,
                    "account_number": summary.account_number,
                    "date_range": summary.date_range,
                    "currency": summary.currency,
                    "unit": summary.unit,
                    "expense_total": summary.expense_total,
                    "expense_count": summary.expense_count,
                    "income_total": summary.income_total,
                    "income_count": summary.income_count,
                    "current_balance": summary.current_balance,
                    "record_count": summary.record_count,
                    "bank_name": summary.bank_name,
                    "bank_type": self.bank_type
                }
                for summary in summaries
            ]
        return None
    
    async def export_to_excel(
        self, 
        session: AsyncSession, 
        file_id: int, 
        ws
    ) -> None:
        """广发银行导出需要特殊处理多 Sheet"""
        # 注意：这个方法的 ws 参数在广发银行场景下不使用
        # 因为需要创建多个 Sheet，所以在 files/router.py 中特殊处理
        pass
    
    async def export_to_workbook(
        self, 
        session: AsyncSession, 
        file_id: int, 
        wb
    ) -> None:
        """广发银行专用：导出到整个工作簿（支持多 Sheet）"""
        summary_stmt = select(CgbSummary).where(CgbSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summaries = summary_result.scalars().all()
        
        if summaries:
            for idx, summary in enumerate(summaries):
                # Sheet 名称使用起止日期或序号
                sheet_name = f"明细{idx+1}" if not summary.date_range else summary.date_range[:30]
                sheet = wb.create_sheet(title=sheet_name)
                
                # 汇总信息
                sheet.append(["户名", summary.account_name])
                sheet.append(["账号", summary.account_number])
                sheet.append(["起止日期", summary.date_range])
                sheet.append(["币种", summary.currency])
                sheet.append(["单位", summary.unit])
                sheet.append(["支出总金额", summary.expense_total])
                sheet.append(["支出总笔数", summary.expense_count])
                sheet.append(["收入总金额", summary.income_total])
                sheet.append(["收入总笔数", summary.income_count])
                sheet.append(["账户当前余额", summary.current_balance])
                sheet.append(["记录数", summary.record_count])
                sheet.append([])
                
                # 交易明细标题
                headers = ["流水号", "交易时间", "收入", "支出", "余额", "币种", "对方账号", "对方户名", "交易行所", "对方开户行联行号", "对方开户行", "凭证号", "摘要", "备注", "附言"]
                sheet.append(headers)
                
                # 该汇总关联的交易明细
                tx_stmt = select(CgbTransaction).where(
                    or_(
                        CgbTransaction.summary_id == summary.id,
                        # 向后兼容：如果只有一个汇总且交易没有 summary_id
                        (CgbTransaction.file_id == file_id) & (CgbTransaction.summary_id == None)
                    ) if len(summaries) == 1 else CgbTransaction.summary_id == summary.id
                )
                tx_result = await session.execute(tx_stmt)
                for tx in tx_result.scalars().all():
                    sheet.append([
                        tx.serial_no, tx.transaction_time, tx.income, tx.expense, 
                        tx.balance, tx.currency, tx.counterparty_account, 
                        tx.counterparty_name, tx.transaction_branch, 
                        tx.counterparty_bank_code, tx.counterparty_bank, 
                        tx.voucher_no, tx.description, tx.remark, tx.postscript
                    ])
    
    def create_records(
        self, 
        file_id: int, 
        transactions_data: List[Dict], 
        summary_data: Dict
    ) -> tuple:
        """广发银行的记录创建需要特殊处理多汇总场景，在 files/router.py 中单独实现"""
        transactions = create_cgb_transaction_records(file_id, transactions_data)
        summary = create_cgb_summary_record(file_id, summary_data)
        return transactions, summary
    
    async def delete_records(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> None:
        # 先删 transaction 因为有外键约束
        await session.execute(
            delete(CgbTransaction).where(CgbTransaction.file_id == file_id)
        )
        await session.execute(
            delete(CgbSummary).where(CgbSummary.file_id == file_id)
        )
    
    # ============================================================
    # 识别配置相关方法
    # ============================================================
    
    def get_bank_names(self) -> List[str]:
        return ["广发银行", "广发银行股份有限公司", "CGB"]
    
    def get_summary_schema(self) -> Dict[str, Any]:
        return {
            "户名": "",
            "账号": "",
            "起止日期": "",
            "币种": "",
            "单位": "",
            "支出总金额": "",
            "支出总笔数": "",
            "收入总金额": "",
            "收入总笔数": "",
            "账户当前余额": "",
            "记录数": ""
        }
    
    def get_transaction_schema(self) -> Dict[str, Any]:
        return {
            "流水号": "",
            "交易时间": "",
            "收入": "",
            "支出": "",
            "余额": "",
            "币种": "",
            "对方账号": "",
            "对方户名": "",
            "交易行所": "",
            "对方开户行联行号": "",
            "对方开户行": "",
            "凭证号": "",
            "摘要": "",
            "备注": "",
            "附言": ""
        }
