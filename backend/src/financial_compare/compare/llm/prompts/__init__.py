"""Compare 流水线 LLM system prompt 集中存放。"""

from financial_compare.compare.llm.prompts.content_match import CONTENT_MATCH_SYSTEM_PROMPT
from financial_compare.compare.llm.prompts.table_align import (
    TABLE_PAIR_MATCH_SYSTEM_PROMPT,
    TABLE_ROW_MATCH_SYSTEM_PROMPT,
)
from financial_compare.compare.llm.prompts.table_gate import (
    TABLE_TEXT_GATE_HEADER_SYSTEM,
    TABLE_TEXT_GATE_TAIL_SYSTEM,
)
from financial_compare.compare.llm.prompts.table_rebuild import VIRTUAL_TABLE_REBUILD_SYSTEM
from financial_compare.compare.llm.prompts.title_match import TITLE_MATCH_SYSTEM_PROMPT

__all__ = [
    "CONTENT_MATCH_SYSTEM_PROMPT",
    "TABLE_PAIR_MATCH_SYSTEM_PROMPT",
    "TABLE_ROW_MATCH_SYSTEM_PROMPT",
    "TABLE_TEXT_GATE_HEADER_SYSTEM",
    "TABLE_TEXT_GATE_TAIL_SYSTEM",
    "TITLE_MATCH_SYSTEM_PROMPT",
    "VIRTUAL_TABLE_REBUILD_SYSTEM",
]
