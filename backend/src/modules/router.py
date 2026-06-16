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
    """获取当前用户可见的模块列表（含完整元数据）。

    可见规则：
    - 公开模块（permission_required=False）对所有用户恒定可见；
    - 需权限模块（permission_required=True）仅在用户拥有授权时可见；
    - 无授权记录时：PERMISSION_DEFAULT_OPEN=True 放行全部，否则仅返回公开模块。
    """
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
        # 仅返回公开模块
        return [m for m in all_modules if m.permission_required == False]

    # 公开模块 ∪ 已授权模块
    return [m for m in all_modules if m.permission_required == False or m.key in permitted_keys]
