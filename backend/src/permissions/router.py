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
    """获取当前用户可见的模块 key 列表。

    公开模块（permission_required=False 且启用）对所有用户恒定可见；
    需权限模块仅在用户拥有授权时可见。无授权记录时按 PERMISSION_DEFAULT_OPEN 处理。
    """
    statement = select(UserPermission.module).where(
        UserPermission.user_id == user_id
    )
    result = await session.execute(statement)
    modules = [row[0] for row in result.all()]

    # 公开模块（permission_required=False 且启用）对所有用户恒定可见
    public_stmt = select(Module.key).where(
        Module.permission_required == False, Module.status == True
    )
    public_result = await session.execute(public_stmt)
    public_keys = [row[0] for row in public_result.all()]

    if not modules:
        if settings.PERMISSION_DEFAULT_OPEN:
            all_stmt = select(Module.key).where(Module.status == True)
            all_result = await session.execute(all_stmt)
            return [row[0] for row in all_result.all()]
        return public_keys

    # 已授权 ∪ 公开，去重保序
    return list(dict.fromkeys(modules + public_keys))
