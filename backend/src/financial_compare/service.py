"""
财务报告比对服务：调用结构化 LLM 比对引擎，把结果写入数据库。

引擎（compare/document/parser/table/llm 包，移植自 qdf_filediff）负责全部
解析、章节配对、三阶段比较逻辑。本模块仅做任务调度与结果持久化。

LLM 调用通过 llm/model.py::chat 适配到项目的 request_qwen35。
"""
import asyncio
import json
import logging
import time

from src.database import SessionLocal
from src.financial_compare.models import FinancialCompareTask

logger = logging.getLogger(__name__)


async def process_financial_compare(task_id: int):
    """比对任务主入口（后台任务）。

    三阶段 session 模式（参照 confirmation_compare，避免耗尽数据库连接池）：
      Phase 1: 读任务、标记 processing、关闭 session
      Phase 2: 调引擎（CPU+LLM 重活，asyncio.to_thread，不持有 DB 连接）
      Phase 3: 结果写库
    """
    t0 = time.monotonic()

    # ---- Phase 1 ----
    try:
        async with SessionLocal() as session:
            task = await session.get(FinancialCompareTask, task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            task.status = "processing"
            await session.commit()
            docx_path = task.docx_file_path
            pdf_path = task.pdf_file_path
            docx_start_page = task.docx_start_page
            docx_end_page = task.docx_end_page
            pdf_start_page = task.pdf_start_page
            pdf_end_page = task.pdf_end_page
    except Exception as e:
        logger.error(f"[FinancialCompare] Phase 1 failed for task {task_id}: {e}")
        return

    # ---- Phase 2: 调引擎 ----
    try:
        def _run_engine():
            from financial_compare.app_config import init_app_config, OUTPUT_TASKS
            init_app_config()
            from financial_compare.main_service import MainService
            from financial_compare.parser.page_range import PageRange

            svc = MainService(
                task_id=f"fc_{task_id}",
                tasks_dir=str(OUTPUT_TASKS),
                enable_logging=True,
            )
            page_range = PageRange.from_sides(
                start_a=docx_start_page,
                end_a=docx_end_page,
                start_b=pdf_start_page,
                end_b=pdf_end_page,
            )
            return svc.compare_files(docx_path, pdf_path, page_range=page_range)

        result = await asyncio.to_thread(_run_engine)
        duration = time.monotonic() - t0
        logger.info(
            f"[FinancialCompare] Task {task_id}: 引擎比对完成, 耗时{duration:.1f}s, "
            f"content_diffs={len(result.get('content_diffs', []))}, "
            f"table_anchor_diffs={len(result.get('table_anchor_diffs', []))}"
        )
    except Exception as e:
        logger.error(f"[FinancialCompare] Phase 2 failed for task {task_id}: {e}")
        import traceback
        traceback.print_exc()
        async with SessionLocal() as session:
            task = await session.get(FinancialCompareTask, task_id)
            if task:
                task.status = "failed"
                task.error_msg = str(e)
                task.duration = time.monotonic() - t0
                await session.commit()
        return

    # ---- Phase 3: 从引擎快照读 DiffRecord，写库 ----
    try:
        # 引擎把每条差异以 DiffRecord 格式写入 diffs.jsonl（带 diff_id/kind/scope/loc/payload）。
        # 这是前端期望的格式。注意不要用 result["content_diffs"]（那是节级汇总，不是差异条目）。
        from financial_compare.app_config import OUTPUT_TASKS
        import os
        diffs_jsonl_path = os.path.join(str(OUTPUT_TASKS), f"fc_{task_id}", "diffs.jsonl")
        diff_records: list[dict] = []
        if os.path.exists(diffs_jsonl_path):
            with open(diffs_jsonl_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        diff_records.append(json.loads(line))

        stats = {
            "total_diffs": len(diff_records),
            "content_diffs": len(result.get("content_diffs", [])),
            "table_anchor_diffs": len(result.get("table_anchor_diffs", [])),
            "missing_titles_a": len(result.get("missing_titles_a", [])),
            "missing_titles_b": len(result.get("missing_titles_b", [])),
        }

        async with SessionLocal() as session:
            task = await session.get(FinancialCompareTask, task_id)
            if not task:
                return
            task.status = "done"
            task.duration = duration
            task.diff_stats = json.dumps(stats, ensure_ascii=False)
            task.diff_blocks = json.dumps(diff_records, ensure_ascii=False)
            await session.commit()
    except Exception as e:
        logger.error(f"[FinancialCompare] Phase 3 failed for task {task_id}: {e}")
