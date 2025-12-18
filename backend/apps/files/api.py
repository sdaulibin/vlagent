from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List
import shutil
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc

from core.database import get_session
from apps.files.models import (
    FileRecord, 
    # 山东地方银行
    ShandongLocalSummary, ShandongLocalTransaction,
    # 光大银行
    EverbrightSummary, EverbrightTransaction,
    # 招商银行
    CmbSummary, CmbTransaction,
)
from apps.transactions.api import (
    create_shandong_transaction_records,
    create_shandong_summary_record,
    create_everbright_transaction_records,
    create_everbright_summary_record,
    create_cmb_transaction_records,
    create_cmb_summary_record,
)
from services import pdf_processor

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = "/Users/binginx/PycharmProjects/vl_flow/backend/res"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=List[FileRecord])
async def get_files(session: AsyncSession = Depends(get_session)):
    """获取所有文件列表"""
    statement = select(FileRecord).order_by(desc(FileRecord.created_at))
    result = await session.execute(statement)
    return result.scalars().all()


@router.get("/{file_id}", response_model=FileRecord)
async def get_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """获取单个文件详情"""
    statement = select(FileRecord).where(FileRecord.id == file_id)
    result = await session.execute(statement)
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    """上传文件（仅保存，不处理）"""
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)

        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 创建文件记录 - 状态为 pending（待处理）
        db_file = FileRecord(filename=file.filename, file_path=file_path, status="pending")
        session.add(db_file)
        await session.commit()
        await session.refresh(db_file)

        return {
            "status": "success",
            "filename": file.filename,
            "file_id": db_file.id,
            "message": "文件上传成功，请点击开始识别"
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{file_id}/recognize")
async def start_recognition(file_id: int, session: AsyncSession = Depends(get_session)):
    """开始识别文件内容"""
    try:
        # 获取文件记录
        result = await session.execute(select(FileRecord).where(FileRecord.id == file_id))
        db_file = result.scalar_one_or_none()
        
        if not db_file:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        if db_file.status == "done":
            return {"status": "already_done", "message": "文件已识别完成"}
        
        if db_file.status == "processing":
            return {"status": "processing", "message": "文件正在识别中"}
        
        # 更新状态为处理中
        db_file.status = "processing"
        await session.commit()

        try:
            # 提取文件内容（包含银行类型识别）
            result = pdf_processor.process_pdf_to_excel(db_file.file_path, max_workers=4)
            
            # 获取银行类型
            bank_type = result.get("bank_type", "shandong_local")
            db_file.bank_type = bank_type
            
            # 记录原始数据量
            raw_transactions = result.get("transactions", [])
            print(f"[识别结果] 银行类型: {bank_type}, 原始交易数据: {len(raw_transactions)} 条")
            
            # 根据银行类型创建对应的记录
            transactions = []
            summary = None
            
            if bank_type == "everbright":
                # 光大银行
                transactions = create_everbright_transaction_records(db_file.id, raw_transactions)
                summary = create_everbright_summary_record(db_file.id, result.get("summary"))
            elif bank_type == "cmb":
                # 招商银行
                transactions = create_cmb_transaction_records(db_file.id, raw_transactions)
                summary = create_cmb_summary_record(db_file.id, result.get("summary"))
            else:
                # 山东地方银行（默认）
                transactions = create_shandong_transaction_records(db_file.id, raw_transactions)
                summary = create_shandong_summary_record(db_file.id, result.get("summary"))
            
            print(f"[创建记录] 创建交易记录: {len(transactions)} 条")
            if len(transactions) != len(raw_transactions):
                print(f"[警告] 数据丢失! 原始: {len(raw_transactions)}, 创建: {len(transactions)}, 丢失: {len(raw_transactions) - len(transactions)}")
            
            session.add_all(transactions)
            if summary:
                session.add(summary)
            
            # 更新文件状态
            db_file.status = "done"
            await session.commit()
            
            return {
                "status": "success",
                "file_id": db_file.id,
                "bank_type": bank_type,
                "transactions_count": len(transactions),
                "has_summary": summary is not None
            }

        except Exception as e_process:
            db_file.status = "failed"
            db_file.error_msg = str(e_process)
            await session.commit()
            raise e_process

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{file_id}")
async def delete_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """删除文件及其关联的所有数据"""
    try:
        # 查询文件记录
        statement = select(FileRecord).where(FileRecord.id == file_id)
        result = await session.execute(statement)
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        
        from sqlmodel import delete
        
        # 删除山东地方银行记录
        await session.execute(
            delete(ShandongLocalTransaction).where(ShandongLocalTransaction.file_id == file_id)
        )
        await session.execute(
            delete(ShandongLocalSummary).where(ShandongLocalSummary.file_id == file_id)
        )
        
        # 删除光大银行记录
        await session.execute(
            delete(EverbrightTransaction).where(EverbrightTransaction.file_id == file_id)
        )
        await session.execute(
            delete(EverbrightSummary).where(EverbrightSummary.file_id == file_id)
        )
        
        # 删除招商银行记录
        await session.execute(
            delete(CmbTransaction).where(CmbTransaction.file_id == file_id)
        )
        await session.execute(
            delete(CmbSummary).where(CmbSummary.file_id == file_id)
        )
        
        # 删除上传的原文件
        if file_record.file_path and os.path.exists(file_record.file_path):
            os.remove(file_record.file_path)
        
        # 删除处理过程中生成的目录 (res/文件名_task_*)
        filename_base = os.path.splitext(file_record.filename)[0]
        for item in os.listdir(UPLOAD_DIR):
            item_path = os.path.join(UPLOAD_DIR, item)
            if os.path.isdir(item_path) and item.startswith(f"task_{filename_base}"):
                shutil.rmtree(item_path)
        
        # 删除文件记录
        await session.delete(file_record)
        await session.commit()
        
        return {"status": "success", "message": f"File {file_id} deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
