from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, desc
from sqlalchemy import delete as sql_delete
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote
import os
import shutil

from src.database import get_session
from src.documents.models import (
    DocumentCompareTask,
    DocumentPageDiff,
    DocumentTaskListItem,
    DocumentTaskStatusResponse,
    DocumentPageDiffItem,
    DocumentCompareResponse,
)
from src.documents.service import process_document_comparison

router = APIRouter(prefix="/documents", tags=["文档比对"])
public_router = APIRouter(tags=["文档比对-文件访问"])

UPLOAD_DIR = os.getenv(
    "DOCUMENT_UPLOAD_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "upload", "documents"),
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def _build_safe_upload_path(upload_dir: str, original_filename: str, prefix: str = "") -> str:
    safe_name = Path((original_filename or "").strip()).name
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="文件名无效")

    stem, suffix = os.path.splitext(safe_name)
    unique_name = f"{prefix}{stem}_{uuid4().hex}{suffix}"

    base_dir = Path(upload_dir).resolve()
    target_path = (base_dir / unique_name).resolve()
    if base_dir not in target_path.parents:
        raise HTTPException(status_code=400, detail="非法文件路径")
    return str(target_path)


@router.post("/compare")
async def compare_documents(
    background_tasks: BackgroundTasks,
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
):
    """上传两份文档并启动异步比对"""
    allowed = (".pdf", ".docx", ".doc")
    for f in (file_a, file_b):
        if not (f.filename or "").lower().endswith(allowed):
            raise HTTPException(status_code=400, detail=f"仅支持 PDF 和 Word 文档，不支持: {f.filename}")

    file_a_path = _build_safe_upload_path(UPLOAD_DIR, file_a.filename, prefix="a_")
    file_b_path = _build_safe_upload_path(UPLOAD_DIR, file_b.filename, prefix="b_")

    with open(file_a_path, "wb") as buf:
        shutil.copyfileobj(file_a.file, buf)
    with open(file_b_path, "wb") as buf:
        shutil.copyfileobj(file_b.file, buf)

    task = DocumentCompareTask(
        file_a_name=file_a.filename,
        file_a_path=file_a_path,
        file_b_name=file_b.filename,
        file_b_path=file_b_path,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(process_document_comparison, db, task)

    return {"task_id": task.id, "status": "pending"}


@router.post("/list", response_model=list[DocumentTaskListItem])
async def list_tasks(db: AsyncSession = Depends(get_session)):
    """获取所有比对任务列表"""
    statement = select(DocumentCompareTask).order_by(desc(DocumentCompareTask.created_at))
    result = await db.execute(statement)
    tasks = result.scalars().all()
    return [DocumentTaskListItem.model_validate(t) for t in tasks]


@router.post("/list/{task_id}", response_model=DocumentCompareResponse)
async def get_task(task_id: int, db: AsyncSession = Depends(get_session)):
    """获取任务详情（含页级 diff）"""
    task = await db.get(DocumentCompareTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    pages_stmt = select(DocumentPageDiff).where(DocumentPageDiff.task_id == task_id).order_by(DocumentPageDiff.id)
    pages_result = await db.execute(pages_stmt)
    pages = [DocumentPageDiffItem.model_validate(p) for p in pages_result.scalars().all()]

    resp = DocumentCompareResponse.model_validate(task)
    resp.pages = pages
    return resp


@router.post("/{task_id}/status", response_model=DocumentTaskStatusResponse)
async def get_task_status(task_id: int, db: AsyncSession = Depends(get_session)):
    """轮询任务状态"""
    task = await db.get(DocumentCompareTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return DocumentTaskStatusResponse.model_validate(task)


async def _serve_task_file(task_id: int, doc_type: str, db: AsyncSession):
    """文件服务内部方法。DOCX/DOC 自动转 PDF 后返回，转换结果缓存到同目录"""
    task = await db.get(DocumentCompareTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if doc_type == "a":
        file_path, filename = task.file_a_path, task.file_a_name
    elif doc_type == "b":
        file_path, filename = task.file_b_path, task.file_b_name
    else:
        raise HTTPException(status_code=400, detail="doc_type 必须为 'a' 或 'b'")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    ext = os.path.splitext(filename)[1].lower()

    # DOCX/DOC → PDF 转换（缓存到同目录，下次直接返回）
    if ext in (".docx", ".doc"):
        pdf_path = os.path.splitext(file_path)[0] + ".pdf"
        if not os.path.exists(pdf_path):
            from src.documents.service import docx_to_pdf
            docx_to_pdf(file_path, output_dir=os.path.dirname(file_path))
        file_path = pdf_path
        ext = ".pdf"
        filename = os.path.splitext(filename)[0] + ".pdf"

    media_type = MIME_TYPES.get(ext, "application/octet-stream")
    encoded_filename = quote(filename)

    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"},
    )


@router.post("/{task_id}/file/{doc_type}")
async def get_task_file(task_id: int, doc_type: str, db: AsyncSession = Depends(get_session)):
    """获取原始文件（POST，需认证）"""
    return await _serve_task_file(task_id, doc_type, db)


@public_router.get("/documents/{task_id}/file/{doc_type}")
async def get_task_file_public(task_id: int, doc_type: str, db: AsyncSession = Depends(get_session)):
    """获取原始文件（GET，无需认证，用于 iframe 嵌入，支持 #page=N 页码跳转）"""
    return await _serve_task_file(task_id, doc_type, db)


@router.delete("/{task_id}")
async def delete_task(task_id: int, db: AsyncSession = Depends(get_session)):
    """删除比对任务及关联数据"""
    task = await db.get(DocumentCompareTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    await db.execute(sql_delete(DocumentPageDiff).where(DocumentPageDiff.task_id == task_id))

    for path in [task.file_a_path, task.file_b_path]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    await db.delete(task)
    await db.commit()
    return {"status": "success", "message": "任务已删除"}
