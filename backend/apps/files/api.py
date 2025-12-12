from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List
import shutil
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc

from core.database import get_session
from apps.files.models import FileRecord, TransactionRecord
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
    """上传并处理PDF文件"""
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)

        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Create File Record
        db_file = FileRecord(
            filename=file.filename,
            file_path=file_path,
            status="processing"
        )
        session.add(db_file)
        await session.commit()
        await session.refresh(db_file)

        try:
            # Process the file
            raw_transactions = pdf_processor.process_pdf_to_excel(file_path, max_workers=4)

            transactions_to_add = []
            
            for idx, item in enumerate(raw_transactions):
                t = TransactionRecord(
                    file_id=db_file.id,
                    sequence=str(item.get("序号", idx + 1)),
                    transaction_time=item.get("交易时间", ""),
                    channel=item.get("交易渠道", ""),
                    income=item.get("收入", ""),
                    expense=item.get("支出", ""),
                    balance=item.get("账户余额", ""),
                    currency=item.get("币种", ""),
                    counterparty_account=item.get("对方账号", ""),
                    counterparty_name=item.get("对方户名", ""),
                    description=item.get("摘要备注", "")
                )
                transactions_to_add.append(t)
            
            # Batch add transactions
            session.add_all(transactions_to_add)
            
            # Update File Status
            db_file.status = "done"
            session.add(db_file)
            
            await session.commit()
            
            return {
                "status": "success",
                "filename": file.filename,
                "file_id": db_file.id,
                "transactions": transactions_to_add
            }

        except Exception as e_process:
            db_file.status = "failed"
            db_file.error_msg = str(e_process)
            session.add(db_file)
            await session.commit()
            raise e_process

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
