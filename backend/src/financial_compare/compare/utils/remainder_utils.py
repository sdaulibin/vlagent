"""Remainder 池操作与节点展平。"""

from __future__ import annotations

from financial_compare.document.item import DocumentItem, TableBlock, TextLine, is_table_block, is_text_line
from financial_compare.document.tree import DocumentNode


class RemainderUtils:
    @staticmethod
    def sort_remainder(items: list[DocumentItem]) -> list[DocumentItem]:
        return sorted(items, key=lambda x: x.loc.stream_index)

    @staticmethod
    def flatten_node_content_to_remainder(node: DocumentNode, target: list[DocumentItem]) -> None:
        """仅展平节点自身 content_items，不含子树（整行/整表原子）。"""
        for item in node.content_items:
            if is_text_line(item) or is_table_block(item):
                target.append(item)

    @staticmethod
    def flatten_subtree_to_remainder(node: DocumentNode, target: list[DocumentItem]) -> None:
        RemainderUtils.flatten_node_content_to_remainder(node, target)
        for child in node.children:
            RemainderUtils.flatten_subtree_to_remainder(child, target)

    @staticmethod
    def remove_entries(pool: list[DocumentItem], to_remove: list[DocumentItem]) -> None:
        remove_ids = {id(entry) for entry in to_remove}
        pool[:] = [entry for entry in pool if id(entry) not in remove_ids]

    @staticmethod
    def node_has_substance(node: DocumentNode) -> bool:
        if node.content_items:
            return True
        return any(RemainderUtils.node_has_substance(child) for child in node.children)
