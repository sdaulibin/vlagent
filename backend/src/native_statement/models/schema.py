"""
银行模版数据模型

定义银行流水 PDF 解析所需的模版结构。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class SummaryField:
    """汇总字段定义"""
    name: str                          # 原始字段名（如 "账号"）
    field: str                         # 标准字段名（如 "account_number"）
    pattern: Optional[str] = None      # 正则提取模式
    required: bool = False             # 是否必填


@dataclass
class TransactionField:
    """交易字段定义"""
    name: str                          # 原始表头名（如 "交易日期"）
    field: str                         # 标准字段名（如 "transaction_date"）
    type: str = "string"               # 字段类型: string, amount, datetime, int
    required: bool = False             # 是否必填


@dataclass
class ExtractionConfig:
    """提取配置"""
    preferred_strategy: str = "auto"   # 首选策略: auto, camelot_stream, pdfplumber_lines, pdfplumber_text
    fallback_strategies: List[str] = field(default_factory=lambda: ["pdfplumber_lines", "pdfplumber_text"])
    multiline_merge: bool = False      # 是否需要多行合并
    serial_column_index: int = 0       # 流水号所在列索引
    min_columns: int = 5               # 最小列数要求
    first_page_only_summary: bool = True  # 汇总信息是否只在第一页提取


@dataclass
class DetectionConfig:
    """银行检测配置"""
    keywords: List[str] = field(default_factory=list)           # 关键词列表
    serial_pattern: Optional[str] = None                        # 流水号正则模式
    header_keywords: List[str] = field(default_factory=list)    # 表头关键词


@dataclass
class PostProcessingConfig:
    """后处理配置"""
    clean_counterparty_name: bool = False      # 清理对方户名
    merge_serial_fragments: bool = False       # 合并流水号片段
    serial_fragment_pattern: Optional[str] = None  # 流水号片段正则
    clean_time_string: bool = True             # 清理时间字符串
    remove_newlines: bool = True               # 移除换行符


@dataclass
class BankSchema:
    """银行模版完整定义"""
    template_id: str                                          # 模版 ID（如 "cmb"）
    bank_names: List[str]                                     # 银行名称列表
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    post_processing: PostProcessingConfig = field(default_factory=PostProcessingConfig)
    summary_schema: Dict[str, SummaryField] = field(default_factory=dict)
    transaction_schema: List[TransactionField] = field(default_factory=list)
    raw_config: Dict[str, Any] = field(default_factory=dict, repr=False)  # 原始 JSON 配置

    @classmethod
    def from_dict(cls, data: dict) -> "BankSchema":
        """从字典创建模版实例"""
        # 解析 detection 配置
        detection_data = data.get("detection", {})
        detection = DetectionConfig(
            keywords=detection_data.get("keywords", data.get("bank_names", [])),
            serial_pattern=detection_data.get("serial_pattern"),
            header_keywords=detection_data.get("header_keywords", []),
        )

        # 解析 extraction 配置
        extraction_data = data.get("extraction", {})
        extraction = ExtractionConfig(
            preferred_strategy=extraction_data.get("preferred_strategy", "auto"),
            fallback_strategies=extraction_data.get("fallback_strategies", ["pdfplumber_lines", "pdfplumber_text"]),
            multiline_merge=extraction_data.get("multiline_merge", False),
            serial_column_index=extraction_data.get("serial_column_index", 0),
            min_columns=extraction_data.get("min_columns", 5),
            first_page_only_summary=extraction_data.get("first_page_only_summary", True),
        )

        # 解析 post_processing 配置
        post_data = data.get("post_processing", {})
        post_processing = PostProcessingConfig(
            clean_counterparty_name=post_data.get("clean_counterparty_name", False),
            merge_serial_fragments=post_data.get("merge_serial_fragments", False),
            serial_fragment_pattern=post_data.get("serial_fragment_pattern"),
            clean_time_string=post_data.get("clean_time_string", True),
            remove_newlines=post_data.get("remove_newlines", True),
        )

        # 解析 summary_schema
        summary_schema = {}
        for name, config in data.get("summary_schema", {}).items():
            if isinstance(config, dict):
                summary_schema[name] = SummaryField(
                    name=name,
                    field=config.get("field", name),
                    pattern=config.get("pattern"),
                    required=config.get("required", False),
                )
            else:
                # 简单格式：{"字段名": ""}
                summary_schema[name] = SummaryField(name=name, field=name)

        # 解析 transaction_schema
        transaction_schema = []
        tx_schema = data.get("transaction_schema", [])
        if isinstance(tx_schema, list):
            for item in tx_schema:
                if isinstance(item, dict):
                    # 可能是列表中的字典格式
                    for name, config in item.items():
                        if isinstance(config, dict):
                            transaction_schema.append(TransactionField(
                                name=name,
                                field=config.get("field", name),
                                type=config.get("type", "string"),
                                required=config.get("required", False),
                            ))
                        else:
                            transaction_schema.append(TransactionField(name=name, field=name))
                else:
                    # 简单格式
                    transaction_schema.append(TransactionField(name=str(item), field=str(item)))
        elif isinstance(tx_schema, dict):
            # 字典格式
            for name, config in tx_schema.items():
                if isinstance(config, dict):
                    transaction_schema.append(TransactionField(
                        name=name,
                        field=config.get("field", name),
                        type=config.get("type", "string"),
                    ))
                else:
                    transaction_schema.append(TransactionField(name=name, field=name))

        return cls(
            template_id=data.get("template_id", "unknown"),
            bank_names=data.get("bank_names", []),
            detection=detection,
            extraction=extraction,
            post_processing=post_processing,
            summary_schema=summary_schema,
            transaction_schema=transaction_schema,
            raw_config=data,
        )

    def get_header_mapping(self) -> Dict[str, str]:
        """获取表头映射字典"""
        return {f.name: f.field for f in self.transaction_schema}
