import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import SessionLocal, UpstreamSessionLocal
from src.modules.models import Module

logger = logging.getLogger(__name__)

# vlagent 在上游 hi_agent_list 中的主入口 id
VLAGENT_AGENT_ID = 46


async def sync_modules() -> dict:
    """从上游 hi_agent_list(pid=46) 同步模块到本地 modules 表。"""
    if not UpstreamSessionLocal:
        logger.info("模块同步跳过: 上游数据库未配置")
        return {"status": "skipped", "reason": "上游数据库未配置"}

    logger.info("[模块同步] 开始同步 hi_agent_list(pid=%d) → modules", VLAGENT_AGENT_ID)
    stats = {"updated": 0, "created": 0, "disabled": 0}

    async with UpstreamSessionLocal() as upstream:
        rows = await upstream.execute(text(
            "SELECT id, name, description, sorting, is_show, is_delete "
            "FROM hi_agent_list WHERE pid = :pid AND is_delete = false"
        ), {"pid": VLAGENT_AGENT_ID})
        upstream_agents = rows.mappings().all()

    logger.info("[模块同步] 上游查询到 %d 条子模块记录", len(upstream_agents))

    async with SessionLocal() as session:
        # 查询本地所有模块
        result = await session.execute(select(Module))
        all_modules = result.scalars().all()
        logger.info("[模块同步] 本地 modules 表共 %d 条记录", len(all_modules))

        # 构建 agent_id → Module 索引
        local_modules = {m.agent_id: m for m in all_modules if m.agent_id is not None}
        # 同时构建 title → Module 索引（用于首次绑定 agent_id，去除空格匹配）
        title_to_module = {m.title.replace(" ", ""): m for m in all_modules}

        matched_agent_ids = set()

        for agent in upstream_agents:
            agent_id = agent["id"]
            matched_agent_ids.add(agent_id)
            # 仅根据 is_delete 判断状态（上游 is_show=0 是默认值，不代表禁用）
            is_active = not agent["is_delete"]

            # 优先按 agent_id 匹配
            mod = local_modules.get(agent_id)
            match_mode = "agent_id"

            # 首次同步：按 title 匹配并绑定 agent_id
            if mod is None:
                mod = title_to_module.get(agent["name"].replace(" ", ""))
                match_mode = "title"
                if mod and mod.agent_id is None:
                    logger.info("[模块同步] 首次绑定: agent_id=%d → module key=%r (title=%r)",
                                agent_id, mod.key, agent["name"])

            if mod is None:
                logger.warning("[模块同步] 跳过: 上游 agent id=%d name=%r 无匹配本地 module",
                               agent_id, agent["name"])
                continue

            # 更新上游管制的字段
            changes = []
            if mod.title != agent["name"]:
                changes.append(f"title: {mod.title!r}→{agent['name']!r}")
                mod.title = agent["name"]
            if agent["description"] and mod.description != agent["description"]:
                changes.append(f"description 已更新")
                mod.description = agent["description"]
            if mod.sort_order != (agent["sorting"] or 0):
                changes.append(f"sort_order: {mod.sort_order}→{agent['sorting'] or 0}")
                mod.sort_order = agent["sorting"] or 0
            if mod.status != is_active:
                changes.append(f"status: {mod.status}→{is_active}")
                mod.status = is_active
            if mod.agent_id != agent_id:
                changes.append(f"agent_id: {mod.agent_id}→{agent_id}")
                mod.agent_id = agent_id

            if changes:
                stats["updated"] += 1
                logger.info("[模块同步] 更新 module key=%r (匹配方式=%s): %s",
                            mod.key, match_mode, "; ".join(changes))

        # 上游已删除的模块 → 标记为不可用
        result = await session.execute(select(Module).where(Module.agent_id.is_not(None)))
        for mod in result.scalars().all():
            if mod.agent_id not in matched_agent_ids and mod.status:
                mod.status = False
                stats["disabled"] += 1
                logger.info("[模块同步] 禁用: module key=%r agent_id=%d (上游已删除)",
                            mod.key, mod.agent_id)

        await session.commit()

    logger.info("[模块同步] 完成: updated=%d, created=%d, disabled=%d",
                stats["updated"], stats["created"], stats["disabled"])
    return {"status": "ok", **stats}
