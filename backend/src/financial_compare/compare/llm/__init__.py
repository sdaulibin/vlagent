"""Compare 流水线 LLM：传输层与 prompt 集中管理。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from financial_compare.compare.llm.client import CompareLlmClient

__all__ = ["CompareLlmClient"]


def __getattr__(name: str):
    if name == "CompareLlmClient":
        from financial_compare.compare.llm.client import CompareLlmClient

        return CompareLlmClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
