"""
财务报告比对 API 路由
"""
import os
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only
from sqlmodel import select

from src.auth import get_current_user_id
from src.config import settings
from src.database import get_session
from src.financial_compare.models import (
    FinancialCompareTask,
    FinancialCompareStatusResponse,
    FinancialCompareTaskItem,
    FinancialCompareDetail,
)
from src.financial_compare.service import process_financial_compare

router = APIRouter(prefix="/financial-compare", tags=["财务报告比对"])

ALLOWED_DOCX_EXT = {".docx"}
ALLOWED_PDF_EXT = {".pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _copyfileobj_limited(src, dst, limit=MAX_FILE_SIZE):
    """Copy file with size limit"""
    total = 0
    while chunk := src.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise ValueError(f"文件大小超过限制 ({limit // 1024 // 1024}MB)")
        dst.write(chunk)


@router.post("/compare")
async def compare(
    background_tasks: BackgroundTasks,
    file_docx: UploadFile = File(..., description="基准 DOCX 文件"),
    file_pdf: UploadFile = File(..., description="年度报告 PDF 文件"),
    docx_start_page: int = Form(default=1, description="DOCX 起始页"),
    docx_end_page: int | None = Form(default=None, description="DOCX 结束页（空=到末尾）"),
    pdf_start_page: int = Form(default=1, description="PDF 起始页"),
    pdf_end_page: int | None = Form(default=None, description="PDF 结束页（空=到末尾）"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """上传文件并启动比对任务"""
    # 验证文件扩展名
    docx_ext = os.path.splitext(file_docx.filename or "")[1].lower()
    pdf_ext = os.path.splitext(file_pdf.filename or "")[1].lower()
    if docx_ext not in ALLOWED_DOCX_EXT:
        raise HTTPException(400, f"基准文件仅支持 .docx 格式，收到: {docx_ext}")
    if pdf_ext not in ALLOWED_PDF_EXT:
        raise HTTPException(400, f"年度报告仅支持 .pdf 格式，收到: {pdf_ext}")

    # PDF magic number 验证
    header = await file_pdf.read(5)
    await file_pdf.seek(0)
    if header[:4] != b"%PDF":
        raise HTTPException(400, "上传的 PDF 文件格式不正确")

    # 保存文件
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(user_id), "financial_compare")
    os.makedirs(upload_dir, exist_ok=True)

    docx_suffix = f"_{uuid.uuid4().hex[:8]}{docx_ext}"
    pdf_suffix = f"_{uuid.uuid4().hex[:8]}{pdf_ext}"

    docx_path = os.path.join(upload_dir, f"{file_docx.filename}{docx_suffix}")
    pdf_path = os.path.join(upload_dir, f"{file_pdf.filename}{pdf_suffix}")

    with open(docx_path, "wb") as f:
        _copyfileobj_limited(file_docx.file, f)
    with open(pdf_path, "wb") as f:
        _copyfileobj_limited(file_pdf.file, f)

    # 创建任务
    task = FinancialCompareTask(
        user_id=user_id,
        docx_file_path=docx_path,
        docx_file_name=file_docx.filename,
        pdf_file_path=pdf_path,
        pdf_file_name=file_pdf.filename,
        docx_start_page=docx_start_page,
        docx_end_page=docx_end_page,
        pdf_start_page=pdf_start_page,
        pdf_end_page=pdf_end_page,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    task_id = task.id

    # 关闭 session 后启动后台任务
    await session.close()

    background_tasks.add_task(process_financial_compare, task_id)

    return {"task_id": task_id, "status": "pending"}


@router.get("/list", response_model=list[FinancialCompareTaskItem])
async def list_tasks(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户的比对任务列表"""
    # load_only 排除 diff_blocks 大字段，避免列表查询拉取大文本
    stmt = (
        select(FinancialCompareTask)
        .options(load_only(
            FinancialCompareTask.id,
            FinancialCompareTask.docx_file_name,
            FinancialCompareTask.pdf_file_name,
            FinancialCompareTask.docx_start_page,
            FinancialCompareTask.docx_end_page,
            FinancialCompareTask.pdf_start_page,
            FinancialCompareTask.pdf_end_page,
            FinancialCompareTask.status,
            FinancialCompareTask.duration,
            FinancialCompareTask.created_at,
        ))
        .where(FinancialCompareTask.user_id == user_id)
        .order_by(FinancialCompareTask.created_at.desc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/list/{task_id}", response_model=FinancialCompareDetail)
async def get_task_detail(
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取任务详情（含比对结果）。"""
    task = await session.get(FinancialCompareTask, task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(404, "任务不存在")
    return task


@router.get("/{task_id}/status", response_model=FinancialCompareStatusResponse)
async def get_task_status(
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """轮询任务状态"""
    task = await session.get(FinancialCompareTask, task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(404, "任务不存在")
    return task


@router.get("/{task_id}/file/{doc_type}")
async def get_file(
    task_id: int,
    doc_type: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取原始文件（docx 或 pdf）"""
    task = await session.get(FinancialCompareTask, task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(404, "任务不存在")

    if doc_type == "docx":
        path = task.docx_file_path
        filename = task.docx_file_name
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif doc_type == "pdf":
        path = task.pdf_file_path
        filename = task.pdf_file_name
        media_type = "application/pdf"
    else:
        raise HTTPException(400, "doc_type 必须为 docx 或 pdf")

    if not os.path.exists(path):
        raise HTTPException(404, "文件不存在")

    return FileResponse(path, media_type=media_type, filename=filename)


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """删除比对任务及文件"""
    task = await session.get(FinancialCompareTask, task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(404, "任务不存在")

    # 删除文件
    for path in [task.docx_file_path, task.pdf_file_path]:
        try:
            if path and os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass

    await session.delete(task)
    await session.commit()
    return {"detail": "已删除"}
