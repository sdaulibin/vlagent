"""
询证函 API 路由

独立的 API 端点，不与银行流水识别共用。
"""
import os
import shutil
import time
import asyncio
from datetime import datetime
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc

from src.database import get_session
from src.confirmation_letter.models import ConfirmationLetter, ConfirmationLetterUpdate
from src.confirmation_letter.service import process_confirmation_letter


router = APIRouter(prefix="/confirmation", tags=["confirmation_letter"])

# 配置上传目录
UPLOAD_DIR = os.getenv("CONFIRMATION_UPLOAD_DIR", 
                       os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "res", "confirmation"))
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=List[ConfirmationLetter])
async def get_confirmation_letters(session: AsyncSession = Depends(get_session)):
    """获取所有询证函记录"""
    statement = select(ConfirmationLetter).order_by(desc(ConfirmationLetter.created_at))
    result = await session.execute(statement)
    return result.scalars().all()


@router.get("/{letter_id}", response_model=ConfirmationLetter)
async def get_confirmation_letter(letter_id: int, session: AsyncSession = Depends(get_session)):
    """获取单个询证函详情"""
    statement = select(ConfirmationLetter).where(ConfirmationLetter.id == letter_id)
    result = await session.execute(statement)
    letter = result.scalar_one_or_none()
    if not letter:
        raise HTTPException(status_code=404, detail="询证函记录不存在")
    return letter


@router.post("/upload")
async def upload_confirmation_letter(
    file: UploadFile = File(...), 
    session: AsyncSession = Depends(get_session)
):
    """上传询证函文件"""
    try:
        # 验证文件格式
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="仅支持 PDF 格式文件")
        
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        
        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 创建记录
        letter = ConfirmationLetter(filename=file.filename, file_path=file_path)
        session.add(letter)
        await session.commit()
        await session.refresh(letter)
        
        return {
            "status": "success",
            "letter_id": letter.id,
            "filename": file.filename,
            "message": "询证函上传成功，请点击开始识别"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{letter_id}/recognize")
async def recognize_confirmation_letter(
    letter_id: int, 
    session: AsyncSession = Depends(get_session)
):
    """识别询证函字段"""
    try:
        # 获取记录
        result = await session.execute(
            select(ConfirmationLetter).where(ConfirmationLetter.id == letter_id)
        )
        letter = result.scalar_one_or_none()
        
        if not letter:
            raise HTTPException(status_code=404, detail="询证函记录不存在")
        
        if letter.status == "done":
            return {"status": "already_done", "message": "已识别完成"}
        
        if letter.status == "processing":
            return {"status": "processing", "message": "正在识别中"}
        
        # 更新状态
        letter.status = "processing"
        await session.commit()
        
        start_time = time.time()
        
        try:
            # 执行识别
            recognition_result = await run_in_threadpool(
                process_confirmation_letter, letter.file_path
            )
            
            # 更新识别结果
            letter.confirmation_no = recognition_result.get("confirmation_no", "")
            letter.accounting_firm = recognition_result.get("accounting_firm", "")
            letter.reply_address = recognition_result.get("reply_address", "")
            letter.contact_person = recognition_result.get("contact_person", "")
            letter.phone = recognition_result.get("phone", "")
            letter.postal_code = recognition_result.get("postal_code", "")
            letter.debit_account = recognition_result.get("debit_account", "")
            letter.cutoff_date = recognition_result.get("cutoff_date", "")
            letter.start_date = recognition_result.get("start_date", "")
            letter.end_date = recognition_result.get("end_date", "")
            letter.seal_date = recognition_result.get("seal_date", "")
            letter.seal_name = recognition_result.get("seal_name", "")
            
            letter.status = "done"
            letter.recognition_duration = round((time.time() - start_time) * 1000, 2)
            letter.updated_at = datetime.utcnow()
            
            await session.commit()
            
            return {
                "status": "success",
                "letter_id": letter.id,
                "recognition_duration_ms": letter.recognition_duration,
                "result": recognition_result
            }
            
        except Exception as e:
            letter.status = "failed"
            letter.error_msg = str(e)
            await session.commit()
            raise
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{letter_id}")
async def update_confirmation_letter(
    letter_id: int, 
    data: ConfirmationLetterUpdate,
    session: AsyncSession = Depends(get_session)
):
    """人工修改识别结果"""
    result = await session.execute(
        select(ConfirmationLetter).where(ConfirmationLetter.id == letter_id)
    )
    letter = result.scalar_one_or_none()
    
    if not letter:
        raise HTTPException(status_code=404, detail="询证函记录不存在")
    
    # 更新非空字段
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(letter, field, value)
    
    letter.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(letter)
    
    return {"status": "success", "letter": letter}


@router.delete("/{letter_id}")
async def delete_confirmation_letter(
    letter_id: int, 
    session: AsyncSession = Depends(get_session)
):
    """删除询证函记录及所有关联文件"""
    result = await session.execute(
        select(ConfirmationLetter).where(ConfirmationLetter.id == letter_id)
    )
    letter = result.scalar_one_or_none()
    
    if not letter:
        raise HTTPException(status_code=404, detail="询证函记录不存在")
    
    cleaned = []
    
    # 1. 删除上传的 PDF 文件
    if letter.file_path and os.path.exists(letter.file_path):
        os.remove(letter.file_path)
        cleaned.append(f"PDF: {letter.file_path}")
    
    # 2. 删除 PDF 转图片过程中生成的临时目录
    #    split_pdf_to_images / pdf_to_images 生成的目录格式：task_{basename}_images
    if letter.file_path:
        pdf_dir = os.path.dirname(letter.file_path)
        base_name = os.path.splitext(os.path.basename(letter.file_path))[0]
        
        # 清理可能存在的临时图片目录
        temp_patterns = [
            f"task_{base_name}_images",         # pdf_to_images 生成
            f"_tmp_images",                      # 测试脚本生成
        ]
        for pattern in temp_patterns:
            temp_dir = os.path.join(pdf_dir, pattern)
            if os.path.exists(temp_dir) and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                cleaned.append(f"临时目录: {temp_dir}")
    
    # 3. 删除数据库记录
    await session.delete(letter)
    await session.commit()
    cleaned.append(f"数据库记录: id={letter_id}")
    
    return {
        "status": "success", 
        "message": f"询证函 {letter_id} 已完全删除",
        "cleaned": cleaned
    }

