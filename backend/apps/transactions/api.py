from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
from io import BytesIO
from urllib.parse import quote
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from openpyxl import Workbook

from core.database import get_session
from apps.files.models import FileRecord
from apps.transactions.models import (
    # 山东地方银行
    ShandongLocalSummary, ShandongLocalTransaction,
    # 光大银行
    EverbrightSummary, EverbrightTransaction,
    # 招商银行
    CmbSummary, CmbTransaction,
    # 向后兼容别名
    SummaryRecord, TransactionRecord
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


# ============================================================
# 山东地方银行（潍坊、莱商、齐鲁）记录创建
# ============================================================

def create_shandong_transaction_records(file_id: int, raw_transactions: list) -> List[ShandongLocalTransaction]:
    """将原始交易数据转换为山东地方银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = ShandongLocalTransaction(
            file_id=file_id,
            sequence=str(item.get("序号", idx + 1)),
            transaction_time=item.get("交易时间", ""),
            channel=item.get("交易渠道", ""),
            income=item.get("收入", ""),
            expense=item.get("支出", ""),
            balance=item.get("账户余额", ""),
            currency=item.get("币种", ""),
            counterparty_account=item.get("对方账号", ""),
            counterparty_name=item.get("对方户名", ""),
            description=item.get("摘要备注", "")
        )
        records.append(t)
    return records


def create_shandong_summary_record(file_id: int, summary_data: dict) -> Optional[ShandongLocalSummary]:
    """创建山东地方银行汇总记录"""
    if not summary_data:
        return None
    return ShandongLocalSummary(
        file_id=file_id,
        account_name=summary_data.get("账户名称", ""),
        account_number=summary_data.get("账(卡)号", ""),
        date_range=summary_data.get("起止日期", ""),
        income_count=summary_data.get("收入总笔数", ""),
        income_total=summary_data.get("收入总金额", ""),
        expense_count=summary_data.get("支出总笔数", ""),
        expense_total=summary_data.get("支出总金额", ""),
        has_stamp=summary_data.get("是否有盖章", ""),
        bank_name=summary_data.get("开户行", ""),
        stamp_type=summary_data.get("盖章类型", "")
    )


# ============================================================
# 光大银行记录创建
# ============================================================

def create_everbright_transaction_records(file_id: int, raw_transactions: list) -> List[EverbrightTransaction]:
    """将原始交易数据转换为光大银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = EverbrightTransaction(
            file_id=file_id,
            sequence=str(item.get("序号", idx + 1)),
            transaction_date=item.get("交易日期", ""),
            transaction_time=item.get("时间", ""),
            debit_credit=item.get("借/贷", ""),
            amount=item.get("交易金额", ""),
            balance=item.get("账户余额", ""),
            counterparty_account=item.get("对方账号", ""),
            counterparty_name=item.get("对方名称", ""),
            voucher_no=item.get("凭证号", ""),
            description=item.get("摘要", ""),
            serial_no=item.get("流水号", "")
        )
        records.append(t)
    return records


def create_everbright_summary_record(file_id: int, summary_data: dict) -> Optional[EverbrightSummary]:
    """创建光大银行汇总记录"""
    if not summary_data:
        return None
    return EverbrightSummary(
        file_id=file_id,
        account_name=summary_data.get("账户名称", ""),
        account_number=summary_data.get("账号", ""),
        date_range=summary_data.get("交易日期", ""),
        debit_amount=summary_data.get("借方发生额", ""),
        credit_amount=summary_data.get("贷方发生额", ""),
        debit_count=summary_data.get("借方笔数", ""),
        credit_count=summary_data.get("贷方笔数", "")
    )


# ============================================================
# 招商银行记录创建
# ============================================================

def create_cmb_transaction_records(file_id: int, raw_transactions: list) -> List[CmbTransaction]:
    """将原始交易数据转换为招商银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = CmbTransaction(
            file_id=file_id,
            serial_no=item.get("交易流水号", ""),
            transaction_date=item.get("交易日期", ""),
            debit_amount=item.get("借方(出账)", ""),
            credit_amount=item.get("贷方(入账)", ""),
            balance=item.get("余额", ""),
            counterparty_name=item.get("收(付)方名称", ""),
            counterparty_account=item.get("收(付)方账号", ""),
            description=item.get("摘要", ""),
            transaction_type=item.get("交易类型", ""),
            card_no=item.get("公司一卡通号", ""),
            print_instance_no=item.get("打印实例号", "")
        )
        records.append(t)
    return records


def create_cmb_summary_record(file_id: int, summary_data: dict) -> Optional[CmbSummary]:
    """创建招商银行汇总记录"""
    if not summary_data:
        return None
    return CmbSummary(
        file_id=file_id,
        account_number=summary_data.get("账号", ""),
        account_name=summary_data.get("账号名", ""),
        start_date=summary_data.get("开始日期", ""),
        end_date=summary_data.get("结束日期", ""),
        debit_count=summary_data.get("出账总笔数", ""),
        credit_count=summary_data.get("入账总笔数", ""),
        debit_total=summary_data.get("出账总金额", ""),
        credit_total=summary_data.get("入账总金额", ""),
        total_count=summary_data.get("笔数", "")
    )


# 向后兼容的别名
create_transaction_records = create_shandong_transaction_records
create_summary_record = create_shandong_summary_record


# ============================================================
# API 端点
# ============================================================

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
                "time": r.transaction_time,
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


@router.get("/{file_id}/export")
async def export_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """导出文件交易数据为 Excel"""
    # 获取文件信息
    file_stmt = select(FileRecord).where(FileRecord.id == file_id)
    file_result = await session.execute(file_stmt)
    file_record = file_result.scalar_one_or_none()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    # 获取交易记录
    tx_stmt = select(TransactionRecord).where(TransactionRecord.file_id == file_id)
    tx_result = await session.execute(tx_stmt)
    transactions = tx_result.scalars().all()
    
    # 获取汇总记录
    summary_stmt = select(SummaryRecord).where(SummaryRecord.file_id == file_id)
    summary_result = await session.execute(summary_stmt)
    summary = summary_result.scalar_one_or_none()
    
    # 创建 Excel 工作簿
    wb = Workbook()
    ws = wb.active
    ws.title = "交易明细"
    
    # 添加汇总信息
    if summary:
        ws.append(["账户名称", summary.account_name])
        ws.append(["账(卡)号", summary.account_number])
        ws.append(["开户行", summary.bank_name])
        ws.append(["起止日期", summary.date_range])
        ws.append(["收入笔数", summary.income_count])
        ws.append(["收入总额", summary.income_total])
        ws.append(["支出笔数", summary.expense_count])
        ws.append(["支出总额", summary.expense_total])
        ws.append([])  # 空行
    
    # 添加交易明细表头
    headers = ["序号", "交易时间", "交易渠道", "收入", "支出", "账户余额", "币种", "对方账号", "对方户名", "摘要备注"]
    ws.append(headers)
    
    # 添加交易数据
    for tx in transactions:
        ws.append([
            tx.sequence,
            tx.transaction_time,
            tx.channel,
            tx.income,
            tx.expense,
            tx.balance,
            tx.currency,
            tx.counterparty_account,
            tx.counterparty_name,
            tx.description
        ])
    
    # 保存到内存
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    # 生成文件名 (使用 URL 编码支持中文)
    filename = os.path.splitext(file_record.filename)[0] + ".xlsx"
    encoded_filename = quote(filename)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    )
