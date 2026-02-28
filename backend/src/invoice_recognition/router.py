from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, desc
import os
import aiofiles
from datetime import datetime
from typing import List

from src.database import get_session
from src.invoice_recognition.models import (
    InvoiceFile, 
    InvoiceResult,
    InvoiceRecognitionResponse,
    InvoiceRecognitionResult
)
from src.invoice_recognition.service import process_invoice_recognitions

router = APIRouter(prefix="/invoice_recognition", tags=["Invoice Recognition"])

# 上传目录
UPLOAD_DIR = os.path.join(os.getcwd(), "downloads", "invoice_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=InvoiceRecognitionResponse)
async def upload_invoice_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session)
):
    """
    上传新的发票 PDF 进行识别。返回数据库中新建任务的文件信息。
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件。")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_filename = file.filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
    unique_filename = f"{timestamp}_{safe_filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # 1. 异步保存文件
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    # 2. 插入 InvoiceFile
    db_file = InvoiceFile(
        filename=file.filename,
        file_path=file_path,
        status="pending"
    )
    db.add(db_file)
    await db.commit()
    await db.refresh(db_file)

    # 3. 提交后台任务处理识别
    background_tasks.add_task(process_invoice_recognitions, db, db_file)

    return InvoiceRecognitionResponse(
        file_id=db_file.id,
        filename=db_file.filename,
        status=db_file.status,
        results=[]
    )

@router.get("/list/{file_id}", response_model=InvoiceRecognitionResponse)
async def get_invoice_result(
    file_id: int,
    db: AsyncSession = Depends(get_session)
):
    """
    获取单个发票 PDF 的识别结果和状态。
    """
    db_file = await db.get(InvoiceFile, file_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    statement = select(InvoiceResult).where(InvoiceResult.file_id == file_id).order_by(InvoiceResult.page_number)
    results = (await db.execute(statement)).scalars().all()

    page_results = [
        InvoiceRecognitionResult(
            page_number=r.page_number,
            invoice_type=r.invoice_type,
            invoice_amount=r.invoice_amount,
            raw_text=r.raw_text
        ) for r in results
    ]

    return InvoiceRecognitionResponse(
        file_id=db_file.id,
        filename=db_file.filename,
        status=db_file.status,
        error_msg=db_file.error_msg,
        results=page_results
    )
