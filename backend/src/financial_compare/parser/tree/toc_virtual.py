"""TOC 虚拟 L1 节注入：toc 有而文档树无时，在正文锚点处补齐虚拟 L1 节点。"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import replace

from financial_compare.document.item import TextLine
from financial_compare.document.toc import AnchorCandidate, AnchorResolver, TocEntry, TocVirtualStats
from financial_compare.document.tree import DocumentNode, iter_content_items, iter_nodes_preorder, max_stream_index
from financial_compare.document.tree_utils import extract_number_hint, normalize_title
from financial_compare.document.types import StructuredDocument, TocBlock

_RE_L1 = re.compile(r"^第([一二三四五六七八九十百千万零〇○\d]+)[节節]\s*(.*)$", re.UNICODE)
_RE_PAGE = re.compile(r"[\s\t]+[\d０-９]+(?:\s*[-–—~～]\s*[\d０-９]+)?\s*$")
_NOISE = re.compile(r"[（）()【】\[\]：:，,。.\-—_|｜、；;！!？?·•\s]+")
_SENT_MARK = frozenset("。;！!？?")
_LLM_PROMPT = (
    "给定 TOC 一级目录与正文候选行，返回 JSON："
    '{"line_index":<整数或null>,"reason":"..."}。'
    "允许简繁/同义词；无匹配则 line_index=null。勿输出 markdown。"
)


def apply_toc_virtual_sections(
    doc: StructuredDocument,
    *,
    resolve_anchor: AnchorResolver | None = None,
) -> tuple[StructuredDocument, TocVirtualStats]:
    block = _pick_toc_block(doc.toc)
    if block is None or not doc.root.children and not _has_content(doc.root):
        return doc, TocVirtualStats(False, 0, 0, ())

    entries = _parse_toc_l1(block)
    tree_l1 = _tree_l1_map(doc.root)
    missing = [e for e in entries if e.ordinal_key not in tree_l1]
    if not missing:
        return doc, TocVirtualStats(False, 0, 0, ())

    max_stream = max_stream_index(doc.root)
    inject_at: dict[int, str] = {}
    misses: list[str] = []
    search_from = 0
    for entry in missing:
        ei = next(i for i, e in enumerate(entries) if e.ordinal_key == entry.ordinal_key)
        start, end = _window(entries, ei, tree_l1, max_stream)
        start = max(start, search_from)
        cands = _find_candidates(doc.root, entry, start, end)
        picked = _pick_anchor(entry, cands, resolve_anchor)
        if picked is None:
            misses.append(entry.section_title)
            continue
        stream_idx, title = picked
        inject_at[stream_idx] = title
        search_from = stream_idx + 1

    if not inject_at:
        return doc, TocVirtualStats(False, len(missing), 0, tuple(misses))

    new_root = _inject_virtual_nodes(doc.root, inject_at)
    return (
        StructuredDocument(root=new_root, toc=doc.toc),
        TocVirtualStats(True, len(missing), len(inject_at), tuple(misses)),
    )


def make_llm_toc_anchor_resolver(chat_fn: Callable[[str, str], str]) -> AnchorResolver:
    def resolve(entry: TocEntry, candidates: list[AnchorCandidate]) -> int | None:
        if not candidates:
            return None
        valid = {c.line_index for c in candidates}
        payload = json.dumps(
            {
                "toc_entry": {"ordinal_key": entry.ordinal_key, "section_title": entry.section_title},
                "candidates": [{"line_index": c.line_index, "line_text": c.line_text, "score": c.score} for c in candidates],
            },
            ensure_ascii=False,
        )
        return parse_toc_anchor_response(chat_fn(_LLM_PROMPT, payload), valid_indices=valid)

    return resolve


def parse_toc_anchor_response(text: str, *, valid_indices: set[int]) -> int | None:
    raw = text.strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict) or data.get("line_index") is None:
        return None
    try:
        idx = int(data["line_index"])
    except (TypeError, ValueError):
        return None
    return idx if idx in valid_indices else None


def _has_content(root: DocumentNode) -> bool:
    return any(True for _ in iter_content_items(root))


def _pick_toc_block(toc: list[TocBlock]) -> TocBlock | None:
    return max(toc, key=lambda b: len(_parse_toc_l1(b)), default=None) if toc else None


def _parse_toc_l1(block: TocBlock) -> list[TocEntry]:
    out, seen = [], set()
    for line in block.lines:
        text = line.text.strip()
        if not text or text in ("目录", "目錄", "目    录"):
            continue
        text = _RE_PAGE.sub("", text).strip()
        m = _RE_L1.match(text)
        if not m:
            continue
        key = unicodedata.normalize("NFKC", m.group(1))
        if key in seen:
            continue
        seen.add(key)
        out.append(TocEntry(key, text))
    return out


def _tree_l1_map(root: DocumentNode) -> dict[str, int]:
    out: dict[str, int] = {}
    for child in root.children:
        if child.level != 1 or child.title_stream_index is None:
            continue
        m = _RE_L1.match(child.title.strip())
        if m:
            out[unicodedata.normalize("NFKC", m.group(1))] = child.title_stream_index
    return out


def _window(
    entries: list[TocEntry],
    ei: int,
    tree_l1: dict[str, int],
    max_stream: int,
) -> tuple[int, int]:
    start = 0
    for j in range(ei - 1, -1, -1):
        if entries[j].ordinal_key in tree_l1:
            start = tree_l1[entries[j].ordinal_key] + 1
            break
    end = max_stream + 1
    for j in range(ei + 1, len(entries)):
        if entries[j].ordinal_key in tree_l1:
            end = tree_l1[entries[j].ordinal_key]
            break
    return start, end


def _find_candidates(
    root: DocumentNode,
    entry: TocEntry,
    start: int,
    end: int,
    *,
    top_k: int = 8,
) -> list[AnchorCandidate]:
    m = _RE_L1.match(entry.section_title)
    core = m.group(2).strip() if m else entry.section_title.strip()
    scored: list[AnchorCandidate] = []
    for node in iter_nodes_preorder(root):
        if node.title_stream_index is not None and start <= node.title_stream_index < end:
            text = node.title.strip()
            if text and len(re.sub(r"\s+", "", text)) <= 64 and not any(c in text for c in _SENT_MARK):
                score = _similarity(core, text)
                if score >= 0.4:
                    scored.append(AnchorCandidate(node.title_stream_index, text, score))
        for item in node.content_items:
            if not isinstance(item, TextLine):
                continue
            stream_idx = item.loc.stream_index
            if stream_idx < start or stream_idx >= end:
                continue
            text = item.text.strip()
            if not text or len(re.sub(r"\s+", "", text)) > 64 or any(c in text for c in _SENT_MARK):
                continue
            score = _similarity(core, text)
            if score >= 0.4:
                scored.append(AnchorCandidate(stream_idx, text, score))
    scored.sort(key=lambda c: (-c.score, c.line_index))
    return scored[:top_k]


def _inject_virtual_nodes(root: DocumentNode, inject_at: dict[int, str]) -> DocumentNode:
    children = list(root.children)
    for stream_idx in sorted(inject_at.keys()):
        title = inject_at[stream_idx]
        pos = _insert_pos_for_stream(children, stream_idx)
        parent_path = root.path
        node = DocumentNode(
            level=1,
            title=title,
            role="section",
            path=f"{parent_path}/{title}",
            number_hint=extract_number_hint(title),
            title_norm=normalize_title(title),
            title_stream_index=stream_idx,
        )
        children.insert(pos, node)
    return replace(root, children=children)


def _insert_pos_for_stream(children: list[DocumentNode], stream_idx: int) -> int:
    for pos, child in enumerate(children):
        if child.title_stream_index is not None and child.title_stream_index >= stream_idx:
            return pos
        for item in child.content_items:
            if item.loc.stream_index >= stream_idx:
                return pos
    return len(children)


def _pick_anchor(
    entry: TocEntry,
    cands: list[AnchorCandidate],
    resolve_anchor: AnchorResolver | None,
) -> tuple[int, str] | None:
    if not cands:
        return None
    best = cands[0]
    confident = best.score >= 0.95 and (len(cands) == 1 or best.score - cands[1].score >= 0.15)
    if not confident and resolve_anchor is not None:
        idx = resolve_anchor(entry, cands)
        if idx is None:
            return None
        text = next(c.line_text for c in cands if c.line_index == idx)
        return idx, _inject_title(entry, text)
    if confident or best.score >= 0.7:
        return best.line_index, _inject_title(entry, best.line_text)
    return None


def _inject_title(entry: TocEntry, anchor: str) -> str:
    text = anchor.strip()
    if _RE_L1.match(text):
        return text
    m = re.match(r"^第[^节節\s]+[节節]", entry.section_title)
    return f"{m.group(0) if m else f'第{entry.ordinal_key}節'} {text}"


def _similarity(a_raw: str, b_raw: str) -> float:
    a, b = _norm(a_raw), _norm(b_raw)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.85 + 0.15 * min(len(a), len(b)) / max(len(a), len(b))
    overlap = len(set(a) & set(b)) / len(set(a) | set(b))
    return overlap * 0.75


def _norm(text: str) -> str:
    return _NOISE.sub("", unicodedata.normalize("NFKC", text).strip().lower())
