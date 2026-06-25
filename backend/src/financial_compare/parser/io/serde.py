"""StructuredDocument 序列化/反序列化（root 文档树 + toc）。"""

from __future__ import annotations

import json
from pathlib import Path

from financial_compare.document.item import DocumentItem, Row, TableBlock, TableLoc, TextLine, TextLoc
from financial_compare.document.tree import DocumentNode, iter_content_items
from financial_compare.document.types import StructuredDocument, StructuredLine, TocBlock

PARSED_VERSION = 6


def is_pdf_text_loc(loc: TextLoc | dict[str, object]) -> bool:
    """PDF 正文 TextLine：有 page、无 DOCX element_index。"""
    if isinstance(loc, TextLoc):
        return loc.page is not None and loc.element_index is None
    if isinstance(loc, dict):
        return loc.get("page") is not None and loc.get("element_index") is None
    return False


def validate_structured_document(doc: StructuredDocument) -> None:
    """v6：PDF TextLine 必须带非空 ``loc.spans``（供文表虚拟重建）。"""
    missing: list[int] = []
    for item in iter_content_items(doc.root):
        if not isinstance(item, TextLine):
            continue
        if not item.text.strip():
            continue
        if not is_pdf_text_loc(item.loc):
            continue
        if not item.loc.spans:
            missing.append(item.loc.stream_index)
    if missing:
        sample = ", ".join(str(x) for x in missing[:5])
        suffix = f"… 等共 {len(missing)} 条" if len(missing) > 5 else ""
        raise ValueError(
            f"parsed v{PARSED_VERSION}: PDF TextLine 缺少 loc.spans "
            f"（stream_index: {sample}{suffix}）；请重新运行 test_file_parse.py 导出"
        )


