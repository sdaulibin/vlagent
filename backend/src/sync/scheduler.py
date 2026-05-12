import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import settings
from src.database import UpstreamSessionLocal
from src.sync.sync_modules import sync_modules
from src.sync.sync_permissions import sync_permissions

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def run_sync():
    """执行一次完整同步：先模块，再权限。"""
    try:
        logger.info("开始上游数据同步")
        mod_result = await sync_modules()
        perm_result = await sync_permissions()
        logger.info("上游数据同步完成: modules=%s, permissions=%s", mod_result, perm_result)
    except Exception:
        logger.exception("上游数据同步异常")


def start_scheduler():
    """启动定时同步调度器。"""
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
    logger.info("定时同步已启动，间隔 %d 分钟", settings.SYNC_INTERVAL_MINUTES)


def stop_scheduler():
    """停止定时同步调度器。"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("定时同步已停止")
