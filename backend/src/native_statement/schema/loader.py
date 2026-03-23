"""
模版加载器

从文件系统加载银行模版配置。
"""
import json
from pathlib import Path
from typing import Optional, Dict, Any

from ..models.schema import BankSchema
from .registry import registry


class SchemaLoader:
    """模版加载器"""

    @staticmethod
    def load(template_id: str) -> Optional[BankSchema]:
        """
        加载指定银行的模版

        Args:
            template_id: 银行模版 ID

        Returns:
            BankSchema 或 None
        """
        return registry.get_schema(template_id)

    @staticmethod
    def load_from_file(file_path: str) -> BankSchema:
        """
        从文件加载模版

        Args:
            file_path: 模版文件路径

        Returns:
            BankSchema
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return BankSchema.from_dict(data)

    @staticmethod
    def detect_and_load(text: str) -> BankSchema:
        """
        从文本中检测银行类型并加载对应模版

        Args:
            text: PDF 全文文本

        Returns:
            BankSchema（如果未识别则返回默认模版）
        """
        template_id = registry.detect_bank_type(text)
        schema = registry.get_schema(template_id)
        if schema is None:
            schema = registry.get_default_schema()
        return schema

    @staticmethod
    def save_schema(schema: BankSchema, output_dir: str) -> str:
        """
        保存模版到文件

        Args:
            schema: 银行模版
            output_dir: 输出目录

        Returns:
            保存的文件路径
        """
        output_path = Path(output_dir) / f"{schema.template_id}.json"

        # 构建输出数据
        data = {
            "template_id": schema.template_id,
            "bank_names": schema.bank_names,
            "detection": {
                "keywords": schema.detection.keywords,
                "serial_pattern": schema.detection.serial_pattern,
                "header_keywords": schema.detection.header_keywords,
            },
            "extraction": {
                "preferred_strategy": schema.extraction.preferred_strategy,
                "fallback_strategies": schema.extraction.fallback_strategies,
                "multiline_merge": schema.extraction.multiline_merge,
                "serial_column_index": schema.extraction.serial_column_index,
                "min_columns": schema.extraction.min_columns,
                "first_page_only_summary": schema.extraction.first_page_only_summary,
            },
            "post_processing": {
                "clean_counterparty_name": schema.post_processing.clean_counterparty_name,
                "merge_serial_fragments": schema.post_processing.merge_serial_fragments,
                "serial_fragment_pattern": schema.post_processing.serial_fragment_pattern,
                "clean_time_string": schema.post_processing.clean_time_string,
                "remove_newlines": schema.post_processing.remove_newlines,
            },
            "summary_schema": {},
            "transaction_schema": [],
        }

        # 添加 summary_schema
        for name, field in schema.summary_schema.items():
            data["summary_schema"][name] = {
                "field": field.field,
                "pattern": field.pattern,
                "required": field.required,
            }

        # 添加 transaction_schema
        for field in schema.transaction_schema:
            data["transaction_schema"].append({
                field.name: {
                    "field": field.field,
                    "type": field.type,
                    "required": field.required,
                }
            })

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        return str(output_path)
