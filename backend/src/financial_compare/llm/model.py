"""LLM 调用适配层：桥接引擎的 chat() 接口到项目的 request_qwen35。

参考项目（qdf_filediff）的 llm/model.py 自己创建 OpenAI 客户端；
本项目有统一的 LLM 客户端 services/core/request_ai.py::request_qwen35
（复用连接池、并发信号量、QWEN35_* 配置）。

引擎内部所有 `from financial_compare.llm.model import chat` 的引用通过本文件适配，零改动。
注意：引擎的 chat() 是同步调用（在 ThreadPoolExecutor 中运行），
request_qwen35 也是同步函数，直接转发即可。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from financial_compare.app_config import OUTPUT_LOGS, get_app_config

_LOGGER_NAME = "filediff.llm"
_logger: logging.Logger | None = None
_STARTUP_LOG_TAG = f"{datetime.now().strftime('%H%M%S')}"


def _llm_settings() -> dict[str, str]:
    """从 get_app_config() 读 LLM 配置（适配后端由 app_config.py 从 settings 构造）。"""
    raw = get_app_config().get("llm")
    if isinstance(raw, dict):
        return {k: str(v) for k, v in raw.items()}
    if isinstance(raw, list):
        merged: dict[str, str] = {}
        for item in raw:
            if isinstance(item, dict):
                merged.update({k: str(v) for k, v in item.items()})
        return merged
    raise ValueError("配置缺少 llm 段")


def load_llm_config() -> dict[str, str]:
    return _llm_settings()


def _resolve_api_key(yaml_key: str) -> str:
    for env_name in ("OPENAI_API_KEY", "DASHSCOPE_API_KEY"):
        v = os.getenv(env_name)
        if v:
            return v
    return yaml_key


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    log_dir = OUTPUT_LOGS
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"llm_{_STARTUP_LOG_TAG}.log"
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(fh)
    logger.propagate = False
    _logger = logger
    return logger


def chat(system: str, user: str) -> str:
    """使用 system + user 提示词调用大模型，返回 assistant 文本。

    适配到项目的 request_qwen35（复用连接池、QWEN35 配置）。
    引擎在 ThreadPoolExecutor 中同步调用本函数，request_qwen35 也是同步的。
    """
    cfg = load_llm_config()
    model = cfg.get("model") or "Qwen3.5-35B"
    log = _get_logger()
    log.info("REQUEST model=%s user=%r", model, user[:500])

    # 惰性导入避免循环依赖（services.core 可能在初始化链上）
    from services.core.request_ai import request_qwen35

    # 用流式调用（默认），request_qwen35 会聚合流式响应为完整字符串。
    # 不用 is_stream=False：request_qwen35 在非流式时仍传 stream_options，
    # vLLM 后端会拒绝（stream_options 仅 stream=True 时合法）。
    text = request_qwen35(
        question=user,
        system_content=system,
        model=model,
        is_stream=True,
        show_request=False,
        show_cost=False,
        temperature=0.1,      # 引擎原版用 0.1（判定任务需要确定性）
    )
    text = text or ""
    log.info("RESPONSE %r", text[:500])
    return text


def reset_llm_client() -> None:
    """测试用：重置日志缓存。"""
    global _logger
    _logger = None


if __name__ == "__main__":
    from financial_compare.app_config import init_app_config

    try:
        init_app_config()
        out = chat("You are a helpful assistant.", "用一句话介绍你自己。")
        print(out)
    except Exception as e:
        print(f"错误：{e}")
