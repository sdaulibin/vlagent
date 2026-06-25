"""DocumentItem 混合流数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class TextLoc:
    stream_index: int
    section_path: str | None = None
    element_index: int | None = None
    page: int | None = None
    bbox: list[float] | None = None
    spans: list[dict[str, Any]] | None = None


@dataclass
class TextLine:
    text: str
    loc: TextLoc
    kind: Literal["text"] = "text"


@dataclass
class TableLoc:
    stream_index: int
    table_index: int
    section_path: str | None = None
    element_index: int | None = None
    page: int | None = None
    page_end: int | None = None
    bbox: list[float] | None = None


@dataclass
class Row:
    content: str
    row_type: Literal["header", "body"]
    row_index: int
    bbox: list[float] | None = None
    cell_bboxes: list[list[float] | None] | None = None


TableKind = Literal["KVTable", "ComTable"]


@dataclass
class TableBlock:
    rows: list[Row]
    loc: TableLoc
    html: str | None = None
    table_kind: TableKind | None = None
    kind: Literal["table"] = "table"


DocumentItem = TextLine | TableBlock


def item_text(item: DocumentItem) -> str:
    """语言门禁等场景下的文本抽样。"""
    if isinstance(item, TextLine):
        return item.text
    return " ".join(row.content for row in item.rows)


def is_text_line(item: DocumentItem) -> bool:
    return isinstance(item, TextLine)


def is_table_block(item: DocumentItem) -> bool:
    return isinstance(item, TableBlock)
