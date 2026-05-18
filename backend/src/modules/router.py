from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.auth import get_current_user_id
from src.config import settings
from src.database import get_session
from src.modules.models import Module
from src.permissions.models import UserPermission

router = APIRouter(prefix="/modules", tags=["模块管理"])


@router.get("")
async def get_modules(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户有权限的模块列表（含完整元数据），无权限记录时根据配置决定返回全部或空列表"""
    # 查询用户权限
    perm_stmt = select(UserPermission.module).where(
        UserPermission.user_id == user_id
    )
    perm_result = await session.execute(perm_stmt)
    permitted_keys = [row[0] for row in perm_result.all()]

    # 查询所有启用的模块
    module_stmt = (
        select(Module)
        .where(Module.status == True)
        .order_by(Module.sort_order)
    )
    result = await session.execute(module_stmt)
    all_modules = result.scalars().all()

    if not permitted_keys:
        if settings.PERMISSION_DEFAULT_OPEN:
            return all_modules
        return []

    return [m for m in all_modules if m.key in permitted_keys]
