"""
询证函格式比对 API 路由
"""
import os
import json
import time
import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sqlalchemy import or_

from src.auth import get_current_user_id
from src.database import get_session
from .models import FormatCompareFile, FormatCompareResult, FormatCompareTaskDTO, FormatMismatchItem, TemplateInfo
from .service import compare_with_template, get_template_list, get_template_pdf_path, _load_template

router = APIRouter(prefix="/format-compare", tags=["格式比对"])

# 从统一配置读取上传目录
from src.config import UPLOAD_DIR_FORMAT_COMPARE
UPLOAD_DIR = UPLOAD_DIR_FORMAT_COMPARE
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


def _to_dto(file_obj: FormatCompareFile, result_obj: FormatCompareResult | None) -> FormatCompareTaskDTO:
    # 解析 extracted_content
    extracted_content = _parse_json_list(result_obj.extracted_content_json) if result_obj else None

    # 加载对应模板的 template_content
    format_type = result_obj.format_type if result_obj else None
    template_content = None
    if format_type and format_type != "unknown":
        template = _load_template(format_type)
        if template:
            template_content = template.get("highlighted_content", [])

    return FormatCompareTaskDTO(
        id=file_obj.id,
        filename=file_obj.filename,
        format_type=format_type,
        status=file_obj.status,
        passed=result_obj.passed if result_obj else None,
        mismatches=_parse_mismatches(result_obj.mismatches_json) if result_obj else [],
        extracted_content=extracted_content,
        template_content=template_content,
        error_msg=file_obj.error_msg,
        duration_ms=file_obj.duration_ms,
        created_at=file_obj.created_at,
    )


async def _get_file_with_result(file_id: int, session: AsyncSession, user_id: str):
    """获取文件记录和比对结果，带权限校验"""
    file_obj = await session.get(FormatCompareFile, file_id)
    if not file_obj:
        raise HTTPException(404, "文件不存在")
    if file_obj.user_id is not None and file_obj.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问")

    res_stmt = select(FormatCompareResult).where(FormatCompareResult.file_id == file_id)
    res_result = await session.execute(res_stmt)
    result_obj = res_result.scalar_one_or_none()
    return file_obj, result_obj


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
    user_id: str = Depends(get_current_user_id),
):
    """上传询证函（仅保存文件，不立即比对）"""
    # 验证文件格式（扩展名 + 魔数）
    from services.pdf.file_validator import validate_file_content, read_file_header
    header = await read_file_header(file)
    is_valid, error_msg = validate_file_content(file.filename, header, [".pdf"])
    if not is_valid:
        raise HTTPException(400, error_msg)

    user_upload_dir = os.path.join(UPLOAD_DIR, user_id)
    os.makedirs(user_upload_dir, exist_ok=True)

    safe_name = f"{uuid4().hex[:8]}_{os.path.basename(file.filename)}"
    file_path = os.path.join(user_upload_dir, safe_name)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    record = FormatCompareFile(
        filename=file.filename,
        file_path=file_path,
        user_id=user_id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    return _to_dto(record, None)


@router.post("/{file_id}/compare")
async def run_compare(
    file_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """提交比对任务（异步后台处理）"""
    file_obj, _ = await _get_file_with_result(file_id, session, user_id)

    if file_obj.status == "processing":
        raise HTTPException(400, "比对正在进行中")

    file_obj.status = "processing"
    session.add(file_obj)
    await session.commit()

    background_tasks.add_task(_run_compare_async, file_id)

    return _to_dto(file_obj, None)


async def _run_compare_async(file_id: int):
    """后台比对任务，使用独立 session"""
    from src.database import SessionLocal

    async with SessionLocal() as db:
        file_obj = await db.get(FormatCompareFile, file_id)
        if not file_obj:
            return

        start_time = time.time()
        try:
            result = await asyncio.to_thread(compare_with_template, file_obj.file_path)

            # 删除旧结果
            old_stmt = select(FormatCompareResult).where(FormatCompareResult.file_id == file_id)
            old_res = await db.execute(old_stmt)
            old = old_res.scalar_one_or_none()
            if old:
                await db.delete(old)

            compare_result = FormatCompareResult(
                file_id=file_id,
                user_id=file_obj.user_id,
                format_type=result.get("format_type", "unknown"),
                passed=result.get("passed", False),
                mismatches_json=json.dumps(result.get("mismatches", []), ensure_ascii=False),
                extracted_content_json=json.dumps(result.get("extracted_content", []), ensure_ascii=False),
            )
            db.add(compare_result)

            file_obj.status = "done"
        except Exception as e:
            file_obj.status = "failed"
            file_obj.error_msg = str(e)

        file_obj.duration_ms = round((time.time() - start_time) * 1000, 1)
        db.add(file_obj)
        await db.commit()


@router.get("", response_model=list[FormatCompareTaskDTO])
async def list_tasks(
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """获取所有比对任务"""
    stmt = (
        select(FormatCompareFile, FormatCompareResult)
        .outerjoin(FormatCompareResult, FormatCompareResult.file_id == FormatCompareFile.id)
        .where(or_(FormatCompareFile.user_id == user_id, FormatCompareFile.user_id.is_(None)))
        .order_by(FormatCompareFile.created_at.desc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    seen = set()
    dtos = []
    for file_obj, result_obj in rows:
        if file_obj.id not in seen:
            seen.add(file_obj.id)
            dtos.append(_to_dto(file_obj, result_obj))
    return dtos


@router.get("/{file_id}", response_model=FormatCompareTaskDTO)
async def get_task(
    file_id: int,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """获取单个比对任务详情"""
    file_obj, result_obj = await _get_file_with_result(file_id, session, user_id)
    return _to_dto(file_obj, result_obj)


@router.get("/{file_id}/file")
async def preview_uploaded_file(
    file_id: int,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """预览上传的询证函 PDF"""
    file_obj, _ = await _get_file_with_result(file_id, session, user_id)
    if not os.path.exists(file_obj.file_path):
        raise HTTPException(404, "文件不存在")
    return FileResponse(file_obj.file_path, media_type="application/pdf")


@router.delete("/{file_id}")
async def delete_task(
    file_id: int,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """删除比对任务"""
    file_obj, _ = await _get_file_with_result(file_id, session, user_id)

    # 删除比对结果
    res_stmt = select(FormatCompareResult).where(FormatCompareResult.file_id == file_id)
    res_result = await session.execute(res_stmt)
    result_obj = res_result.scalar_one_or_none()
    if result_obj:
        await session.delete(result_obj)

    # 删除文件
    if os.path.exists(file_obj.file_path):
        os.remove(file_obj.file_path)

    await session.delete(file_obj)
    await session.commit()
    return {"message": "已删除"}
