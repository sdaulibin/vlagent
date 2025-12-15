from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List, Optional
import shutil
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc

from core.database import get_session
from apps.files.models import FileRecord, TransactionRecord, SummaryRecord
from services import pdf_processor

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = "/Users/binginx/PycharmProjects/vl_flow/backend/res"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def create_transaction_records(file_id: int, raw_transactions: list) -> List[TransactionRecord]:
    """将原始交易数据转换为 TransactionRecord 对象列表"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = TransactionRecord(
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


def create_summary_record(file_id: int, summary_data: dict) -> Optional[SummaryRecord]:
    """将汇总数据转换为 SummaryRecord 对象"""
    if not summary_data:
        return None
    return SummaryRecord(
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
    """上传并处理PDF文件"""
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)

        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 创建文件记录
        db_file = FileRecord(filename=file.filename, file_path=file_path, status="processing")
        session.add(db_file)
        await session.commit()
        await session.refresh(db_file)

        try:
            # 提取文件内容
            result = pdf_processor.process_pdf_to_excel(file_path, max_workers=4)
            
            # 创建交易记录
            transactions = create_transaction_records(db_file.id, result.get("transactions", []))
            session.add_all(transactions)
            
            # 创建汇总记录
            summary = create_summary_record(db_file.id, result.get("summary"))
            if summary:
                session.add(summary)
            
            # 更新文件状态
            db_file.status = "done"
            await session.commit()
            
            return {
                "status": "success",
                "filename": file.filename,
                "file_id": db_file.id,
                "transactions": transactions,
                "summary": summary
            }

        except Exception as e_process:
            db_file.status = "failed"
            db_file.error_msg = str(e_process)
            await session.commit()
            raise e_process

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
        
        # 删除交易记录
        from sqlmodel import delete
        await session.execute(
            delete(TransactionRecord).where(TransactionRecord.file_id == file_id)
        )
        
        # 删除汇总记录
        await session.execute(
            delete(SummaryRecord).where(SummaryRecord.file_id == file_id)
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



