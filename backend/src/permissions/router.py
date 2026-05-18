from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.auth import get_current_user_id
from src.config import settings
from src.database import get_session
from src.modules.models import Module
from src.permissions.models import UserPermission

router = APIRouter(prefix="/permissions", tags=["权限管理"])


@router.get("/me")
async def get_my_permissions(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户的模块权限列表，无记录时根据 PERMISSION_DEFAULT_OPEN 配置决定返回全部或空列表"""
    statement = select(UserPermission.module).where(
        UserPermission.user_id == user_id
    )
    result = await session.execute(statement)
    modules = [row[0] for row in result.all()]

    if not modules:
        if settings.PERMISSION_DEFAULT_OPEN:
            all_stmt = select(Module.key).where(Module.status == True)
            all_result = await session.execute(all_stmt)
            return [row[0] for row in all_result.all()]
        return []

    return modules
