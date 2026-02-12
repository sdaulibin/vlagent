from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from typing import List
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote
import shutil
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc

from src.database import get_session
from src.contracts.models import CompareTask, DiffRecord
from services import contract_processor

router = APIRouter(prefix="/contracts", tags=["contracts"])

UPLOAD_DIR = "/Users/binginx/PycharmProjects/vl_flow/backend/res/contracts"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _build_safe_upload_path(upload_dir: str, original_filename: str, prefix: str = "") -> str:
    """Build a safe, unique path under upload_dir and prevent path traversal."""
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

# 文件类型映射
MIME_TYPES = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
}


@router.get("", response_model=List[CompareTask])
async def get_compare_tasks(session: AsyncSession = Depends(get_session)):
    """获取所有比对任务列表"""
    statement = select(CompareTask).order_by(desc(CompareTask.created_at))
    result = await session.execute(statement)
    return result.scalars().all()


@router.get("/{task_id}", response_model=CompareTask)
async def get_compare_task(task_id: int, session: AsyncSession = Depends(get_session)):
    """获取单个比对任务详情"""
    statement = select(CompareTask).where(CompareTask.id == task_id)
    result = await session.execute(statement)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/diffs", response_model=List[DiffRecord])
async def get_task_diffs(task_id: int, session: AsyncSession = Depends(get_session)):
    """获取比对任务的差异列表"""
    statement = select(DiffRecord).where(DiffRecord.task_id == task_id)
    result = await session.execute(statement)
    return result.scalars().all()


@router.get("/{task_id}/file/{doc_type}")
async def get_task_file(task_id: int, doc_type: str, session: AsyncSession = Depends(get_session)):
    """
    获取比对任务的原始文件
    doc_type: 'a' 或 'b'，分别代表原文档和比对文档
    """
    statement = select(CompareTask).where(CompareTask.id == task_id)
    result = await session.execute(statement)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if doc_type == 'a':
        file_path = task.file_a_path
        filename = task.file_a_name
    elif doc_type == 'b':
        file_path = task.file_b_path
        filename = task.file_b_name
    else:
        raise HTTPException(status_code=400, detail="doc_type must be 'a' or 'b'")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # 获取文件扩展名和 MIME 类型
    ext = os.path.splitext(filename)[1].lower()
    media_type = MIME_TYPES.get(ext, 'application/octet-stream')
    
    # URL 编码文件名以处理中文字符
    encoded_filename = quote(filename)

    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"
        }
    )

@router.post("/compare")
async def compare_contracts(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    """上传两份文档并进行比对"""
    try:
        # 确保目录存在
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # 保存文件
        file_a_path = _build_safe_upload_path(UPLOAD_DIR, file_a.filename, prefix="a_")
        file_b_path = _build_safe_upload_path(UPLOAD_DIR, file_b.filename, prefix="b_")
        
        with open(file_a_path, "wb") as buffer:
            shutil.copyfileobj(file_a.file, buffer)
        
        with open(file_b_path, "wb") as buffer:
            shutil.copyfileobj(file_b.file, buffer)
        
        # 创建比对任务
        task = CompareTask(
            file_a_name=file_a.filename,
            file_a_path=file_a_path,
            file_b_name=file_b.filename,
            file_b_path=file_b_path,
            status="processing"
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        
        try:
            # 执行比对并获取内容
            result_data = await run_in_threadpool(
                contract_processor.compare_documents_with_content,
                file_a_path,
                file_b_path,
            )
            
            content_a = result_data.get("content_a", "")
            content_b = result_data.get("content_b", "")
            diffs = result_data.get("diffs", [])
            
            # 更新任务内容
            task.content_a = content_a
            task.content_b = content_b
            
            # 保存差异记录
            for diff_data in diffs:
                diff = DiffRecord(
                    task_id=task.id,
                    diff_type=diff_data.get("type", "modified"),
                    original_text=diff_data.get("original", ""),
                    comparison_text=diff_data.get("comparison", ""),
                    location=diff_data.get("location", "")
                )
                session.add(diff)
            
            task.status = "done"
            await session.commit()
            
            return {
                "status": "success",
                "task_id": task.id,
                "diff_count": len(diffs),
                "content_a": content_a,
                "content_b": content_b
            }
            
        except Exception as e_compare:
            task.status = "failed"
            task.error_msg = str(e_compare)
            await session.commit()
            raise e_compare
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}")
async def delete_compare_task(task_id: int, session: AsyncSession = Depends(get_session)):
    """删除比对任务及其差异记录"""
    from sqlmodel import delete
    
    # 查询任务
    statement = select(CompareTask).where(CompareTask.id == task_id)
    result = await session.execute(statement)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 先删除关联的差异记录（使用 SQL DELETE）
    delete_diffs_stmt = delete(DiffRecord).where(DiffRecord.task_id == task_id)
    await session.execute(delete_diffs_stmt)
    
    # 删除文件
    for path in [task.file_a_path, task.file_b_path]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                print(f"Failed to delete file {path}: {e}")
    
    # 删除任务记录
    await session.delete(task)
    await session.commit()
    
    return {"status": "success", "message": "Task deleted"}
