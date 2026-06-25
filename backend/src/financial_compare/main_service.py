"""应用层门面：串联 parser 与 compare，供 CLI / FastAPI 复用。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from financial_compare.app_config import init_app_config
from financial_compare.compare.engine import SimplifiedTraditionalCompare
from financial_compare.document.tree import count_l1_sections, count_nodes, count_table_blocks, iter_content_items
from financial_compare.document.types import StructuredDocument, StructuredLine
from financial_compare.llm.model import load_llm_config
from financial_compare.parser.io.export import tree_to_main_lines
from financial_compare.parser.page_range import PageRange
from financial_compare.parser.structured_parser import StructuredParser
from financial_compare.parser.tree.finalize import finalize_structured_document


class MainService:
    """文件差异比较应用服务。"""

    def __init__(
        self,
        *,
        config_path: str | Path | None = None,
        enable_logging: bool = True,
        log_level: str = "INFO",
        log_file: str | None = None,
        preview_chars: int = 120,
        view_budget: int = 2400,
        task_id: str | None = None,
        tasks_dir: str | Path | None = None,
        resume: bool = False,
    ) -> None:
        init_app_config(config_path)
        self._compare = SimplifiedTraditionalCompare(
            enable_logging=enable_logging,
            log_level=log_level,
            log_file=log_file,
            preview_chars=preview_chars,
            view_budget=view_budget,
            task_id=task_id,
            tasks_dir=tasks_dir,
            resume=resume,
        )

    @property
    def compare_engine(self) -> SimplifiedTraditionalCompare:
        return self._compare

    def health(self) -> dict[str, str]:
        return {"status": "ok"}

    def ready(self) -> dict[str, Any]:
        """检查 LLM 配置是否可读（不发起模型调用）。"""
        try:
            cfg = load_llm_config()
            return {
                "ready": True,
                "model": cfg.get("model"),
                "base_url": cfg.get("base_url"),
            }
        except Exception as exc:
            return {"ready": False, "error": str(exc)}

    def parse_file(
        self,
        file_path: str | Path,
        *,
        page_range: PageRange | None = None,
        side: str = "a",
    ) -> StructuredDocument:
        doc = StructuredParser().parse(
            file_path,
            page_range=page_range,
            side=side,
        )
        return finalize_structured_document(
            doc,
            resolve_anchor=self._compare.resolve_toc_anchor,
        )

    def parse_pair(
        self,
        path_a: str | Path,
        path_b: str | Path,
        *,
        page_range: PageRange | None = None,
    ) -> tuple[StructuredDocument, StructuredDocument, bool]:
        doc_a, doc_b, swapped = StructuredParser().parse_pair(
            path_a,
            path_b,
            page_range=page_range,
        )
        return (
            finalize_structured_document(
                doc_a,
                resolve_anchor=self._compare.resolve_toc_anchor,
            ),
            finalize_structured_document(
                doc_b,
                resolve_anchor=self._compare.resolve_toc_anchor,
            ),
            swapped,
        )

    def compare_files(
        self,
        file_a: str | Path,
        file_b: str | Path,
        *,
        page_range: PageRange | None = None,
    ) -> dict[str, Any]:
        doc_a, doc_b, _swapped = self.parse_pair(file_a, file_b, page_range=page_range)
        return self.compare_documents(doc_a, doc_b)

    def compare_documents(
        self,
        doc_a: StructuredDocument,
        doc_b: StructuredDocument,
        *,
        parsed_path_a: str | Path | None = None,
        parsed_path_b: str | Path | None = None,
    ) -> dict[str, Any]:
        if parsed_path_a is not None:
            self._compare._parsed_path_a = Path(parsed_path_a)
        if parsed_path_b is not None:
            self._compare._parsed_path_b = Path(parsed_path_b)
        return self._compare.compare(doc_a, doc_b)

    def export_deduped_document(
        self,
        doc: StructuredDocument,
    ) -> tuple[StructuredDocument, list[StructuredLine], dict[str, int]]:
        """返回已 finalize 文档的去重标题行。"""
        dedup_main = tree_to_main_lines(doc.root)
        stats = doc.dedup_stats or {"removed": 0, "kept": 0}
        return doc, dedup_main, stats

    def preview_documents(
        self,
        doc_a: StructuredDocument,
        doc_b: StructuredDocument,
    ) -> dict[str, Any]:
        """不调用 LLM，返回已 finalize 文档的结构预览。"""
        stats_a = doc_a.toc_virtual_stats.__dict__ if doc_a.toc_virtual_stats else {}
        stats_b = doc_b.toc_virtual_stats.__dict__ if doc_b.toc_virtual_stats else {}
        return {
            "tree_nodes_a": count_nodes(doc_a.root),
            "tree_nodes_b": count_nodes(doc_b.root),
            "content_items_a": sum(1 for _ in iter_content_items(doc_a.root)),
            "content_items_b": sum(1 for _ in iter_content_items(doc_b.root)),
            "table_blocks_a": count_table_blocks(doc_a.root),
            "table_blocks_b": count_table_blocks(doc_b.root),
            "toc_blocks_a": len(doc_a.toc),
            "toc_blocks_b": len(doc_b.toc),
            "toc_virtual_a": stats_a,
            "toc_virtual_b": stats_b,
            "l1_sections_a": count_l1_sections(doc_a.root),
            "l1_sections_b": count_l1_sections(doc_b.root),
        }
