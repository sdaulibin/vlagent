"""
文件相关 API 路由

使用策略模式通过银行处理器动态分发请求。
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import List
from io import BytesIO
from urllib.parse import quote
from pathlib import Path
from uuid import uuid4
import shutil
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc
from openpyxl import Workbook

from src.database import get_session
from src.files.models import FileRecord
from src.banks import get_bank_handler, get_all_handlers
from src.banks.cgb_handler import CgbHandler
from src.transactions.service import (
    create_cgb_transaction_records,
    create_cgb_summary_record,
)
from services import pdf_processor

router = APIRouter(prefix="/files", tags=["files"])

# Load config from env
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/Users/binginx/PycharmProjects/vlagent/backend/res")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _build_safe_upload_path(upload_dir: str, original_filename: str) -> str:
    """Build a safe, unique path under upload_dir and prevent path traversal."""
    safe_name = Path((original_filename or "").strip()).name
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="文件名无效")

    stem, suffix = os.path.splitext(safe_name)
    unique_name = f"{stem}_{uuid4().hex}{suffix}"

    base_dir = Path(upload_dir).resolve()
    target_path = (base_dir / unique_name).resolve()
    if base_dir not in target_path.parents:
        raise HTTPException(status_code=400, detail="非法文件路径")
    return str(target_path)


@router.post("", response_model=List[FileRecord])
async def get_files(session: AsyncSession = Depends(get_session)):
    """获取所有文件列表"""
    statement = select(FileRecord).order_by(desc(FileRecord.created_at))
    result = await session.execute(statement)
    return result.scalars().all()


@router.post("/{file_id}", response_model=FileRecord)
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
        # 1. 验证文件格式（仅支持 PDF）
        from services.pdf.file_validator import validate_pdf_format
        
        # 读取文件头部用于验证
        file_header = await file.read(1024)
        await file.seek(0)  # 重置文件指针
        
        is_valid, error_msg = validate_pdf_format(file.filename, file_header)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        file_path = _build_safe_upload_path(UPLOAD_DIR, file.filename)

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

    except HTTPException:
        raise
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
        
        if db_file.status == "invalid":
            return {"status": "invalid", "message": f"文件验证未通过: {db_file.error_msg}"}
        
        # 2. 验证是否为银行流水文件
        from fastapi.concurrency import run_in_threadpool
        from services.pdf.file_validator import validate_bank_statement
        from services.pdf.pdf_utils import pdf_to_images
        
        # 转换第一页为图片进行验证
        images_dir = pdf_to_images(db_file.file_path, max_pages=1)
        image_files = sorted([f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        
        if image_files:
            first_page = os.path.join(images_dir, image_files[0])
            is_statement, reason, confidence = await run_in_threadpool(
                validate_bank_statement, first_page
            )
            
            if not is_statement and confidence >= 0.6:
                db_file.status = "invalid"
                db_file.error_msg = f"非银行流水文件: {reason}"
                await session.commit()
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "非银行流水文件",
                        "reason": reason,
                        "confidence": confidence
                    }
                )
        
        # 更新状态为处理中
        db_file.status = "processing"
        await session.commit()

        import time
        import asyncio
        from src.config import RECOGNITION_TIMEOUT
        start_time = time.time()
        
        try:
            # 提取文件内容（包含银行类型识别）
            from fastapi.concurrency import run_in_threadpool
            
            try:
                result = await asyncio.wait_for(
                    run_in_threadpool(pdf_processor.process_pdf_to_excel, db_file.file_path, max_workers=4),
                    timeout=RECOGNITION_TIMEOUT
                )
            except asyncio.TimeoutError:
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
            
            raw_transactions = result.get("transactions", [])
            summary_data = result.get("summary")
            
            # 获取银行处理器
            handler = get_bank_handler(bank_type)
            
            # 广发银行需要特殊处理多汇总场景
            if bank_type == "cgb" and isinstance(summary_data, list) and len(summary_data) > 1:
                transactions, _ = await _process_cgb_multi_summary(
                    session, db_file.id, raw_transactions, summary_data
                )
            elif handler:
                transactions, summary = handler.create_records(
                    db_file.id, raw_transactions, summary_data
                )
                session.add_all(transactions)
                if summary:
                    session.add(summary)
            else:
                # 不支持的银行类型，使用默认处理
                from src.transactions.service import (
                    create_shandong_transaction_records,
                    create_shandong_summary_record,
                )
                transactions = create_shandong_transaction_records(db_file.id, raw_transactions)
                summary = create_shandong_summary_record(db_file.id, summary_data)
                session.add_all(transactions)
                if summary:
                    session.add(summary)
            
            # 计算并保存识别耗时
            end_time = time.time()
            db_file.recognition_duration = round((end_time - start_time) * 1000, 2)
            
            # 更新文件状态
            db_file.status = "done"
            await session.commit()
            
            return {
                "status": "success",
                "file_id": db_file.id,
                "bank_type": bank_type,
                "transactions_count": len(transactions) if 'transactions' in dir() else 0,
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


async def _process_cgb_multi_summary(session, file_id, raw_transactions, summary_data):
    """处理广发银行多汇总场景"""
    summaries_info = []
    for s in summary_data:
        summary_obj = create_cgb_summary_record(file_id, s)
        if summary_obj:
            start_page = s.get("_start_page", 0)
            summaries_info.append((summary_obj, start_page))
    
    transactions = []
    if summaries_info:
        summaries_info.sort(key=lambda x: x[1])
        summary_objs = [info[0] for info in summaries_info]
        session.add_all(summary_objs)
        await session.flush()
        
        page_ranges = []
        for i, (summary_obj, start_page) in enumerate(summaries_info):
            if i + 1 < len(summaries_info):
                end_page = summaries_info[i + 1][1] - 1
            else:
                end_page = 99999
            page_ranges.append((start_page, end_page, summary_obj.id))
        
        for tx_data in raw_transactions:
            tx_page = tx_data.get("_page", 0)
            tx_summary_id = None
            for start_p, end_p, s_id in page_ranges:
                if start_p <= tx_page <= end_p:
                    tx_summary_id = s_id
                    break
            tx_list = create_cgb_transaction_records(file_id, [tx_data], summary_id=tx_summary_id)
            transactions.extend(tx_list)
    else:
        transactions = create_cgb_transaction_records(file_id, raw_transactions)
    
    session.add_all(transactions)
    return transactions, None


@router.delete("/{file_id}")
async def delete_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """删除文件及其关联的所有数据"""
    try:
        statement = select(FileRecord).where(FileRecord.id == file_id)
        result = await session.execute(statement)
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        
        # 使用所有处理器删除各自的记录
        for handler in get_all_handlers().values():
            await handler.delete_records(session, file_id)
        
        # 删除上传的原文件
        if file_record.file_path and os.path.exists(file_record.file_path):
            os.remove(file_record.file_path)
        
        # 删除处理过程中生成的目录
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


@router.post("/{file_id}/export")
async def export_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """导出文件交易数据为 Excel（包含汇总信息）"""
    # 获取文件信息
    file_stmt = select(FileRecord).where(FileRecord.id == file_id)
    file_result = await session.execute(file_stmt)
    file_record = file_result.scalar_one_or_none()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    bank_type = file_record.bank_type or "shandong_local"
    
    # 获取银行处理器
    handler = get_bank_handler(bank_type)
    if not handler:
        raise HTTPException(status_code=400, detail=f"Unsupported bank type: {bank_type}")
    
    # 创建 Excel 工作簿
    wb = Workbook()
    ws = wb.active
    ws.title = "交易明细"
    
    # 广发银行需要特殊处理多 Sheet
    if bank_type == "cgb" and isinstance(handler, CgbHandler):
        wb.remove(ws)  # 删除默认 sheet
        await handler.export_to_workbook(session, file_id, wb)
    else:
        await handler.export_to_excel(session, file_id, ws)
    
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
