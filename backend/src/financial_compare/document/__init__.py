"""Parser / Compare 共用域模型。"""

from financial_compare.document.item import (
    DocumentItem,
    Row,
    TableBlock,
    TableLoc,
    TextLine,
    TextLoc,
    is_table_block,
    is_text_line,
    item_text,
)
from financial_compare.document.toc import AnchorCandidate, AnchorResolver, TocEntry, TocVirtualStats
from financial_compare.document.tree import (
    DocumentNode,
    count_l1_sections,
    count_nodes,
    count_table_blocks,
    iter_content_items,
    iter_nodes_preorder,
    max_stream_index,
)
from financial_compare.document.tree_utils import dedup_tree, extract_number_hint, normalize_title
from financial_compare.document.types import StructuredDocument, StructuredLine, TocBlock

__all__ = [
    "AnchorCandidate",
    "AnchorResolver",
    "DocumentItem",
    "DocumentNode",
    "Row",
    "StructuredDocument",
    "StructuredLine",
    "TableBlock",
    "TableLoc",
    "TextLine",
    "TextLoc",
    "TocBlock",
    "TocEntry",
    "TocVirtualStats",
    "count_l1_sections",
    "count_nodes",
    "count_table_blocks",
    "dedup_tree",
    "extract_number_hint",
    "is_table_block",
    "is_text_line",
    "iter_content_items",
    "iter_nodes_preorder",
    "item_text",
    "max_stream_index",
    "normalize_title",
]
