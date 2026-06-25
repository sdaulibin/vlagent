"""文档树标题归一化与去重（Parser / Compare 共用）。"""

from __future__ import annotations

import re

from financial_compare.document.item import TextLine
from financial_compare.document.tree import DocumentNode

_SPACE_RE = re.compile(r"\s+")
_NOISE_RE = re.compile(r"[（）()【】\[\]：:，,。.\-—_|｜]+")


def extract_number_hint(title: str) -> str:
    s = title.strip()
    patterns = [
        r"^(第[一二三四五六七八九十百千万零〇○\d]+[节節])",
        r"^([一二三四五六七八九十百千]+[、，])",
        r"^(\d+(?:\.\d+){0,3})",
        r"^([（(]?[一二三四五六七八九十百千\d]+[)）]?)",
    ]
    for pat in patterns:
        m = re.match(pat, s)
        if m:
            return m.group(1)
    return ""


def normalize_title(title: str) -> str:
    s = title.strip().lower()
    s = _NOISE_RE.sub("", s)
    s = _SPACE_RE.sub("", s)
    return s


def is_same_anchor(left: DocumentNode, right: DocumentNode) -> bool:
    if left.level != right.level:
        return False
    if left.number_hint and right.number_hint and left.number_hint != right.number_hint:
        return False
    left_anchor = left.title_norm.strip() or ""
    right_anchor = right.title_norm.strip() or ""
    if not left_anchor or not right_anchor:
        return False
    return left_anchor in right_anchor or right_anchor in left_anchor


def node_quality_score(node: DocumentNode) -> tuple[int, int, int]:
    content_len = sum(len(i.text) for i in node.content_items if isinstance(i, TextLine))
    return (len(node.children), content_len, len(node.title))


def choose_better_node(group: list[DocumentNode]) -> DocumentNode:
    best = group[0]
    best_score = node_quality_score(best)
    for node in group[1:]:
        score = node_quality_score(node)
        if score > best_score:
            best = node
            best_score = score
    return best


def dedup_tree(root: DocumentNode) -> dict[str, int]:
    """同级标题去重（原地修改）。"""
    stats = {"removed": 0, "kept": 0}
    _dedup_sibling_nodes(root.children, stats=stats)
    return stats


def _dedup_sibling_nodes(nodes: list[DocumentNode], *, stats: dict[str, int]) -> None:
    if not nodes:
        return
    deduped: list[DocumentNode] = []
    idx = 0
    while idx < len(nodes):
        group = [nodes[idx]]
        idx += 1
        while idx < len(nodes) and is_same_anchor(group[0], nodes[idx]):
            group.append(nodes[idx])
            idx += 1
        chosen = choose_better_node(group)
        deduped.append(chosen)
        if len(group) > 1:
            stats["removed"] += len(group) - 1
            stats["kept"] += 1
    nodes[:] = deduped
    for node in nodes:
        _dedup_sibling_nodes(node.children, stats=stats)
