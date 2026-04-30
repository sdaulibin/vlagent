import os
import json
import time
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlmodel import Session
from typing import Optional

from sqlalchemy import or_

from src.auth import get_current_user_id
from src.database import get_session
from src.credentials.service import process_credential
from src.credentials.schemas import CredentialExtractionResponse
from src.credentials.prompts import PROMPT_MAPPING
from src.credentials.models import (
    CredentialRecord,
    CredentialResult,
    CredentialRecordListItem,
    CredentialRecordResponse,
)

router = APIRouter(prefix="/credentials", tags=["credentials"])

# 配置上传目录
UPLOAD_DIR = os.getenv(
    "CREDENTIAL_UPLOAD_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "upload", "credentials"),
)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _build_safe_upload_path(upload_dir: str, original_filename: str) -> str:
    """Build a safe, unique path under upload_dir and prevent path traversal."""
    safe_name = Path((original_filename or "").strip()).name
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="文件名无效")

    stem, suffix = os.path.splitext(safe_name)
    unique_name = f"{stem}_{uuid4().hex}{suffix}"

    base_dir = Path(upload_dir).resolve()
    target_path = (base_dir / unique_name).resolve()
    if base_dir not in target_path.parents:
        raise HTTPException(status_code=400, detail="非法文件路径")
    return str(target_path)


@router.post("/extract", response_model=CredentialRecordResponse)
async def extract_credential(
    file: UploadFile = File(...),
    credential_type: str = Form(..., description=f"支持的类型: {', '.join(PROMPT_MAPPING.keys())}"),
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """
    提取凭证类文件(图片/PDF)的结构化信息，并保存记录。
    """
    if credential_type not in PROMPT_MAPPING:
        raise HTTPException(status_code=400, detail=f"不受支持的类型: {credential_type}")

    # 创建用户目录
    user_upload_dir = os.path.join(UPLOAD_DIR, user_id)
    os.makedirs(user_upload_dir, exist_ok=True)

    # 保存文件到持久化目录
    file_path = _build_safe_upload_path(user_upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 创建数据库记录
    record = CredentialRecord(
        filename=file.filename,
        file_path=file_path,
        credential_type=credential_type,
        status="processing",
        user_id=user_id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    # 执行提取
    start_time = time.time()
    try:
        result = process_credential(file_path, credential_type)
        duration = time.time() - start_time

        # 保存结果
        cred_result = CredentialResult(
            record_id=record.id,
            credential_type=result["credential_type"],
            extracted_data=json.dumps(result["extracted_data"], ensure_ascii=False),
            user_id=user_id,
        )
        session.add(cred_result)

        record.status = "done"
        record.processing_duration = round(duration, 2)
        await session.commit()
        await session.refresh(record)

        # 构造返回
        await session.refresh(cred_result)
        return CredentialRecordResponse(
            id=record.id,
            filename=record.filename,
            credential_type=record.credential_type,
            status=record.status,
            processing_duration=record.processing_duration,
            result=result["extracted_data"],
        )
    except Exception as e:
        duration = time.time() - start_time
        record.status = "failed"
        record.error_msg = str(e)
        record.processing_duration = round(duration, 2)
        await session.commit()
        await session.refresh(record)
        return CredentialRecordResponse(
            id=record.id,
            filename=record.filename,
            credential_type=record.credential_type,
            status=record.status,
            processing_duration=record.processing_duration,
            error_msg=str(e),
        )


@router.post("/list", response_model=list[CredentialRecordListItem])
async def list_records(
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """获取所有凭证提取记录"""
    statement = select(CredentialRecord).where(or_(CredentialRecord.user_id == user_id, CredentialRecord.user_id.is_(None))).order_by(CredentialRecord.created_at.desc())
    result = await session.execute(statement)
    records = result.scalars().all()
    return [
        CredentialRecordListItem(
            id=r.id,
            filename=r.filename,
            credential_type=r.credential_type,
            status=r.status,
            processing_duration=r.processing_duration,
            error_msg=r.error_msg,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.post("/list/{record_id}", response_model=CredentialRecordResponse)
async def get_record(
    record_id: int,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """获取单条凭证提取记录详情"""
    statement = select(CredentialRecord).where(CredentialRecord.id == record_id)
    result = await session.execute(statement)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    if record.user_id is not None and record.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问")

    # 获取提取结果
    extracted_data = None
    stmt_result = select(CredentialResult).where(CredentialResult.record_id == record_id)
    res = await session.execute(stmt_result)
    cred_result = res.scalar_one_or_none()
    if cred_result:
        extracted_data = json.loads(cred_result.extracted_data)

    return CredentialRecordResponse(
        id=record.id,
        filename=record.filename,
        credential_type=record.credential_type,
        status=record.status,
        processing_duration=record.processing_duration,
        result=extracted_data,
        error_msg=record.error_msg,
    )


@router.post("/{record_id}/file")
async def get_record_file(
    record_id: int,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """获取原始文件预览"""
    statement = select(CredentialRecord).where(CredentialRecord.id == record_id)
    result = await session.execute(statement)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    if record.user_id is not None and record.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问")
    if not os.path.exists(record.file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    from urllib.parse import quote
    encoded_filename = quote(record.filename)

    # 根据扩展名判断 media type
    ext = os.path.splitext(record.filename)[-1].lower()
    media_types = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=record.file_path,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"},
    )


@router.delete("/{record_id}")
async def delete_record(
    record_id: int,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """删除凭证提取记录"""
    statement = select(CredentialRecord).where(CredentialRecord.id == record_id)
    result = await session.execute(statement)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    if record.user_id is not None and record.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问")

    # 先删除提取结果（外键约束）
    await session.execute(
        delete(CredentialResult).where(CredentialResult.record_id == record_id)
    )

    # 删除文件
    if record.file_path and os.path.exists(record.file_path):
        os.remove(record.file_path)

    await session.delete(record)
    await session.commit()
    return {"detail": "删除成功"}
