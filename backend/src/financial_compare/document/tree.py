"""文档树节点与遍历（Parser / Compare 共用）。"""

from __future__ import annotations

from dataclasses import dataclass, field

from financial_compare.document.item import DocumentItem, TextLine, is_table_block


@dataclass
class DocumentNode:
    level: int
    title: str
    role: str
    path: str
    number_hint: str
    title_norm: str
    title_stream_index: int | None = None
    content_items: list[DocumentItem] = field(default_factory=list)
    children: list["DocumentNode"] = field(default_factory=list)

    def content_preview(self, max_chars: int) -> str:
        parts: list[str] = []
        for item in self.content_items:
            if isinstance(item, TextLine) and item.text.strip():
                parts.append(item.text.strip())
            if len("\n".join(parts)) >= max_chars:
                break
        text = "\n".join(parts).strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars]


def count_nodes(node: DocumentNode) -> int:
    total = len(node.children)
    for child in node.children:
        total += count_nodes(child)
    return total


def count_l1_sections(root: DocumentNode) -> int:
    return sum(1 for child in root.children if child.level == 1)


def count_table_blocks(root: DocumentNode) -> int:
    total = 0
    for node in iter_nodes_preorder(root):
        total += sum(1 for item in node.content_items if is_table_block(item))
    return total


def iter_nodes_preorder(root: DocumentNode):
    yield root
    for child in root.children:
        yield from iter_nodes_preorder(child)


def iter_content_items(root: DocumentNode):
    for node in iter_nodes_preorder(root):
        yield from node.content_items


def max_stream_index(root: DocumentNode) -> int:
    best = 0
    for node in iter_nodes_preorder(root):
        if node.title_stream_index is not None:
            best = max(best, node.title_stream_index)
        for item in node.content_items:
            best = max(best, item.loc.stream_index)
    return best
