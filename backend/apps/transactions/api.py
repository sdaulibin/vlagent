from fastapi import APIRouter, Depends
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.database import get_session
from apps.files.models import TransactionRecord, SummaryRecord

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/{file_id}", response_model=List[TransactionRecord])
async def get_transactions(file_id: int, session: AsyncSession = Depends(get_session)):
    """获取指定文件的交易记录"""
    statement = select(TransactionRecord).where(TransactionRecord.file_id == file_id)
    result = await session.execute(statement)
    return result.scalars().all()


@router.get("/{file_id}/summary", response_model=Optional[SummaryRecord])
async def get_summary(file_id: int, session: AsyncSession = Depends(get_session)):
    """获取文件的汇总信息"""
    statement = select(SummaryRecord).where(SummaryRecord.file_id == file_id)
    result = await session.execute(statement)
    return result.scalar_one_or_none()

