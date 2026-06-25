"""引擎配置适配层：桥接参考项目的 app_config 接口到我们的 pydantic-settings。

参考项目（qdf_filediff）的 app_config.py 用 yaml 加载配置；本项目的配置来自
src/config.py（pydantic-settings）。引擎内部所有 `from financial_compare.app_config import ...`
的引用（OUTPUT_*、get_app_config、init_app_config）通过本文件适配，零改动。

引擎期望的配置 shape（get_app_config 返回值）：
  {
    "headers": [...],           # PDF 页眉检测关键词（pdf_header_detect 用）
    "compare": {"zh_script": True},  # 简繁归一化开关（text_compare 用）
    "llm": {"model", "base_url", "api_key"}  # LLM 配置（llm/model 用）
  }
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# 引擎内部快照/日志/解析中间产物的输出目录（独立于项目的 upload/）
OUTPUT_ROOT = Path("output")
OUTPUT_TASKS = OUTPUT_ROOT / "tasks"
OUTPUT_LOGS = OUTPUT_ROOT / "logs"
OUTPUT_PARSED = OUTPUT_ROOT / "parsed"

_cfg: dict[str, Any] | None = None


def _build_config() -> dict[str, Any]:
    """从项目的 settings 构造引擎期望的配置 dict。"""
    try:
        from src.config import settings, QWEN35_KEY, QWEN35_URL, QWEN35_MODEL
    except ImportError:
        # 兜底：settings 不可用时用空配置（引擎 LLM 调用会走 llm/model 自己的兜底）
        return {"headers": [], "compare": {"zh_script": True}, "llm": {}}

    return {
        # 页眉检测：青岛银行年报的页眉特征（可后续按需扩展或移到配置）
        "headers": [
            "青島銀行股份有限公司 | 2025 年度報告",
            "Bank of Qingdao Co., Ltd. | 2025 Annual Report",
        ],
        # 简繁归一化：引擎自带 zh_trad_to_simp.json，开启
        "compare": {"zh_script": True},
        # LLM 配置：从项目的 QWEN35_* 读
        "llm": {
            "model": QWEN35_MODEL,
            "base_url": QWEN35_URL,
            "api_key": QWEN35_KEY,
        },
    }


def init_app_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """初始化配置。本项目配置来自 settings，config_path 参数忽略（兼容引擎调用）。"""
    global _cfg
    _cfg = _build_config()
    return _cfg


def get_app_config() -> dict[str, Any]:
    """获取配置 dict（惰性初始化）。"""
    if _cfg is None:
        init_app_config()
    return _cfg


def reset_app_config() -> None:
    """重置配置缓存（测试用）。"""
    global _cfg
    _cfg = None


def default_config_path() -> Path:
    """兼容引用（引擎未直接调用，但保留接口完整性）。"""
    return Path("config/env.yml")
