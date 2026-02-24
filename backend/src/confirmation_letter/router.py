"""
询证函 API 路由

独立的 API 端点，不与银行流水识别共用。
"""
import os
import json
import shutil
import time
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc

from src.database import get_session
from src.confirmation_letter.models import (
    ConfirmationFile,
    ConfirmationResult,
    ConfirmationResultUpdate,
    ConfirmationFileDTO,
    ConfirmationRecognitionDTO,
    FormatMismatch,
)
from src.confirmation_letter.service import process_confirmation_letter


router = APIRouter(prefix="/confirmation", tags=["confirmation_letter"])

# 配置上传目录
UPLOAD_DIR = os.getenv("CONFIRMATION_UPLOAD_DIR", 
                       os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "res", "confirmation"))
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


def _parse_mismatches(raw_json: str | None) -> List[FormatMismatch]:
    if not raw_json:
        return []
    try:
        data = json.loads(raw_json)
        if isinstance(data, list):
            return [FormatMismatch(**item) for item in data if isinstance(item, dict)]
    except Exception:
        return []
    return []


def _to_recognition_dto(recognition: ConfirmationResult | None) -> ConfirmationRecognitionDTO | None:
    if not recognition:
        return None
    return ConfirmationRecognitionDTO(
        id=recognition.id,
        file_id=recognition.file_id,
        confirmation_no=recognition.confirmation_no,
        accounting_firm=recognition.accounting_firm,
        reply_address=recognition.reply_address,
        contact_person=recognition.contact_person,
        phone=recognition.phone,
        postal_code=recognition.postal_code,
        debit_account=recognition.debit_account,
        cutoff_date=recognition.cutoff_date,
        start_date=recognition.start_date,
        end_date=recognition.end_date,
        seal_date=recognition.seal_date,
        seal_name=recognition.seal_name,
        signature_name=recognition.signature_name,
        format_type=recognition.format_type,
        format_check_passed=recognition.format_check_passed,
        format_mismatches=_parse_mismatches(recognition.format_mismatches_json),
        created_at=recognition.created_at,
        updated_at=recognition.updated_at,
    )


def _to_file_dto(file_obj: ConfirmationFile, rec_obj: ConfirmationResult | None) -> ConfirmationFileDTO:
    return ConfirmationFileDTO(
        id=file_obj.id,
        filename=file_obj.filename,
        status=file_obj.status,
        error_msg=file_obj.error_msg,
        recognition_duration=file_obj.recognition_duration,
        created_at=file_obj.created_at,
        updated_at=file_obj.updated_at,
        recognition=_to_recognition_dto(rec_obj),
    )


@router.get("", response_model=List[ConfirmationFileDTO])
async def get_confirmation_files(session: AsyncSession = Depends(get_session)):
    """获取所有询证函文件记录"""
    statement = (
        select(ConfirmationFile, ConfirmationResult)
        .outerjoin(ConfirmationResult, ConfirmationResult.file_id == ConfirmationFile.id)
        .order_by(desc(ConfirmationFile.created_at))
    )
    result = await session.execute(statement)
    rows = result.all()

    # 组装文件 + 识别结果（单次查询，避免 N+1）
    response_map = {}
    for file_obj, rec_obj in rows:
        if file_obj.id in response_map:
            continue
        response_map[file_obj.id] = _to_file_dto(file_obj, rec_obj)

    return list(response_map.values())


@router.get("/{file_id}", response_model=ConfirmationFileDTO)
async def get_confirmation_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """获取单个询证函详情（文件 + 识别结果）"""
    statement = select(ConfirmationFile).where(ConfirmationFile.id == file_id)
    result = await session.execute(statement)
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="询证函记录不存在")
    
    # 查询关联的识别结果
    res_stmt = select(ConfirmationResult).where(ConfirmationResult.file_id == file_id)
    res_result = await session.execute(res_stmt)
    recognition = res_result.scalar_one_or_none()
    return _to_file_dto(file, recognition)


