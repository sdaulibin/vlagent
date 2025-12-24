from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List
import shutil
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc

from src.database import get_session
from src.files.models import FileRecord
from src.transactions.models import (
    # 山东地方银行
    ShandongLocalSummary, ShandongLocalTransaction,
    # 光大银行
    EverbrightSummary, EverbrightTransaction,
    # 招商银行
    CmbSummary, CmbTransaction,
)
from src.transactions.service import (
    create_shandong_transaction_records,
    create_shandong_summary_record,
    create_everbright_transaction_records,
    create_everbright_summary_record,
    create_cmb_transaction_records,
    create_cmb_summary_record,
)
from services import pdf_processor

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = "/Users/binginx/PycharmProjects/vl_flow/backend/res"
os.makedirs(UPLOAD_DIR, exist_ok=True)


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

        import time
        import asyncio
        from src.config import RECOGNITION_TIMEOUT
        start_time = time.time()
        
        try:
            # 提取文件内容（包含银行类型识别）
            # 使用 run_in_threadpool 避免阻塞主事件循环
            from fastapi.concurrency import run_in_threadpool
            
            # 使用 asyncio.wait_for 增加超时控制
            try:
                result = await asyncio.wait_for(
                    run_in_threadpool(pdf_processor.process_pdf_to_excel, db_file.file_path, max_workers=4),
                    timeout=RECOGNITION_TIMEOUT
                )
            except asyncio.TimeoutError:
                # 超时处理
                end_time = time.time()
                db_file.status = "error"
                db_file.error_msg = f"识别超时（超过 {RECOGNITION_TIMEOUT} 秒），任务已自动停止"
                db_file.recognition_duration = round((end_time - start_time) * 1000, 2)
                await session.commit()
                return {
                    "status": "error",
                    "message": db_file.error_msg,
                    "recognition_duration_ms": db_file.recognition_duration
                }
            
            # 获取银行类型
            bank_type = result.get("bank_type", "shandong_local")
            db_file.bank_type = bank_type
            
            # 记录原始数据量
            raw_transactions = result.get("transactions", [])
            
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
            
            session.add_all(transactions)
            if summary:
                session.add(summary)
            
            # 计算并保存识别耗时（毫秒）
            end_time = time.time()
            db_file.recognition_duration = round((end_time - start_time) * 1000, 2)
            
            # 更新文件状态
            db_file.status = "done"
            await session.commit()
            
            return {
                "status": "success",
                "file_id": db_file.id,
                "bank_type": bank_type,
                "transactions_count": len(transactions),
                "has_summary": summary is not None,
                "recognition_duration_ms": db_file.recognition_duration
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


@router.get("/{file_id}/export")
async def export_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """导出文件交易数据为 Excel"""
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    from urllib.parse import quote
    from openpyxl import Workbook
    
    # 获取文件信息
    file_stmt = select(FileRecord).where(FileRecord.id == file_id)
    file_result = await session.execute(file_stmt)
    file_record = file_result.scalar_one_or_none()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    bank_type = file_record.bank_type or "shandong_local"
    
    # 根据银行类型获取交易记录
    if bank_type == "everbright":
        tx_stmt = select(EverbrightTransaction).where(EverbrightTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        transactions = tx_result.scalars().all()
        headers = ["序号", "交易日期", "时间", "借/贷", "交易金额", "账户余额", "对方账号", "对方名称", "凭证号", "摘要", "流水号"]
        def row_data(tx):
            return [tx.sequence, tx.transaction_date, tx.transaction_time, tx.debit_credit, tx.amount, tx.balance, tx.counterparty_account, tx.counterparty_name, tx.voucher_no, tx.description, tx.serial_no]
    elif bank_type == "cmb":
        tx_stmt = select(CmbTransaction).where(CmbTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        transactions = tx_result.scalars().all()
        headers = ["交易流水号", "交易日期", "借方出账", "贷方入账", "余额", "收付方名称", "收付方账号", "摘要", "交易类型", "公司一卡通号", "打印实例号"]
        def row_data(tx):
            return [tx.serial_no, tx.transaction_date, tx.debit_amount, tx.credit_amount, tx.balance, tx.counterparty_name, tx.counterparty_account, tx.description, tx.transaction_type, tx.card_no, tx.print_instance_no]
    else:
        tx_stmt = select(ShandongLocalTransaction).where(ShandongLocalTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        transactions = tx_result.scalars().all()
        headers = ["序号", "交易时间", "交易渠道", "收入", "支出", "账户余额", "币种", "对方账号", "对方户名", "摘要备注"]
        def row_data(tx):
            return [tx.sequence, tx.transaction_time, tx.channel, tx.income, tx.expense, tx.balance, tx.currency, tx.counterparty_account, tx.counterparty_name, tx.description]
    
    # 创建 Excel 工作簿
    wb = Workbook()
    ws = wb.active
    ws.title = "交易明细"
    
    # 添加表头
    ws.append(headers)
    
    # 添加交易数据
    for tx in transactions:
        ws.append(row_data(tx))
    
    # 保存到内存
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    # 生成文件名
    filename = os.path.splitext(file_record.filename)[0] + ".xlsx"
    encoded_filename = quote(filename)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    )
