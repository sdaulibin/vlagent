"""
询证函格式比对 API 路由
"""
import os
import json
import time
import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.database import get_session
from .models import FormatCompareTask, FormatCompareTaskDTO, FormatMismatchItem, TemplateInfo
from .service import compare_with_template, get_template_list, get_template_pdf_path, _load_template

router = APIRouter(prefix="/format-compare", tags=["格式比对"])

# 上传目录
UPLOAD_DIR = os.getenv(
    "FORMAT_COMPARE_UPLOAD_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "res", "format_compare")
)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _parse_mismatches(raw_json: str | None) -> list[FormatMismatchItem]:
    if not raw_json:
        return []
    try:
        items = json.loads(raw_json)
        return [FormatMismatchItem(**m) for m in items]
    except Exception:
        return []


def _parse_json_list(raw_json: str | None) -> list | None:
    if not raw_json:
        return None
    try:
        return json.loads(raw_json)
    except Exception:
        return None


def _to_dto(task: FormatCompareTask) -> FormatCompareTaskDTO:
    # 解析 extracted_content
    extracted_content = _parse_json_list(task.extracted_content_json)
    
    # 加载对应模板的 template_content
    template_content = None
    if task.format_type and task.format_type != "unknown":
        template = _load_template(task.format_type)
        if template:
            template_content = template.get("highlighted_content", [])
    
    return FormatCompareTaskDTO(
        id=task.id,
        filename=task.filename,
        format_type=task.format_type,
        status=task.status,
        passed=task.passed,
        mismatches=_parse_mismatches(task.mismatches_json),
        extracted_content=extracted_content,
        template_content=template_content,
        error_msg=task.error_msg,
        duration_ms=task.duration_ms,
        created_at=task.created_at,
    )


@router.get("/templates", response_model=list[TemplateInfo])
async def list_templates():
    """获取可用模板列表"""
    templates = get_template_list()
    return [TemplateInfo(**t) for t in templates]


@router.get("/templates/{format_key}/preview")
async def preview_template(format_key: str):
    """预览模板 PDF"""
    path = get_template_pdf_path(format_key)
    if not path:
        raise HTTPException(404, f"模板 {format_key} 不存在")
    return FileResponse(path, media_type="application/pdf")


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """上传询证函（仅保存文件，不立即比对）"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持 PDF 文件")

    # 保存文件
    safe_name = f"{uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 创建任务记录（状态为 pending）
    task = FormatCompareTask(
        filename=file.filename,
        file_path=file_path,
        status="pending",
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    return _to_dto(task)


@router.post("/{task_id}/compare")
async def run_compare(
    task_id: int,
    session: AsyncSession = Depends(get_session),
):
    """对已上传的文件执行格式比对"""
    task = await session.get(FormatCompareTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.status == "processing":
        raise HTTPException(400, "比对正在进行中")

    task.status = "processing"
    session.add(task)
    await session.commit()
    await session.refresh(task)

    # 执行比对
    start_time = time.time()
    try:
        result = await asyncio.to_thread(compare_with_template, task.file_path)
        task.format_type = result.get("format_type", "unknown")
        task.passed = result.get("passed", False)
        task.mismatches_json = json.dumps(result.get("mismatches", []), ensure_ascii=False)
        task.extracted_content_json = json.dumps(result.get("extracted_content", []), ensure_ascii=False)
        task.status = "done"
    except Exception as e:
        task.status = "failed"
        task.error_msg = str(e)

    task.duration_ms = round((time.time() - start_time) * 1000, 1)
    session.add(task)
    await session.commit()
    await session.refresh(task)

    return _to_dto(task)


@router.get("", response_model=list[FormatCompareTaskDTO])
async def list_tasks(session: AsyncSession = Depends(get_session)):
    """获取所有比对任务"""
    stmt = select(FormatCompareTask).order_by(FormatCompareTask.created_at.desc())
    result = await session.execute(stmt)
    tasks = result.scalars().all()
    return [_to_dto(t) for t in tasks]


@router.get("/{task_id}", response_model=FormatCompareTaskDTO)
async def get_task(task_id: int, session: AsyncSession = Depends(get_session)):
    """获取单个比对任务详情"""
    task = await session.get(FormatCompareTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return _to_dto(task)


@router.get("/{task_id}/file")
async def preview_uploaded_file(task_id: int, session: AsyncSession = Depends(get_session)):
    """预览上传的询证函 PDF"""
    task = await session.get(FormatCompareTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if not os.path.exists(task.file_path):
        raise HTTPException(404, "文件不存在")
    return FileResponse(task.file_path, media_type="application/pdf")


@router.delete("/{task_id}")
async def delete_task(task_id: int, session: AsyncSession = Depends(get_session)):
    """删除比对任务"""
    task = await session.get(FormatCompareTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    # 删除文件
    if os.path.exists(task.file_path):
        os.remove(task.file_path)

    await session.delete(task)
    await session.commit()
    return {"message": "已删除"}