@router.get("/{file_id}/file")
async def preview_confirmation_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """预览询证函原始文件"""
    statement = select(ConfirmationFile).where(ConfirmationFile.id == file_id)
    result = await session.execute(statement)
    file_obj = result.scalar_one_or_none()
    if not file_obj:
        raise HTTPException(status_code=404, detail="询证函记录不存在")
    if not os.path.exists(file_obj.file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    from urllib.parse import quote
    encoded_filename = quote(file_obj.filename)
    return FileResponse(
        path=file_obj.file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"},
    )


@router.post("/upload")
async def upload_confirmation_file(
    file: UploadFile = File(...), 
    session: AsyncSession = Depends(get_session)
):
    """上传询证函文件"""
    try:
        # 验证文件格式
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="仅支持 PDF 格式文件")
        
        file_path = _build_safe_upload_path(UPLOAD_DIR, file.filename)
        
        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 创建文件记录
        conf_file = ConfirmationFile(filename=file.filename, file_path=file_path)
        session.add(conf_file)
        await session.commit()
        await session.refresh(conf_file)
        
        return {
            "status": "success",
            "file_id": conf_file.id,
            "filename": file.filename,
            "message": "询证函上传成功，请点击开始识别"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{file_id}/recognize")
async def recognize_confirmation_file(
    file_id: int, 
    session: AsyncSession = Depends(get_session)
):
    """识别询证函字段"""
    try:
        # 获取文件记录
        result = await session.execute(
            select(ConfirmationFile).where(ConfirmationFile.id == file_id)
        )
        conf_file = result.scalar_one_or_none()
        
        if not conf_file:
            raise HTTPException(status_code=404, detail="询证函记录不存在")
        
        if conf_file.status == "done":
            return {"status": "already_done", "message": "已识别完成"}
        
        if conf_file.status == "processing":
            return {"status": "processing", "message": "正在识别中"}
        
        # 更新状态
        conf_file.status = "processing"
        await session.commit()
        
        start_time = time.time()
        
        try:
            # 执行识别
            recognition_result = await run_in_threadpool(
                process_confirmation_letter, 
                conf_file.file_path
            )
            
            # 删除旧的识别结果（如果有）
            old_result = await session.execute(
                select(ConfirmationResult).where(ConfirmationResult.file_id == file_id)
            )
            old = old_result.scalar_one_or_none()
            if old:
                await session.delete(old)
            
            # 创建新的识别结果记录
            conf_result = ConfirmationResult(
                file_id=file_id,
                confirmation_no=recognition_result.get("confirmation_no", ""),
                accounting_firm=recognition_result.get("accounting_firm", ""),
                reply_address=recognition_result.get("reply_address", ""),
                contact_person=recognition_result.get("contact_person", ""),
                phone=recognition_result.get("phone", ""),
                postal_code=recognition_result.get("postal_code", ""),
                debit_account=recognition_result.get("debit_account", ""),
                cutoff_date=recognition_result.get("cutoff_date", ""),
                start_date=recognition_result.get("start_date", ""),
                end_date=recognition_result.get("end_date", ""),
                seal_date=recognition_result.get("seal_date", ""),
                seal_name=recognition_result.get("seal_name", ""),
                signature_name=recognition_result.get("signature_name", ""),
                format_type=recognition_result.get("format_type", "unknown"),
                format_check_passed=recognition_result.get("format_check_passed", False),
                format_mismatches_json=json.dumps(
                    recognition_result.get("format_mismatches", []),
                    ensure_ascii=False,
                ),
            )
            session.add(conf_result)
            
            # 更新文件状态
            conf_file.status = "done"
            conf_file.recognition_duration = round((time.time() - start_time) * 1000, 2)
            conf_file.updated_at = datetime.utcnow()
            
            await session.commit()
            
            return {
                "status": "success",
                "file_id": conf_file.id,
                "recognition_duration_ms": conf_file.recognition_duration,
                "result": recognition_result
            }
            
        except Exception as e:
            conf_file.status = "failed"
            conf_file.error_msg = str(e)
            await session.commit()
            raise
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{file_id}/result")
async def update_confirmation_result(
    file_id: int, 
    data: ConfirmationResultUpdate,
    session: AsyncSession = Depends(get_session)
):
    """人工修改识别结果"""
    # 检查文件是否存在
    file_result = await session.execute(
        select(ConfirmationFile).where(ConfirmationFile.id == file_id)
    )
    if not file_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="询证函记录不存在")
    
    # 查询识别结果
    result = await session.execute(
        select(ConfirmationResult).where(ConfirmationResult.file_id == file_id)
    )
    conf_result = result.scalar_one_or_none()
    
    if not conf_result:
        # 如果没有识别结果，创建一个新的
        conf_result = ConfirmationResult(file_id=file_id)
        session.add(conf_result)
    
    # 更新非空字段
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(conf_result, field, value)
    
    conf_result.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(conf_result)
    
    return {"status": "success", "result": conf_result}


@router.delete("/{file_id}")
async def delete_confirmation_file(
    file_id: int, 
    session: AsyncSession = Depends(get_session)
):
    """删除询证函文件及关联的识别结果"""
    result = await session.execute(
        select(ConfirmationFile).where(ConfirmationFile.id == file_id)
    )
    conf_file = result.scalar_one_or_none()
    
    if not conf_file:
        raise HTTPException(status_code=404, detail="询证函记录不存在")
    
    cleaned = []
    
    # 1. 删除关联的识别结果
    res_result = await session.execute(
        select(ConfirmationResult).where(ConfirmationResult.file_id == file_id)
    )
    conf_result = res_result.scalar_one_or_none()
    if conf_result:
        await session.delete(conf_result)
        await session.flush()  # 先刷新，确保子表记录先删除，避免外键约束冲突
        cleaned.append(f"识别结果: result_id={conf_result.id}")
    
    # 2. 删除上传的 PDF 文件
    if conf_file.file_path and os.path.exists(conf_file.file_path):
        os.remove(conf_file.file_path)
        cleaned.append(f"PDF: {conf_file.file_path}")
    
    # 3. 清理可能存在的临时图片目录
    if conf_file.file_path:
        pdf_dir = os.path.dirname(conf_file.file_path)
        base_name = os.path.splitext(os.path.basename(conf_file.file_path))[0]
        
        temp_patterns = [
            f"task_{base_name}_images",
            f"_tmp_images",
        ]
        for pattern in temp_patterns:
            temp_dir = os.path.join(pdf_dir, pattern)
            if os.path.exists(temp_dir) and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                cleaned.append(f"临时目录: {temp_dir}")
    
    # 4. 删除文件记录
    await session.delete(conf_file)
    await session.commit()
    cleaned.append(f"文件记录: id={file_id}")
    
    return {
        "status": "success", 
        "message": f"询证函 {file_id} 已完全删除",
        "cleaned": cleaned
    }
