import os
import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, desc

from src.database import get_session
from src.pdf_extract.models import (
    PdfExtractTask,
    PdfExtractResult,
    PdfExtractTaskListItem,
    PdfExtractTaskResponse,
    OutputFormat,
)
from src.pdf_extract.service import process_pdf_extract
from src.pdf_extract.exporter import export_csv, export_xlsx

router = APIRouter(prefix="/pdf_extract", tags=["PDF Extract"])

UPLOAD_DIR = os.getenv("PDF_EXTRACT_UPLOAD_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "upload", "pdf_extract"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

DOWNLOAD_DIR = os.getenv("PDF_EXTRACT_DOWNLOAD_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "download", "pdf_extract"))
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=PdfExtractTaskResponse)
async def upload_pdf_extract(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    fields: str = Form(..., description="提取字段 JSON 数组"),
    output_format: str = Form("json", description="输出格式: json/csv/xlsx"),
    db: AsyncSession = Depends(get_session),
):
    """
    上传 PDF 文件和字段定义，启动提取任务。
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    # 解析字段
    try:
        fields_data = json.loads(fields)
        if not isinstance(fields_data, list) or len(fields_data) == 0:
            raise ValueError("fields 必须是非空数组")
        if len(fields_data) > 10:
            raise ValueError("提取字段最多10项")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"字段解析失败: {e}")

    # 保存文件
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_filename = file.filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
    unique_filename = f"{timestamp}_{safe_filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    content = await file.read()
    with open(file_path, 'wb') as out_file:
        out_file.write(content)

    # 创建任务
    task = PdfExtractTask(
        filename=file.filename,
        file_path=file_path,
        fields_json=fields,
        output_format=output_format,
        status="pending"
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 提交后台任务
    background_tasks.add_task(process_pdf_extract, db, task)

    return PdfExtractTaskResponse(
        id=task.id,
        filename=task.filename,
        status=task.status,
        output_format=task.output_format,
        fields=fields_data,
    )


@router.post("/list", response_model=List[PdfExtractTaskListItem])
async def list_pdf_extract_tasks(
    db: AsyncSession = Depends(get_session),
):
    """获取所有提取任务列表"""
    statement = select(PdfExtractTask).order_by(desc(PdfExtractTask.created_at))
    results = (await db.execute(statement)).scalars().all()
    return [
        PdfExtractTaskListItem(
            id=t.id,
            filename=t.filename,
            status=t.status,
            output_format=t.output_format,
            page_count=t.page_count,
            processing_duration=t.processing_duration,
            error_msg=t.error_msg,
            created_at=t.created_at,
        )
        for t in results
    ]


@router.post("/list/{task_id}", response_model=PdfExtractTaskResponse)
async def get_pdf_extract_task(
    task_id: int,
    db: AsyncSession = Depends(get_session),
):
    """获取单个任务的提取结果"""
    task = await db.get(PdfExtractTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    fields_data = json.loads(task.fields_json)
    result_data = None

    statement = select(PdfExtractResult).where(PdfExtractResult.task_id == task_id)
    db_result = (await db.execute(statement)).scalars().first()
    if db_result:
        result_data = json.loads(db_result.extracted_data)

    return PdfExtractTaskResponse(
        id=task.id,
        filename=task.filename,
        status=task.status,
        output_format=task.output_format,
        page_count=task.page_count,
        processing_duration=task.processing_duration,
        fields=fields_data,
        result=result_data,
        error_msg=task.error_msg,
    )


@router.post("/download/{task_id}")
async def download_pdf_extract(
    task_id: int,
    db: AsyncSession = Depends(get_session),
):
    """下载导出文件（CSV/XLSX）"""
    task = await db.get(PdfExtractTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "done":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    statement = select(PdfExtractResult).where(PdfExtractResult.task_id == task_id)
    db_result = (await db.execute(statement)).scalars().first()
    if not db_result:
        raise HTTPException(status_code=404, detail="未找到提取结果")

    extracted_data = json.loads(db_result.extracted_data)
    export_data = [{"filename": task.filename, "data": extracted_data}]

    fmt = task.output_format
    if fmt == "csv":
        file_path = export_csv(export_data)
        media_type = "text/csv"
        filename = f"extract_{task.id}.csv"
    elif fmt == "xlsx":
        file_path = export_xlsx(export_data)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"extract_{task.id}.xlsx"
    else:
        raise HTTPException(status_code=400, detail="当前输出格式为 JSON，请使用 CSV 或 XLSX 下载")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
    )


@router.delete("/{task_id}")
async def delete_pdf_extract_task(
    task_id: int,
    db: AsyncSession = Depends(get_session),
):
    """删除提取任务及其结果"""
    task = await db.get(PdfExtractTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 删除关联结果
    statement = select(PdfExtractResult).where(PdfExtractResult.task_id == task_id)
    results = (await db.execute(statement)).scalars().all()
    for r in results:
        await db.delete(r)

    # 删除磁盘文件
    if task.file_path and os.path.exists(task.file_path):
        os.remove(task.file_path)

    await db.delete(task)
    await db.commit()

    return {"detail": "已删除", "task_id": task_id}
