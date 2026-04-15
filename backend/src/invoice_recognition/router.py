from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, desc
from sqlalchemy import delete
import os
from datetime import datetime
from typing import List

from src.database import get_session
from src.invoice_recognition.models import (
    InvoiceFile, 
    InvoiceResult,
    InvoiceFileListItem,
    InvoiceRecognitionResponse,
    InvoiceRecognitionResult
)
from src.invoice_recognition.service import process_invoice_recognitions

router = APIRouter(prefix="/invoice_recognition", tags=["Invoice Recognition"])

# 上传目录
UPLOAD_DIR = os.getenv("INVOICE_UPLOAD_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "upload", "invoice"))
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
    allowed_extensions = ('.pdf', '.jpg', '.jpeg', '.png')
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail="仅支持 PDF、JPG、PNG 文件。")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_filename = file.filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
    unique_filename = f"{timestamp}_{safe_filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # 1. 保存文件
    content = await file.read()
    with open(file_path, 'wb') as out_file:
        out_file.write(content)

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


@router.post("/list", response_model=List[InvoiceFileListItem])
async def list_invoice_files(
    db: AsyncSession = Depends(get_session)
):
    """
    获取所有发票文件列表（按创建时间倒序）。
    """
    statement = select(InvoiceFile).order_by(desc(InvoiceFile.created_at))
    results = (await db.execute(statement)).scalars().all()
    return [
        InvoiceFileListItem(
            id=f.id,
            filename=f.filename,
            status=f.status,
            page_count=f.page_count,
            recognition_duration=f.recognition_duration,
            error_msg=f.error_msg,
            created_at=f.created_at
        )
        for f in results
    ]


@router.post("/list/{file_id}", response_model=InvoiceRecognitionResponse)
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
            invoice_no=r.invoice_no,
            invoice_date=r.invoice_date,
            invoice_amount=r.invoice_amount,
            buyer_name=r.buyer_name,
            buyer_tax_id=r.buyer_tax_id,
            seller_name=r.seller_name,
            seller_tax_id=r.seller_tax_id,
            raw_text=r.raw_text,
            error_msg=r.error_msg
        ) for r in results
    ]

    return InvoiceRecognitionResponse(
        file_id=db_file.id,
        filename=db_file.filename,
        status=db_file.status,
        page_count=db_file.page_count,
        recognition_duration=db_file.recognition_duration,
        error_msg=db_file.error_msg,
        results=page_results
    )


@router.post("/{file_id}/file")
async def get_invoice_file(
    file_id: int,
    db: AsyncSession = Depends(get_session)
):
    """获取发票原始文件"""
    db_file = await db.get(InvoiceFile, file_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    if not db_file.file_path or not os.path.exists(db_file.file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    media_type = "application/pdf"
    if db_file.filename.lower().endswith(('.jpg', '.jpeg')):
        media_type = "image/jpeg"
    elif db_file.filename.lower().endswith('.png'):
        media_type = "image/png"

    return FileResponse(db_file.file_path, media_type=media_type, filename=db_file.filename)


@router.delete("/{file_id}")
async def delete_invoice_file(
    file_id: int,
    db: AsyncSession = Depends(get_session)
):
    """
    删除发票文件及其所有识别结果。
    """
    db_file = await db.get(InvoiceFile, file_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    # 先删除关联的识别结果（外键约束）
    await db.execute(
        delete(InvoiceResult).where(InvoiceResult.file_id == file_id)
    )

    # 删除磁盘上的文件
    if db_file.file_path and os.path.exists(db_file.file_path):
        os.remove(db_file.file_path)

    # 删除数据库记录
    await db.delete(db_file)
    await db.commit()

    return {"detail": "已删除", "file_id": file_id}
