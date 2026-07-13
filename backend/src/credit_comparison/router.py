"""
信用金额对账 - REST 接口。

遵循宿主约定：APIRouter(prefix="/credit-comparison")，挂在 api_router 下，
统一经 JWT 校验。后台处理用 FastAPI BackgroundTasks + 独立 session（三段式）。
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import List
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import or_
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth import get_current_user_id
from src.config import UPLOAD_DIR_CREDIT_COMPARISON
from src.database import get_session
from src.credit_comparison import exporter, repository, service, view
from src.credit_comparison.exporter import EXCEL_MEDIA_TYPE
from src.credit_comparison.models import (
    CompareTaskItem,
    CompareTaskListResponse,
    CreditCompareTask,
)

router = APIRouter(prefix="/credit-comparison", tags=["Credit Amount Comparison"])

UPLOAD_DIR = UPLOAD_DIR_CREDIT_COMPARISON
os.makedirs(UPLOAD_DIR, exist_ok=True)

WORD_EXTENSIONS = (".doc", ".docx")
EXCEL_EXTENSIONS = (".xls", ".xlsx")


def _task_to_item(task: CreditCompareTask) -> CompareTaskItem:
    return CompareTaskItem(
        id=task.id,
        batch_id=task.batch_id,
        word_file_name=task.word_file_name,
        excel_file_name=task.excel_file_name,
        status=task.status,
        error_msg=task.error_msg or "",
        link_count=task.link_count,
        exception_count=task.exception_count,
        unmatched_count=task.unmatched_count,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


# ====== 上传 / 任务列表 ======


@router.post("/upload", response_model=CompareTaskItem)
async def upload_compare_files(
    background_tasks: BackgroundTasks,
    word_file: UploadFile = File(..., description="Word 文件"),
    excel_file: UploadFile = File(..., description="Excel 文件"),
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """上传 Word + Excel，创建对账任务并放入后台处理。"""

    word_name = word_file.filename or "word.docx"
    excel_name = excel_file.filename or "excel.xlsx"
    if not word_name.lower().endswith(WORD_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Word 文件仅支持 .doc/.docx")
    if not excel_name.lower().endswith(EXCEL_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Excel 文件仅支持 .xls/.xlsx")

    word_content = await word_file.read()
    excel_content = await excel_file.read()
    if not word_content:
        raise HTTPException(status_code=400, detail="Word 文件不能为空")
    if not excel_content:
        raise HTTPException(status_code=400, detail="Excel 文件不能为空")

    batch_id = service.generate_batch_id()
    word_dir, excel_dir = service.build_task_dirs(batch_id, user_id)
    word_path = os.path.join(word_dir, os.path.basename(word_name).replace(" ", "_"))
    excel_path = os.path.join(excel_dir, os.path.basename(excel_name).replace(" ", "_"))
    with open(word_path, "wb") as out:
        out.write(word_content)
    with open(excel_path, "wb") as out:
        out.write(excel_content)

    task = CreditCompareTask(
        batch_id=batch_id,
        user_id=user_id,
        word_file_name=os.path.basename(word_path),
        excel_file_name=os.path.basename(excel_path),
        word_dir=word_dir,
        excel_dir=excel_dir,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    resp_item = _task_to_item(task)
    task_id = task.id
    # 关闭请求级 session，避免后台任务执行期间占用连接导致连接池耗尽。
    await db.close()

    background_tasks.add_task(service.process_compare_task, task_id)
    return resp_item


@router.get("/tasks", response_model=CompareTaskListResponse)
async def list_tasks(
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """返回当前用户的对账任务列表（按创建时间倒序）。"""

    stmt = (
        select(CreditCompareTask)
        .where(or_(CreditCompareTask.user_id == user_id, CreditCompareTask.user_id.is_(None)))
        .order_by(CreditCompareTask.created_at.desc())
    )
    tasks = (await db.execute(stmt)).scalars().all()
    batch_ids = [str(t.batch_id or "").strip() for t in tasks if str(t.batch_id or "").strip()]
    stats_map = await repository.list_batch_compare_stats(db, batch_ids)
    items = []
    for task in tasks:
        item = _task_to_item(task)
        stats = stats_map.get(str(task.batch_id or "").strip())
        if stats:
            item.link_count = int(stats.get("link_count", item.link_count))
            item.exception_count = int(stats.get("exception_count", item.exception_count))
            item.unmatched_count = int(stats.get("unmatched_count", item.unmatched_count))
        items.append(item)
    return CompareTaskListResponse(items=items, total=len(items))


@router.get("/tasks/{task_id}", response_model=CompareTaskItem)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """返回单个任务状态。"""

    task = await db.get(CreditCompareTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id is not None and task.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问")
    item = _task_to_item(task)
    stats_map = await repository.list_batch_compare_stats(db, [str(task.batch_id or "").strip()])
    stats = stats_map.get(str(task.batch_id or "").strip())
    if stats:
        item.link_count = int(stats.get("link_count", item.link_count))
        item.exception_count = int(stats.get("exception_count", item.exception_count))
        item.unmatched_count = int(stats.get("unmatched_count", item.unmatched_count))
    return item


@router.post("/tasks/{task_id}/reprocess", response_model=CompareTaskItem)
async def reprocess_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """重新对账：重置为 pending 后再次入队。"""

    task = await db.get(CreditCompareTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id is not None and task.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问")
    task.status = "pending"
    task.error_msg = ""
    task.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    resp_item = _task_to_item(task)

    task_id_local = task.id
    await db.close()
    background_tasks.add_task(service.process_compare_task, task_id_local)
    return resp_item


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """删除任务及其关联业务数据和磁盘文件。"""

    task = await db.get(CreditCompareTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id is not None and task.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问")
    await service.delete_task_with_files(db, task_id)
    await db.commit()
    return {"detail": "已删除", "task_id": task_id}


# ====== 详情聚合 ======


async def _get_task_by_batch(db: AsyncSession, batch_id: str, user_id: str) -> CreditCompareTask:
    """按批次号查询任务并校验属主。"""

    stmt = select(CreditCompareTask).where(CreditCompareTask.batch_id == batch_id)
    task = (await db.execute(stmt)).scalars().first()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id is not None and task.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问")
    return task


@router.get("/batches/{batch_id}/detail")
async def get_task_detail(
    batch_id: str,
    word_file_name: str = Query("", description="Word 文件名（可选，缺省取任务记录）"),
    excel_file_name: str = Query("", description="Excel 文件名（可选）"),
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """返回对账工作台详情（画线列表 + 异常分组 + 锚点）。"""

    await _get_task_by_batch(db, batch_id, user_id)
    return await view.get_document_pair_detail(db, batch_id, word_file_name, excel_file_name)


@router.get("/batches/{batch_id}/exceptions/export")
async def export_exceptions(
    batch_id: str,
    word_file_name: str = Query("", description="Word 文件名（可选）"),
    excel_file_name: str = Query("", description="Excel 文件名（可选）"),
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """导出任务详情页的异常记录为 xlsx。"""

    await _get_task_by_batch(db, batch_id, user_id)
    try:
        file_name, payload = await exporter.export_document_pair_exceptions(
            db, batch_id, word_file_name, excel_file_name
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=payload,
        media_type=EXCEL_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}"},
    )


@router.delete("/batches/{batch_id}")
async def delete_task_by_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """按批次号删除任务及其关联业务数据和磁盘文件。"""

    task = await _get_task_by_batch(db, batch_id, user_id)
    task_id = task.id
    await service.delete_task_with_files(db, task_id)
    await db.commit()
    return {"detail": "已删除", "batch_id": batch_id}


# ====== 预览 ======


@router.get("/previews/word")
async def preview_word(
    file_name: str = Query(...),
    batch_id: str = Query(...),
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """返回 Word 文档 PDF 预览。"""

    try:
        path = await view_get_word_preview_path(db, file_name, batch_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path)


@router.get("/previews/excel")
async def preview_excel(
    file_name: str = Query(...),
    batch_id: str = Query(...),
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """返回 Excel 文档 PDF 预览。"""

    try:
        path = await view_get_excel_preview_path(db, file_name, batch_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path)


@router.get("/previews/word-structured")
async def preview_word_structured(
    file_name: str = Query(...),
    batch_id: str = Query(...),
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """返回 Word 结构化预览数据。"""

    try:
        return await view_get_word_preview_data(db, file_name, batch_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/previews/excel-structured")
async def preview_excel_structured(
    file_name: str = Query(...),
    batch_id: str = Query(...),
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """返回 Excel 结构化预览数据。"""

    try:
        return await view_get_excel_preview_data(db, file_name, batch_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# 预览函数别名，便于在 router 内统一引用 view.py 的预览能力。
# 注意：preview 模块需要 db 来定位源文件（从任务记录读取 word_dir/excel_dir）。
from src.credit_comparison.preview import (
    get_excel_preview_data as view_get_excel_preview_data,
    get_excel_preview_path as view_get_excel_preview_path,
    get_word_preview_data as view_get_word_preview_data,
    get_word_preview_path as view_get_word_preview_path,
)
