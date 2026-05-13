import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import SessionLocal, UpstreamSessionLocal
from src.modules.models import Module
from src.permissions.models import UserPermission

logger = logging.getLogger(__name__)

VLAGENT_AGENT_ID = 46


async def sync_permissions() -> dict:
    """从上游 sys_user 同步用户权限到本地 user_permissions 表。"""
    if not UpstreamSessionLocal:
        logger.info("权限同步跳过: 上游数据库未配置")
        return {"status": "skipped", "reason": "上游数据库未配置"}

    logger.info("[权限同步] 开始同步 sys_user → user_permissions")

    # 1. 获取本地 modules 的 agent_id 集合
    async with SessionLocal() as session:
        result = await session.execute(
            select(Module.key, Module.agent_id).where(Module.agent_id.is_not(None))
        )
        agent_id_to_key = {row.agent_id: row.key for row in result.all()}

    if not agent_id_to_key:
        logger.warning("[权限同步] 跳过: 本地 modules 无 agent_id 映射")
        return {"status": "skipped", "reason": "no agent_id mapping"}

    valid_agent_ids = set(agent_id_to_key.keys())
    logger.info("[权限同步] 本地 modules agent_id 集合: %s", valid_agent_ids)

    # 2. 从上游获取活跃用户
    async with UpstreamSessionLocal() as upstream:
        rows = await upstream.execute(text(
            "SELECT user_id, agent FROM sys_user "
            "WHERE deleted_at IS NULL AND status = true"
        ))
        users = rows.mappings().all()

    logger.info("[权限同步] 上游活跃用户: %d 人", len(users))

    # 3. 计算权限映射
    new_permissions: list[tuple[str, str]] = []
    skipped_no_vlagent = 0
    skipped_no_modules = 0

    for user in users:
        agent_array = user["agent"] or []
        # 与子模块 id 取交集，映射为 module key
        user_agent_ids = set(agent_array) & valid_agent_ids
        if not user_agent_ids:
            skipped_no_modules += 1
            logger.debug("[权限同步] 用户 %s 含 vlagent 主入口但无子模块权限", user["user_id"])
            continue
        for aid in user_agent_ids:
            key = agent_id_to_key.get(aid)
            if key:
                new_permissions.append((user["user_id"], key))

    affected_users = {p[0] for p in new_permissions}
    logger.info("[权限同步] 有效用户: %d 人 (跳过: 无子模块=%d)",
                len(affected_users), skipped_no_modules)

    for uid in sorted(affected_users):
        user_keys = [k for u, k in new_permissions if u == uid]
        logger.info("[权限同步] 用户 %s → %s", uid, user_keys)

    stats = {"users": len(affected_users), "permissions": len(new_permissions)}

    # 4. 全量替换 user_permissions（事务）
    async with SessionLocal() as session:
        async with session.begin():
            # 查询旧权限数量
            old_count = (await session.execute(
                select(UserPermission)
            )).scalars().all()
            old_count = len(old_count)

            await session.execute(text("DELETE FROM user_permissions"))
            for user_id, module_key in new_permissions:
                session.add(UserPermission(user_id=user_id, module=module_key))
        await session.commit()

    logger.info("[权限同步] 完成: 旧权限=%d条 → 新权限=%d条, 涉及用户=%d人",
                old_count, stats["permissions"], stats["users"])
    return {"status": "ok", **stats}
