"""Compare 流水线 LLM 传输层：日志、缓存、跨阶段 typed task。"""

from __future__ import annotations

import json
import time
from typing import Any

from financial_compare.compare.aligners.content_aligner import _normalize_overlap_kind, validate_overlap_decision
from financial_compare.compare.llm.prompts.content_match import CONTENT_MATCH_SYSTEM_PROMPT
from financial_compare.compare.llm.prompts.title_match import TITLE_MATCH_SYSTEM_PROMPT
from financial_compare.compare.utils.json_utils import JsonUtils
from financial_compare.compare.utils.text_compare import texts_equal
from financial_compare.document.toc import AnchorCandidate, TocEntry
from financial_compare.llm.model import chat
from financial_compare.parser.tree.toc_virtual import make_llm_toc_anchor_resolver


class CompareLlmClient:
    """封装 compare 流水线 LLM 调用与结果缓存。"""

    def __init__(
        self,
        *,
        log_info: Any,
        short_text: Any,
    ) -> None:
        self._log_info = log_info
        self._short_text = short_text
        self._title_match_cache: dict[str, dict[str, Any]] = {}
        self._content_match_cache: dict[str, dict[str, Any]] = {}
        self._toc_anchor_cache: dict[str, int | None] = {}

    def match_title(
        self,
        *,
        user_payload: dict[str, Any],
        trace: dict[str, Any],
    ) -> dict[str, Any]:
        user_text = json.dumps(user_payload, ensure_ascii=False)
        cache_key = f"title::{user_text}"
        if cache_key in self._title_match_cache:
            return self._title_match_cache[cache_key]

        a_node = user_payload.get("a_node") if isinstance(user_payload.get("a_node"), dict) else {}
        b_node = user_payload.get("b_node") if isinstance(user_payload.get("b_node"), dict) else {}
        a_title = str(a_node.get("title_norm") or "")
        b_title = str(b_node.get("title_norm") or "")
        if texts_equal(a_title, b_title):
            out = {"is_match": True, "reason": "title_norm equal", "confidence": 1.0}
            self._title_match_cache[cache_key] = out
            return out

        raw = self._call_llm(TITLE_MATCH_SYSTEM_PROMPT, user_text, call_name="title_match", trace=trace)
        parsed = JsonUtils.parse_object(raw)
        out = {"is_match": False, "reason": "invalid llm output", "confidence": None}
        if isinstance(parsed, dict):
            out = {
                "is_match": bool(parsed.get("is_match")),
                "reason": parsed.get("reason"),
                "confidence": JsonUtils.normalize_confidence(parsed.get("confidence")),
            }
        self._title_match_cache[cache_key] = out
        return out

    def judge_content(self, a_text: str, b_text: str, trace: dict[str, Any]) -> dict[str, Any]:
        user_payload = {"text_a": a_text, "text_b": b_text}
        user_text = json.dumps(user_payload, ensure_ascii=False)
        cache_key = f"content::{user_text}"
        if cache_key in self._content_match_cache:
            return self._content_match_cache[cache_key]

        raw = self._call_llm(
            CONTENT_MATCH_SYSTEM_PROMPT,
            user_text,
            call_name="content_match",
            trace={"trace": trace, "a_len": len(a_text), "b_len": len(b_text)},
        )
        parsed = JsonUtils.parse_object(raw)
        out: dict[str, Any] = {
            "overlap_kind": "none",
            "A_span": "",
            "B_span": "",
            "diff": [],
            "confidence": None,
        }
        if isinstance(parsed, dict):
            out = validate_overlap_decision(
                {
                    "overlap_kind": _normalize_overlap_kind(parsed.get("overlap_kind")),
                    "A_span": str(parsed.get("A_span") or "").strip(),
                    "B_span": str(parsed.get("B_span") or "").strip(),
                    "diff": JsonUtils.normalize_diff_list(parsed.get("diff")),
                    "confidence": JsonUtils.normalize_confidence(parsed.get("confidence")),
                }
            )
        self._content_match_cache[cache_key] = out
        return out

    def call_named(self, call_name: str, system_prompt: str, user_text: str) -> str:
        return self._call_llm(system_prompt, user_text, call_name=call_name, trace={})

    def resolve_toc_anchor(self, entry: TocEntry, candidates: list[AnchorCandidate]) -> int | None:
        cache_key = self._toc_anchor_cache_key(entry, candidates)
        if cache_key in self._toc_anchor_cache:
            return self._toc_anchor_cache[cache_key]

        def chat_fn(system_prompt: str, user_text: str) -> str:
            return self._call_llm(
                system_prompt,
                user_text,
                call_name="toc_anchor_resolve",
                trace={"section_title": entry.section_title, "candidate_count": len(candidates)},
            )

        resolver = make_llm_toc_anchor_resolver(chat_fn)
        idx = resolver(entry, candidates)
        self._toc_anchor_cache[cache_key] = idx
        return idx

    def _call_llm(
        self,
        system_prompt: str,
        user_text: str,
        *,
        call_name: str,
        trace: dict[str, Any] | None = None,
    ) -> str:
        self._log_info(
            "llm_call_start",
            {
                "call_name": call_name,
                "trace": trace or {},
                "user_preview": self._short_text(user_text, max_len=280),
            },
        )
        t0 = time.perf_counter()
        out = chat(system_prompt, user_text)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        self._log_info(
            "llm_call_end",
            {"call_name": call_name, "trace": trace or {}, "elapsed_ms": elapsed_ms},
        )
        return out

    @staticmethod
    def _toc_anchor_cache_key(entry: TocEntry, candidates: list[AnchorCandidate]) -> str:
        parts = [entry.section_title, entry.ordinal_key]
        for item in candidates:
            parts.append(f"{item.line_index}:{item.line_text}")
        return "toc_anchor::" + "|".join(parts)
