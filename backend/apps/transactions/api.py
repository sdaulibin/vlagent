from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.database import get_session
from apps.files.models import (
    FileRecord,
    # 山东地方银行
    ShandongLocalSummary, ShandongLocalTransaction,
    # 光大银行
    EverbrightSummary, EverbrightTransaction,
    # 招商银行
    CmbSummary, CmbTransaction,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/{file_id}")
async def get_transactions(file_id: int, session: AsyncSession = Depends(get_session)) -> List[dict]:
    """获取指定文件的交易记录（根据银行类型从对应表查询）"""
    # 先获取文件记录以确定银行类型
    file_stmt = select(FileRecord).where(FileRecord.id == file_id)
    file_result = await session.execute(file_stmt)
    file_record = file_result.scalar_one_or_none()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    bank_type = file_record.bank_type or "shandong_local"
    
    # 根据银行类型查询对应的表
    if bank_type == "everbright":
        statement = select(EverbrightTransaction).where(EverbrightTransaction.file_id == file_id)
        result = await session.execute(statement)
        records = result.scalars().all()
        # 转换为统一格式
        return [
            {
                "id": r.id,
                "sequence": r.sequence,
                "transaction_date": r.transaction_date,
                "transaction_time": r.transaction_time,
                "debit_credit": r.debit_credit,
                "amount": r.amount,
                "balance": r.balance,
                "counterparty_account": r.counterparty_account,
                "counterparty_name": r.counterparty_name,
                "voucher_no": r.voucher_no,
                "description": r.description,
                "serial_no": r.serial_no,
                "bank_type": "everbright"
            }
            for r in records
        ]
    elif bank_type == "cmb":
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
                "bank_type": "cmb"
            }
            for r in records
        ]
    else:
        # 默认：山东地方银行
        statement = select(ShandongLocalTransaction).where(ShandongLocalTransaction.file_id == file_id)
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
                "bank_type": "shandong_local"
            }
            for r in records
        ]


@router.get("/{file_id}/summary")
async def get_summary(file_id: int, session: AsyncSession = Depends(get_session)) -> Optional[dict]:
    """获取文件的汇总信息（根据银行类型从对应表查询）"""
    # 先获取文件记录以确定银行类型
    file_stmt = select(FileRecord).where(FileRecord.id == file_id)
    file_result = await session.execute(file_stmt)
    file_record = file_result.scalar_one_or_none()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    bank_type = file_record.bank_type or "shandong_local"
    
    # 根据银行类型查询对应的表
    if bank_type == "everbright":
        statement = select(EverbrightSummary).where(EverbrightSummary.file_id == file_id)
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
                "bank_type": "everbright"
            }
    elif bank_type == "cmb":
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
                "bank_type": "cmb"
            }
    else:
        # 默认：山东地方银行
        statement = select(ShandongLocalSummary).where(ShandongLocalSummary.file_id == file_id)
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
                "bank_type": "shandong_local"
            }
    
    return None


