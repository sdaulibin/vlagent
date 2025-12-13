from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List, Optional
import shutil
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc

from core.database import get_session
from apps.files.models import FileRecord, TransactionRecord, SummaryRecord
from services import pdf_processor

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = "/Users/binginx/PycharmProjects/vl_flow/backend/res"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def create_transaction_records(file_id: int, raw_transactions: list) -> List[TransactionRecord]:
    """将原始交易数据转换为 TransactionRecord 对象列表"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = TransactionRecord(
            file_id=file_id,
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
        records.append(t)
    return records


def create_summary_record(file_id: int, summary_data: dict) -> Optional[SummaryRecord]:
    """将汇总数据转换为 SummaryRecord 对象"""
    if not summary_data:
        return None
    return SummaryRecord(
        file_id=file_id,
        account_name=summary_data.get("账户名称", ""),
        account_number=summary_data.get("账(卡)号", ""),
        date_range=summary_data.get("起止日期", ""),
        income_count=summary_data.get("收入总笔数", ""),
        income_total=summary_data.get("收入总金额", ""),
        expense_count=summary_data.get("支出总笔数", ""),
        expense_total=summary_data.get("支出总金额", ""),
        has_stamp=summary_data.get("是否有盖章", ""),
        bank_name=summary_data.get("开户行", ""),
        stamp_type=summary_data.get("盖章类型", "")
    )


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

        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 创建文件记录
        db_file = FileRecord(filename=file.filename, file_path=file_path, status="processing")
        session.add(db_file)
        await session.commit()
        await session.refresh(db_file)

        try:
            # 处理PDF文件
            result = pdf_processor.process_pdf_to_excel(file_path, max_workers=4)
            
            # 创建交易记录
            transactions = create_transaction_records(db_file.id, result.get("transactions", []))
            session.add_all(transactions)
            
            # 创建汇总记录
            summary = create_summary_record(db_file.id, result.get("summary"))
            if summary:
                session.add(summary)
            
            # 更新文件状态
            db_file.status = "done"
            await session.commit()
            
            return {
                "status": "success",
                "filename": file.filename,
                "file_id": db_file.id,
                "transactions": transactions,
                "summary": summary
            }

        except Exception as e_process:
            db_file.status = "failed"
            db_file.error_msg = str(e_process)
            await session.commit()
            raise e_process

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


