"""Parser 文档后处理：TOC 虚拟补齐 + 标题去重。"""

from __future__ import annotations

from financial_compare.document.tree_utils import dedup_tree
from financial_compare.document.types import StructuredDocument
from financial_compare.document.toc import AnchorResolver
from financial_compare.parser.tree.toc_virtual import apply_toc_virtual_sections


def finalize_structured_document(
    doc: StructuredDocument,
    *,
    resolve_anchor: AnchorResolver | None = None,
) -> StructuredDocument:
    """建树后流水线：TOC 虚拟 L1 补齐 → 同级标题去重。"""
    doc, toc_stats = apply_toc_virtual_sections(doc, resolve_anchor=resolve_anchor)
    dedup_stats = dedup_tree(doc.root)
    return StructuredDocument(
        root=doc.root,
        toc=doc.toc,
        toc_virtual_stats=toc_stats,
        dedup_stats=dedup_stats,
    )
