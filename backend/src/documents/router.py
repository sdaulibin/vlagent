from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, desc
from sqlalchemy import delete as sql_delete, and_
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote
import os

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

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

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


def _copyfileobj_limited(fsrc, fdst, max_size: int, chunk_size: int = 1024 * 1024):
    """带大小限制的文件拷贝，超过 max_size 抛出 ValueError"""
    total = 0
    while True:
        chunk = fsrc.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size:
            raise ValueError(f"文件大小超过限制 ({max_size // (1024 * 1024)}MB)")
        fdst.write(chunk)


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

    try:
        with open(file_a_path, "wb") as buf:
            _copyfileobj_limited(file_a.file, buf, MAX_FILE_SIZE)
    except ValueError:
        if os.path.exists(file_a_path):
            os.remove(file_a_path)
        raise HTTPException(status_code=413, detail=f"文件 {file_a.filename} 超过 50MB 限制")

    try:
        with open(file_b_path, "wb") as buf:
            _copyfileobj_limited(file_b.file, buf, MAX_FILE_SIZE)
    except ValueError:
        for p in (file_a_path, file_b_path):
            if os.path.exists(p):
                os.remove(p)
        raise HTTPException(status_code=413, detail=f"文件 {file_b.filename} 超过 50MB 限制")

    # 防重复提交：相同文件名如有 pending/processing 状态的任务，直接返回
    existing_stmt = select(DocumentCompareTask).where(
        and_(
            DocumentCompareTask.file_a_name == file_a.filename,
            DocumentCompareTask.file_b_name == file_b.filename,
            DocumentCompareTask.status.in_(["pending", "processing"]),
        )
    ).order_by(desc(DocumentCompareTask.created_at)).limit(1)
    existing = (await db.execute(existing_stmt)).scalars().first()
    if existing:
        # 清理刚上传的重复文件
        for p in (file_a_path, file_b_path):
            if os.path.exists(p):
                os.remove(p)
        return {"task_id": existing.id, "status": existing.status}

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

    background_tasks.add_task(process_document_comparison, task.id)

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
            import asyncio
            from src.documents.service import docx_to_pdf
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(docx_to_pdf, file_path, os.path.dirname(file_path)),
                    timeout=120,
                )
            except asyncio.TimeoutError:
                raise HTTPException(status_code=504, detail="文档转换PDF超时，请稍后重试")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"文档转换PDF失败: {e}")
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
        # 清理 DOCX 转换产生的 PDF 缓存
        if path:
            pdf_cache = os.path.splitext(path)[0] + ".pdf"
            if os.path.exists(pdf_cache):
                try:
                    os.remove(pdf_cache)
                except Exception:
                    pass

    await db.delete(task)
    await db.commit()
    return {"status": "success", "message": "任务已删除"}
