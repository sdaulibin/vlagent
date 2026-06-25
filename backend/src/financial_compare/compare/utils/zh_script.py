"""简繁字表归一化：两侧均转简体后比较（与 A/B 文件角色无关）。"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Literal

_DEFAULT_CHAR_MAP_PATH = Path("config/zh_trad_to_simp.json")

_WS_RE = re.compile(r"[\s\u00a0\f\v]+", re.UNICODE)
_PUNCT_NORM = str.maketrans(
    {
        "（": "(",
        "）": ")",
        "／": "/",
        "╱": "/",
        "，": ",",
        "：": ":",
    }
)

@lru_cache(maxsize=1)
def _load_trad_to_simp(path: str | None = None) -> dict[str, str]:
    map_path = Path(path) if path else _DEFAULT_CHAR_MAP_PATH
    if not map_path.is_file():
        raise FileNotFoundError(f"简繁字表不存在: {map_path}")
    payload = json.loads(map_path.read_text(encoding="utf-8"))
    chars = payload.get("chars") if isinstance(payload, dict) else None
    if not isinstance(chars, dict):
        raise ValueError(f"简繁字表格式无效: {map_path}")
    return {str(k): str(v) for k, v in chars.items()}


def trad_to_simp(text: str, *, char_map_path: str | None = None) -> str:
    """将繁体文本按字表转为简体；未收录字符保持原样。"""
    mapping = _load_trad_to_simp(char_map_path)
    return "".join(mapping.get(ch, ch) for ch in text)


def norm_for_compare(text: str, *, side: Literal["a", "b"], char_map_path: str | None = None) -> str:
    """NFKC + 轻量标点归一 + 去空白；B 侧额外做繁→简。"""
    normalized = unicodedata.normalize("NFKC", text).translate(_PUNCT_NORM)
    normalized = _WS_RE.sub("", normalized)
    if side == "b":
        normalized = trad_to_simp(normalized, char_map_path=char_map_path)
    return normalized


def script_equal(a: str, b: str, *, char_map_path: str | None = None) -> bool:
    """两侧均转简体后比较（与 A/B 文件角色无关）。"""
    def to_simp(text: str) -> str:
        base = norm_for_compare(text, side="a", char_map_path=char_map_path)
        return trad_to_simp(base, char_map_path=char_map_path)

    return to_simp(a) == to_simp(b)
