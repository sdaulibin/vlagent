"""简繁母本驱动对齐：编排三阶段 compare 流水线。"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from financial_compare.compare.models.node import RemainderPool
from financial_compare.compare.models.result import ResidualTextCompareResult, SectionCompareResult, TableAnchorCompareResult
from financial_compare.compare.phases.residual_text import ResidualTextComparePhase
from financial_compare.compare.phases.section_compare import SectionComparePhase
from financial_compare.compare.phases.table_anchor import TableAnchorComparePhase
from financial_compare.app_config import OUTPUT_LOGS, OUTPUT_TASKS
from financial_compare.compare.services.compare_context import CompareContext
from financial_compare.compare.llm.client import CompareLlmClient
from financial_compare.compare.snapshot import FileSnapshotHooks, TaskSnapshotStore
from financial_compare.document.toc import AnchorCandidate, TocEntry
from financial_compare.document.tree import DocumentNode, count_nodes, iter_content_items
from financial_compare.document.types import StructuredDocument
from financial_compare.parser.io.serde import PARSED_VERSION, validate_parsed_json_file

_LOGGER_NAME = "qdb_filediff.compare"


class SimplifiedTraditionalCompare:
    """Compare 编排入口：只读树 + 三阶段分步调用（不做 dedup / TOC 虚拟 / retag）。"""

    def __init__(
        self,
        *,
        enable_logging: bool = True,
        log_level: str = "INFO",
        log_file: str | None = None,
        preview_chars: int = 120,
        view_budget: int = 2400,
        task_id: str | None = None,
        tasks_dir: str | Path | None = None,
        resume: bool = False,
        parsed_path_a: str | Path | None = None,
        parsed_path_b: str | Path | None = None,
    ) -> None:
        self._enable_logging = enable_logging
        self._preview_chars = preview_chars
        self._view_budget = max(256, view_budget)
        self._task_id = task_id
        self._resume = resume
        self._parsed_path_a = Path(parsed_path_a) if parsed_path_a else None
        self._parsed_path_b = Path(parsed_path_b) if parsed_path_b else None
        self._tasks_dir = Path(tasks_dir) if tasks_dir else OUTPUT_TASKS
        self._logger = self._build_logger(level=log_level, log_file=log_file)
        self._llm = CompareLlmClient(
            log_info=self._log_info,
            short_text=self._short_text,
        )

    def compare(self, doc_a: StructuredDocument, doc_b: StructuredDocument) -> dict[str, Any]:
        t0 = time.perf_counter()
        root_a = doc_a.root
        root_b = doc_b.root
        dedup_stats_a = doc_a.dedup_stats or {"removed": 0, "kept": 0}
        dedup_stats_b = doc_b.dedup_stats or {"removed": 0, "kept": 0}
        toc_stats_a = doc_a.toc_virtual_stats.__dict__ if doc_a.toc_virtual_stats else {}
        toc_stats_b = doc_b.toc_virtual_stats.__dict__ if doc_b.toc_virtual_stats else {}

        self._log_info(
            "compare_start",
            {
                "nodes_a": count_nodes(root_a),
                "nodes_b": count_nodes(root_b),
                "content_items_a": sum(1 for _ in iter_content_items(doc_a.root)),
                "content_items_b": sum(1 for _ in iter_content_items(doc_b.root)),
                "dedup_removed_a": dedup_stats_a["removed"],
                "dedup_kept_a": dedup_stats_a["kept"],
                "dedup_removed_b": dedup_stats_b["removed"],
                "dedup_kept_b": dedup_stats_b["kept"],
                "toc_virtual_a": toc_stats_a,
                "toc_virtual_b": toc_stats_b,
            },
        )

        store, start_phase, skip_phase1, skip_phase2, pool1, pool2 = self._prepare_snapshot(
            doc_a=doc_a,
            doc_b=doc_b,
        )
        context = self._make_context(
            store=store,
            skip_phase1=skip_phase1,
            skip_phase2=skip_phase2,
        )
        sources_sha = store.read_sources_sha() if store is not None else None

        if skip_phase1 and pool1 is not None:
            self._log_info(
                "snapshot_resume_phase2",
                {"task_id": self._task_id, "remainder_a": len(pool1.remainder_a), "remainder_b": len(pool1.remainder_b)},
            )
            r1_pool = pool1
            r1 = SectionCompareResult(
                content_diffs=[],
                missing_titles_a=[],
                missing_titles_b=[],
                traces=[],
                first_title_mismatch=None,
                remainder_pool=r1_pool,
            )
        elif start_phase <= 1:
            if store is not None:
                store.load_title_index_from_events()
            r1 = SectionComparePhase(context).run(root_a, root_b)
            r1_pool = r1.remainder_pool
            if store is not None:
                context.snapshot.on_phase_completed(phase=1, checkpoint_name="phase1.checkpoint.json")
                store.write_phase_checkpoint(
                    1,
                    pool=r1_pool,
                    last_event_id=store.last_event_id(),
                    sources_sha=sources_sha,
                )
                store.write_meta({"phase": 2, "phase_status": "running"})
        else:
            r1_pool = RemainderPool()
            r1 = SectionCompareResult(
                content_diffs=[],
                missing_titles_a=[],
                missing_titles_b=[],
                traces=[],
                first_title_mismatch=None,
                remainder_pool=r1_pool,
            )

        if skip_phase2 and pool2 is not None:
            r2_pool = pool2
            r2 = TableAnchorCompareResult(table_anchor_diffs=[], remainder_pool=r2_pool)
        elif start_phase <= 2:
            if store is not None and not store.phase_completed_in_events(2):
                context.snapshot.on_phase_started(phase=2)
            r2 = TableAnchorComparePhase(context).run(r1_pool)
            r2_pool = r2.remainder_pool
            if store is not None:
                context.snapshot.on_phase_completed(phase=2, checkpoint_name="phase2.checkpoint.json")
                store.write_phase_checkpoint(
                    2,
                    pool=r2_pool,
                    last_event_id=store.last_event_id(),
                    sources_sha=sources_sha,
                )
                store.write_meta({"phase": 3, "phase_status": "running"})
        else:
            r2_pool = r1_pool if skip_phase1 and pool1 is not None else RemainderPool()
            r2 = TableAnchorCompareResult(table_anchor_diffs=[], remainder_pool=r2_pool)

        skip_phase3 = (
            store is not None
            and self._resume
            and store.phase_completed_in_events(3)
        )
        if start_phase <= 3:
            if store is not None and not skip_phase3 and not store.phase_completed_in_events(3):
                context.snapshot.on_phase_started(phase=3)
            if skip_phase3:
                r3 = ResidualTextCompareResult(residual_content_diffs=None)
            else:
                r3 = ResidualTextComparePhase(context).run(r2.remainder_pool)
                if store is not None:
                    residual = r3.residual_content_diffs or {}
                    context.snapshot.on_phase_completed(
                        phase=3,
                        checkpoint_name="phase3.checkpoint.json",
                    )
                    store.write_phase_checkpoint(
                        3,
                        pool=r2.remainder_pool,
                        last_event_id=store.last_event_id(),
                        sources_sha=sources_sha,
                        stats={
                            "residual_text_diffs": len(residual.get("text_diffs", [])),
                        },
                    )
                    store.write_meta({"phase": 3, "phase_status": "completed"})
        else:
            r3 = ResidualTextCompareResult(residual_content_diffs=None)

        result: dict[str, Any] = {
            "missing_titles_a": r1.missing_titles_a,
            "missing_titles_b": r1.missing_titles_b,
            "title_order_violations": [],
            "content_diffs": r1.content_diffs,
            "table_anchor_diffs": r2.table_anchor_diffs,
            "residual_content_diffs": r3.residual_content_diffs,
            "traces": r1.traces,
            "dedup_stats": {"a": dedup_stats_a, "b": dedup_stats_b},
            "toc_virtual_stats": {"a": toc_stats_a, "b": toc_stats_b},
            "first_title_mismatch": r1.first_title_mismatch,
        }

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        residual = result.get("residual_content_diffs") or {}
        self._log_info(
            "compare_end",
            {
                "elapsed_ms": elapsed_ms,
                "missing_titles_a": len(result["missing_titles_a"]),
                "missing_titles_b": len(result["missing_titles_b"]),
                "content_nodes": len(result["content_diffs"]),
                "table_anchor_nodes": len(result["table_anchor_diffs"]),
                "residual_text_diffs": len(residual.get("text_diffs", [])),
            },
        )
        return result

    def resolve_toc_anchor(self, entry: TocEntry, candidates: list[AnchorCandidate]) -> int | None:
        return self._llm.resolve_toc_anchor(entry, candidates)

    def _prepare_snapshot(
        self,
        *,
        doc_a: StructuredDocument,
        doc_b: StructuredDocument,
    ) -> tuple[
        TaskSnapshotStore | None,
        int,
        bool,
        bool,
        RemainderPool | None,
        RemainderPool | None,
    ]:
        if not self._task_id:
            return None, 1, False, False, None, None

        store = TaskSnapshotStore.open(self._tasks_dir, self._task_id, create=not self._resume)
        start_phase = 1
        skip_phase1 = False
        skip_phase2 = False
        pool1: RemainderPool | None = None
        pool2: RemainderPool | None = None

        if self._resume:
            meta = store.read_meta() or {}
            start_phase = int(meta.get("phase", 1))
            if start_phase >= 2 and store.phase_checkpoint_path(1).exists():
                skip_phase1 = True
                pool1 = store.load_phase1_remainder_pool(doc_a=doc_a, doc_b=doc_b)
            if start_phase >= 3 and store.phase_checkpoint_path(2).exists():
                skip_phase2 = True
                pool2 = store.load_phase_remainder_pool(2, doc_a=doc_a, doc_b=doc_b)
            if start_phase == 1:
                store.load_title_index_from_events()
        else:
            if self._parsed_path_a and self._parsed_path_b:
                validate_parsed_json_file(self._parsed_path_a)
                validate_parsed_json_file(self._parsed_path_b)
                store.validate_sources(self._parsed_path_a, self._parsed_path_b)
                sha = store.init_sources(
                    path_a=self._parsed_path_a,
                    path_b=self._parsed_path_b,
                    parsed_version=PARSED_VERSION,
                )
            else:
                sha = {"a": "", "b": ""}
            store.write_meta({"phase": 1, "phase_status": "running"})
            FileSnapshotHooks(store).on_task_started(sources_sha=sha)

        return store, start_phase, skip_phase1, skip_phase2, pool1, pool2

    def _make_context(
        self,
        *,
        store: TaskSnapshotStore | None = None,
        skip_phase1: bool = False,
        skip_phase2: bool = False,
    ) -> CompareContext:
        preview_chars = self._preview_chars

        def llm_match_title(
            *,
            node_a: DocumentNode,
            node_b: DocumentNode,
            parent_path_a: str,
            parent_path_b: str,
            a_index: int,
            b_index: int,
        ) -> dict[str, Any]:
            return self._llm.match_title(
                user_payload={
                    "a_node": {
                        "level": node_a.level,
                        "title_norm": node_a.title_norm,
                        "content_preview": node_a.content_preview(preview_chars),
                    },
                    "b_node": {
                        "level": node_b.level,
                        "title_norm": node_b.title_norm,
                        "content_preview": node_b.content_preview(preview_chars),
                    },
                },
                trace={
                    "parent_path_a": parent_path_a,
                    "parent_path_b": parent_path_b,
                    "a_index": a_index,
                    "b_index": b_index,
                    "path_a": node_a.path,
                    "path_b": node_b.path,
                },
            )

        from financial_compare.compare.snapshot.hooks import NoopSnapshotHooks

        hooks = FileSnapshotHooks(store) if store is not None else NoopSnapshotHooks()
        return CompareContext(
            view_budget=self._view_budget,
            preview_chars=self._preview_chars,
            llm_judge_content=self._llm.judge_content,
            llm_match_title=llm_match_title,
            llm_call_named=self._llm.call_named,
            log_info=self._log_info,
            snapshot=hooks,
            skip_phase1=skip_phase1,
            skip_phase2=skip_phase2,
        )

    def _build_logger(self, *, level: str, log_file: str | None) -> logging.Logger:
        logger = logging.getLogger(_LOGGER_NAME)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        if not logger.handlers:
            if log_file:
                target = Path(log_file)
            else:
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                target = OUTPUT_LOGS / f"compare_{stamp}.log"
            target.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(target, encoding="utf-8")
            fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            logger.addHandler(fh)
            logger.info("compare log file: %s", target.resolve())
        logger.propagate = False
        return logger

    def _log_info(self, event: str, payload: dict[str, Any]) -> None:
        if not self._enable_logging:
            return
        self._logger.info("%s %s", event, json.dumps(payload, ensure_ascii=False))

    @staticmethod
    def _short_text(text: str, *, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return f"{text[:max_len]}...(truncated)"
