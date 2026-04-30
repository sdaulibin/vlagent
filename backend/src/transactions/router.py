"""
交易相关 API 路由

使用策略模式通过银行处理器动态分发请求。
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_
from sqlmodel import select

from src.auth import get_current_user_id
from src.database import get_session
from src.files.models import FileRecord
from src.banks import get_bank_handler

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/{file_id}")
async def get_transactions(
    file_id: int,
    summary_id: int = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """获取指定文件的交易记录（根据银行类型从对应表查询）"""
    file_stmt = select(FileRecord).where(
        FileRecord.id == file_id,
        or_(FileRecord.user_id == user_id, FileRecord.user_id.is_(None)),
    )
    file_result = await session.execute(file_stmt)
    file_record = file_result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    bank_type = file_record.bank_type or "shandong_local"
    handler = get_bank_handler(bank_type)
    if not handler:
        raise HTTPException(status_code=400, detail=f"Unsupported bank type: {bank_type}")

    return await handler.get_transactions(session, file_id, summary_id)


@router.post("/{file_id}/summary")
async def get_summary(
    file_id: int,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> Optional[dict | List[dict]]:
    """获取文件的汇总信息（根据银行类型从对应表查询）"""
    file_stmt = select(FileRecord).where(
        FileRecord.id == file_id,
        or_(FileRecord.user_id == user_id, FileRecord.user_id.is_(None)),
    )
    file_result = await session.execute(file_stmt)
    file_record = file_result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    bank_type = file_record.bank_type or "shandong_local"
    handler = get_bank_handler(bank_type)
    if not handler:
        raise HTTPException(status_code=400, detail=f"Unsupported bank type: {bank_type}")

    return await handler.get_summary(session, file_id)
