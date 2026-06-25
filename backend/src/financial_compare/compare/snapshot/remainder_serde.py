"""remainder_pool 与 checkpoint 互转。"""

from __future__ import annotations

from typing import Any

from financial_compare.document.item import DocumentItem, is_table_block, is_text_line
from financial_compare.document.tree import DocumentNode, iter_content_items
from financial_compare.document.types import StructuredDocument


def build_content_index(root: DocumentNode) -> dict[int, DocumentItem]:
    index: dict[int, DocumentItem] = {}
    for item in iter_content_items(root):
        index[item.loc.stream_index] = item
    return index


def remainder_pool_to_dict(
    pool_a: list[DocumentItem],
    pool_b: list[DocumentItem],
) -> dict[str, list[dict[str, Any]]]:
    return {
        "a": [_document_item_ref(x) for x in pool_a],
        "b": [_document_item_ref(x) for x in pool_b],
    }


def _document_item_ref(item: DocumentItem) -> dict[str, Any]:
    return {"kind": item.kind, "stream_index": item.loc.stream_index}


def remainder_pool_from_dict(
    data: dict[str, Any],
    *,
    doc_a: StructuredDocument,
    doc_b: StructuredDocument,
) -> tuple[list[DocumentItem], list[DocumentItem]]:
    index_a = build_content_index(doc_a.root)
    index_b = build_content_index(doc_b.root)
    return (
        [_resolve_ref(x, index=index_a) for x in data.get("a", []) if isinstance(x, dict)],
        [_resolve_ref(x, index=index_b) for x in data.get("b", []) if isinstance(x, dict)],
    )


def _resolve_ref(raw: dict[str, Any], *, index: dict[int, DocumentItem]) -> DocumentItem:
    kind = raw.get("kind")
    stream_index = int(raw.get("stream_index", 0))
    item = index.get(stream_index)
    if item is None:
        raise ValueError(f"无法从 parsed 树还原 stream_index={stream_index}")
    if kind == "text" and not is_text_line(item):
        raise ValueError(f"checkpoint kind=text 但 stream_index={stream_index} 非 TextLine")
    if kind == "table" and not is_table_block(item):
        raise ValueError(f"checkpoint kind=table 但 stream_index={stream_index} 非 TableBlock")
    return item
