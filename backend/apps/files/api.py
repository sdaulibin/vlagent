from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List, Optional
import shutil
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc

from core.database import get_session
from apps.files.models import (
    FileRecord, 
    # 山东地方银行
    ShandongLocalSummary, ShandongLocalTransaction,
    # 光大银行
    EverbrightSummary, EverbrightTransaction,
    # 招商银行
    CmbSummary, CmbTransaction,
    # 向后兼容别名
    SummaryRecord, TransactionRecord
)
from services import pdf_processor

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = "/Users/binginx/PycharmProjects/vl_flow/backend/res"
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
            debit_amount=item.get("借方出账", ""),
            credit_amount=item.get("贷方入账", ""),
            balance=item.get("余额", ""),
            counterparty_name=item.get("收付方名称", ""),
            counterparty_account=item.get("收付方账号", ""),
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




@router.get("", response_model=List[FileRecord])
async def get_files(session: AsyncSession = Depends(get_session)):
    """获取所有文件列表"""
    statement = select(FileRecord).order_by(desc(FileRecord.created_at))
    result = await session.execute(statement)
    return result.scalars().all()


@router.get("/{file_id}", response_model=FileRecord)
async def get_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """获取单个文件详情"""
    statement = select(FileRecord).where(FileRecord.id == file_id)
    result = await session.execute(statement)
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file


@router.get("/{file_id}/export")
async def export_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """导出文件交易数据为 Excel"""
    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook
    from io import BytesIO
    
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
    from urllib.parse import quote
    filename = os.path.splitext(file_record.filename)[0] + ".xlsx"
    encoded_filename = quote(filename)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    )


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    """上传文件（仅保存，不处理）"""
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)

        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 创建文件记录 - 状态为 pending（待处理）
        db_file = FileRecord(filename=file.filename, file_path=file_path, status="pending")
        session.add(db_file)
        await session.commit()
        await session.refresh(db_file)

        return {
            "status": "success",
            "filename": file.filename,
            "file_id": db_file.id,
            "message": "文件上传成功，请点击开始识别"
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{file_id}/recognize")
async def start_recognition(file_id: int, session: AsyncSession = Depends(get_session)):
    """开始识别文件内容"""
    try:
        # 获取文件记录
        result = await session.execute(select(FileRecord).where(FileRecord.id == file_id))
        db_file = result.scalar_one_or_none()
        
        if not db_file:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        if db_file.status == "done":
            return {"status": "already_done", "message": "文件已识别完成"}
        
        if db_file.status == "processing":
            return {"status": "processing", "message": "文件正在识别中"}
        
        # 更新状态为处理中
        db_file.status = "processing"
        await session.commit()

        try:
            # 提取文件内容（包含银行类型识别）
            result = pdf_processor.process_pdf_to_excel(db_file.file_path, max_workers=4)
            
            # 获取银行类型
            bank_type = result.get("bank_type", "shandong_local")
            db_file.bank_type = bank_type
            
            # 记录原始数据量
            raw_transactions = result.get("transactions", [])
            print(f"[识别结果] 银行类型: {bank_type}, 原始交易数据: {len(raw_transactions)} 条")
            
            # 根据银行类型创建对应的记录
            transactions = []
            summary = None
            
            if bank_type == "everbright":
                # 光大银行
                transactions = create_everbright_transaction_records(db_file.id, raw_transactions)
                summary = create_everbright_summary_record(db_file.id, result.get("summary"))
            elif bank_type == "cmb":
                # 招商银行
                transactions = create_cmb_transaction_records(db_file.id, raw_transactions)
                summary = create_cmb_summary_record(db_file.id, result.get("summary"))
            else:
                # 山东地方银行（默认）
                transactions = create_shandong_transaction_records(db_file.id, raw_transactions)
                summary = create_shandong_summary_record(db_file.id, result.get("summary"))
            
            print(f"[创建记录] 创建交易记录: {len(transactions)} 条")
            if len(transactions) != len(raw_transactions):
                print(f"[警告] 数据丢失! 原始: {len(raw_transactions)}, 创建: {len(transactions)}, 丢失: {len(raw_transactions) - len(transactions)}")
            
            session.add_all(transactions)
            if summary:
                session.add(summary)
            
            # 更新文件状态
            db_file.status = "done"
            await session.commit()
            
            return {
                "status": "success",
                "file_id": db_file.id,
                "bank_type": bank_type,
                "transactions_count": len(transactions),
                "has_summary": summary is not None
            }

        except Exception as e_process:
            db_file.status = "failed"
            db_file.error_msg = str(e_process)
            await session.commit()
            raise e_process

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{file_id}")
async def delete_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """删除文件及其关联的所有数据"""
    try:
        # 查询文件记录
        statement = select(FileRecord).where(FileRecord.id == file_id)
        result = await session.execute(statement)
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        
        from sqlmodel import delete
        
        # 删除山东地方银行记录
        await session.execute(
            delete(ShandongLocalTransaction).where(ShandongLocalTransaction.file_id == file_id)
        )
        await session.execute(
            delete(ShandongLocalSummary).where(ShandongLocalSummary.file_id == file_id)
        )
        
        # 删除光大银行记录
        await session.execute(
            delete(EverbrightTransaction).where(EverbrightTransaction.file_id == file_id)
        )
        await session.execute(
            delete(EverbrightSummary).where(EverbrightSummary.file_id == file_id)
        )
        
        # 删除招商银行记录
        await session.execute(
            delete(CmbTransaction).where(CmbTransaction.file_id == file_id)
        )
        await session.execute(
            delete(CmbSummary).where(CmbSummary.file_id == file_id)
        )
        
        # 删除上传的原文件
        if file_record.file_path and os.path.exists(file_record.file_path):
            os.remove(file_record.file_path)
        
        # 删除处理过程中生成的目录 (res/文件名_task_*)
        filename_base = os.path.splitext(file_record.filename)[0]
        for item in os.listdir(UPLOAD_DIR):
            item_path = os.path.join(UPLOAD_DIR, item)
            if os.path.isdir(item_path) and item.startswith(f"task_{filename_base}"):
                shutil.rmtree(item_path)
        
        # 删除文件记录
        await session.delete(file_record)
        await session.commit()
        
        return {"status": "success", "message": f"File {file_id} deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