def validate_parsed_json_file(path: str | Path) -> StructuredDocument:
    """加载 parsed JSON 并校验 version + PDF spans schema。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"parsed 文件根节点必须是 object: {path}")
    doc = structured_document_from_dict(data)
    validate_structured_document(doc)
    return doc


def structured_line_to_dict(line: StructuredLine) -> dict[str, object]:
    return {"level": line.level, "role": line.role, "text": line.text}


def structured_line_from_dict(data: dict[str, object]) -> StructuredLine:
    return StructuredLine(
        level=int(data["level"]),
        role=data["role"],  # type: ignore[arg-type]
        text=str(data["text"]),
    )


def text_loc_to_dict(loc: TextLoc) -> dict[str, object]:
    out: dict[str, object] = {
        "stream_index": loc.stream_index,
        "section_path": loc.section_path,
        "element_index": loc.element_index,
        "page": loc.page,
        "bbox": loc.bbox,
    }
    if loc.spans is not None:
        out["spans"] = loc.spans
    return out


def text_loc_from_dict(data: dict[str, object]) -> TextLoc:
    bbox = data.get("bbox")
    spans = data.get("spans")
    return TextLoc(
        stream_index=int(data["stream_index"]),
        section_path=data.get("section_path"),  # type: ignore[arg-type]
        element_index=data.get("element_index"),  # type: ignore[arg-type]
        page=data.get("page"),  # type: ignore[arg-type]
        bbox=list(bbox) if isinstance(bbox, list) else None,
        spans=list(spans) if isinstance(spans, list) else None,
    )


def table_loc_to_dict(loc: TableLoc) -> dict[str, object]:
    return {
        "stream_index": loc.stream_index,
        "table_index": loc.table_index,
        "section_path": loc.section_path,
        "element_index": loc.element_index,
        "page": loc.page,
        "page_end": loc.page_end,
        "bbox": loc.bbox,
    }


def table_loc_from_dict(data: dict[str, object]) -> TableLoc:
    bbox = data.get("bbox")
    return TableLoc(
        stream_index=int(data["stream_index"]),
        table_index=int(data["table_index"]),
        section_path=data.get("section_path"),  # type: ignore[arg-type]
        element_index=data.get("element_index"),  # type: ignore[arg-type]
        page=data.get("page"),  # type: ignore[arg-type]
        page_end=data.get("page_end"),  # type: ignore[arg-type]
        bbox=list(bbox) if isinstance(bbox, list) else None,
    )


def row_to_dict(row: Row) -> dict[str, object]:
    out: dict[str, object] = {
        "content": row.content,
        "row_type": row.row_type,
        "row_index": row.row_index,
        "bbox": row.bbox,
    }
    if row.cell_bboxes is not None:
        out["cell_bboxes"] = row.cell_bboxes
    return out


def row_from_dict(data: dict[str, object]) -> Row:
    bbox = data.get("bbox")
    raw_cells = data.get("cell_bboxes")
    cell_bboxes: list[list[float] | None] | None = None
    if isinstance(raw_cells, list):
        cell_bboxes = []
        for item in raw_cells:
            if isinstance(item, list) and len(item) >= 4:
                cell_bboxes.append([float(x) for x in item[:4]])
            else:
                cell_bboxes.append(None)
    return Row(
        content=str(data["content"]),
        row_type=data["row_type"],  # type: ignore[arg-type]
        row_index=int(data["row_index"]),
        bbox=list(bbox) if isinstance(bbox, list) else None,
        cell_bboxes=cell_bboxes,
    )


def document_item_to_dict(item: DocumentItem) -> dict[str, object]:
    if isinstance(item, TextLine):
        return {
            "kind": "text",
            "text": item.text,
            "loc": text_loc_to_dict(item.loc),
        }
    return {
        "kind": "table",
        "rows": [row_to_dict(row) for row in item.rows],
        "loc": table_loc_to_dict(item.loc),
        "html": item.html,
        "table_kind": item.table_kind,
    }


def document_item_from_dict(data: dict[str, object]) -> DocumentItem:
    kind = data.get("kind")
    if kind == "text":
        loc = data.get("loc")
        if not isinstance(loc, dict):
            raise ValueError("TextLine 缺少 loc")
        return TextLine(text=str(data["text"]), loc=text_loc_from_dict(loc))
    if kind == "table":
        loc = data.get("loc")
        rows_raw = data.get("rows")
        if not isinstance(loc, dict) or not isinstance(rows_raw, list):
            raise ValueError("TableBlock 缺少 loc 或 rows")
        html = data.get("html")
        table_kind = data.get("table_kind")
        return TableBlock(
            rows=[row_from_dict(row) for row in rows_raw if isinstance(row, dict)],
            loc=table_loc_from_dict(loc),
            html=str(html) if html is not None else None,
            table_kind=str(table_kind) if table_kind in ("KVTable", "ComTable") else None,  # type: ignore[arg-type]
        )
    raise ValueError(f"未知 DocumentItem kind: {kind!r}")


def document_node_to_dict(node: DocumentNode) -> dict[str, object]:
    payload: dict[str, object] = {
        "level": node.level,
        "title": node.title,
        "role": node.role,
        "path": node.path,
        "number_hint": node.number_hint,
        "title_norm": node.title_norm,
        "content_items": [document_item_to_dict(item) for item in node.content_items],
        "children": [document_node_to_dict(child) for child in node.children],
    }
    if node.title_stream_index is not None:
        payload["title_stream_index"] = node.title_stream_index
    return payload


def document_node_from_dict(data: dict[str, object]) -> DocumentNode:
    children_raw = data.get("children")
    items_raw = data.get("content_items")
    if not isinstance(children_raw, list) or not isinstance(items_raw, list):
        raise ValueError("文档树节点格式错误：缺少 children / content_items")
    stream_raw = data.get("title_stream_index")
    return DocumentNode(
        level=int(data["level"]),
        title=str(data["title"]),
        role=str(data["role"]),
        path=str(data["path"]),
        number_hint=str(data.get("number_hint") or ""),
        title_norm=str(data.get("title_norm") or ""),
        title_stream_index=int(stream_raw) if stream_raw is not None else None,
        content_items=[
            document_item_from_dict(item) for item in items_raw if isinstance(item, dict)
        ],
        children=[
            document_node_from_dict(child) for child in children_raw if isinstance(child, dict)
        ],
    )


def toc_from_dict(toc_raw: object) -> list[TocBlock]:
    if not isinstance(toc_raw, list):
        raise ValueError("parsed 文件格式错误：缺少 toc")
    toc: list[TocBlock] = []
    for block in toc_raw:
        if not isinstance(block, dict):
            continue
        lines_raw = block.get("lines")
        if not isinstance(lines_raw, list):
            continue
        lines = tuple(
            structured_line_from_dict(line) for line in lines_raw if isinstance(line, dict)
        )
        toc.append(TocBlock(lines=lines))
    return toc


def structured_document_to_dict(
    doc: StructuredDocument,
    *,
    source_file: str | None = None,
    version: int = PARSED_VERSION,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": version,
        "root": document_node_to_dict(doc.root),
        "toc": [
            {"lines": [structured_line_to_dict(line) for line in block.lines]}
            for block in doc.toc
        ],
    }
    if source_file is not None:
        payload["source_file"] = source_file
    return payload


def structured_document_from_dict(data: dict[str, object]) -> StructuredDocument:
    version = data.get("version")
    if version != PARSED_VERSION:
        raise ValueError(f"不支持的 parsed 版本: {version!r}（当前 {PARSED_VERSION}）")

    root_raw = data.get("root")
    if not isinstance(root_raw, dict):
        raise ValueError("parsed 文件格式错误：缺少 root")
    root = document_node_from_dict(root_raw)
    toc = toc_from_dict(data.get("toc"))
    doc = StructuredDocument(root=root, toc=toc)
    validate_structured_document(doc)
    return doc
