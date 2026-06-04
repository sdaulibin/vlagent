import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import settings
from src.database import SessionLocal, UpstreamSessionLocal
from src.sync.sync_modules import sync_modules
from src.sync.sync_permissions import sync_permissions

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

# Advisory Lock 标识（全局唯一，用于同步任务互斥）
_SYNC_LOCK_ID = 20260604


async def _try_advisory_lock() -> bool:
    """尝试获取 PostgreSQL Advisory Lock（非阻塞）。

    Returns:
        True = 获取成功，当前 worker 执行同步
        False = 其他 worker/Pod 正在执行同步，跳过
    """
    async with SessionLocal() as session:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT pg_try_advisory_lock(:id)"), {"id": _SYNC_LOCK_ID}
        )
        acquired = result.scalar()
        return bool(acquired)


async def _release_advisory_lock():
    """释放 PostgreSQL Advisory Lock。"""
    try:
        async with SessionLocal() as session:
            from sqlalchemy import text
            await session.execute(
                text("SELECT pg_advisory_unlock(:id)"), {"id": _SYNC_LOCK_ID}
            )
    except Exception:
        pass  # 连接断开时锁会自动释放


async def run_sync():
    """执行一次完整同步：先模块，再权限。

    通过 PostgreSQL Advisory Lock 确保整个集群（所有 Pod、所有 worker）
    同一时刻只有一个实例执行同步。
    """
    acquired = await _try_advisory_lock()
    if not acquired:
        logger.info("同步锁已被其他 worker/Pod 持有，跳过本次同步")
        return

    try:
        logger.info("开始上游数据同步（已获取 Advisory Lock）")
        mod_result = await sync_modules()
        perm_result = await sync_permissions()
        logger.info("上游数据同步完成: modules=%s, permissions=%s", mod_result, perm_result)
    except Exception:
        logger.exception("上游数据同步异常")
    finally:
        await _release_advisory_lock()


def start_scheduler():
    """启动定时同步调度器。所有 worker 都启动调度器，
    但通过 PG Advisory Lock 保证同一时刻只有一个执行同步。"""
    global _scheduler

    if not UpstreamSessionLocal:
        logger.info("上游数据库未配置，跳过定时同步")
        return

    if not settings.DATABASE_UPSTREAM_URL:
        return

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_sync,
        "interval",
        minutes=settings.SYNC_INTERVAL_MINUTES,
        id="upstream_sync",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("定时同步已启动，间隔 %d 分钟（Advisory Lock 互斥）", settings.SYNC_INTERVAL_MINUTES)


def stop_scheduler():
    """停止定时同步调度器。"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("定时同步已停止")
