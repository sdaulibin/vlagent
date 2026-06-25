"""从 Parser 文档树导出可读视图。"""

from __future__ import annotations

from financial_compare.document.tree import DocumentNode
from financial_compare.document.types import StructuredLine


def tree_to_main_lines(root: DocumentNode) -> list[StructuredLine]:
    """导出文档树标题行（不含正文）。"""
    out: list[StructuredLine] = []
    for child in root.children:
        _append_node_lines(child, out)
    return out


def _append_node_lines(node: DocumentNode, out: list[StructuredLine]) -> None:
    out.append(StructuredLine(level=node.level, role=node.role, text=node.title))  # type: ignore[arg-type]
    for child in node.children:
        _append_node_lines(child, out)


__all__ = [
    "tree_to_main_lines",
]
