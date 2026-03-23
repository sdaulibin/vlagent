"""
银行注册表

管理所有银行的模版配置。
"""
import json
import os
from typing import Dict, List, Optional
from pathlib import Path

from ..models.schema import BankSchema


class BankRegistry:
    """银行注册表"""

    _instance: Optional["BankRegistry"] = None
    _schemas: Dict[str, BankSchema] = {}
    _keyword_mapping: Dict[str, str] = {}  # keyword -> template_id
    _default_template: str = "shandong_local"
    _initialized: bool = False

    def __new__(cls) -> "BankRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self, schemas_dir: Optional[str] = None) -> None:
        """
        初始化注册表，加载所有模版

        Args:
            schemas_dir: 模版目录路径，默认为 backend/config/native_statement
        """
        if self._initialized:
            return

        if schemas_dir is None:
            # 默认路径：从当前文件位置向上查找
            # 当前文件：backend/src/native_statement/schema/registry.py
            # 目标目录：backend/config/native_statement
            current_dir = Path(__file__).resolve()
            # 向上查找 backend 目录
            backend_dir = current_dir
            for _ in range(10):  # 最多向上查找10级
                if backend_dir.name == "backend":
                    break
                backend_dir = backend_dir.parent

            schemas_dir = backend_dir / "config" / "native_statement"

            # 如果还是找不到，尝试其他路径
            if not schemas_dir.exists():
                # 尝试从项目根目录查找
                project_root = backend_dir.parent
                schemas_dir = project_root / "backend" / "config" / "native_statement"

        schemas_dir = Path(schemas_dir)
        if not schemas_dir.exists():
            raise FileNotFoundError(f"模版目录不存在: {schemas_dir}")

        # 加载 bank_registry.json
        registry_path = schemas_dir / "bank_registry.json"
        if registry_path.exists():
            with open(registry_path, "r", encoding="utf-8") as f:
                registry_data = json.load(f)
                self._keyword_mapping = registry_data.get("keywords", {})
                self._default_template = registry_data.get("default", "shandong_local")

        # 加载所有银行模版
        for schema_file in schemas_dir.glob("*.json"):
            if schema_file.name == "bank_registry.json":
                continue

            try:
                with open(schema_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                schema = BankSchema.from_dict(data)
                self._schemas[schema.template_id] = schema

                # 更新关键词映射（如果模版中有 bank_names）
                for name in schema.bank_names:
                    if name not in self._keyword_mapping:
                        self._keyword_mapping[name] = schema.template_id

            except Exception as e:
                print(f"⚠️ 加载模版失败: {schema_file.name}, 错误: {e}")

        self._initialized = True
        print(f"✅ BankRegistry 初始化完成，加载了 {len(self._schemas)} 个银行模版")

    def get_schema(self, template_id: str) -> Optional[BankSchema]:
        """获取指定银行的模版"""
        if not self._initialized:
            self.initialize()
        return self._schemas.get(template_id)

    def detect_bank_type(self, text: str) -> str:
        """
        从文本中检测银行类型

        Args:
            text: PDF 全文文本

        Returns:
            银行模版 ID
        """
        if not self._initialized:
            self.initialize()

        text_lower = text.lower()
        for keyword, template_id in self._keyword_mapping.items():
            if keyword in text or keyword.lower() in text_lower:
                return template_id

        return self._default_template

    def get_all_template_ids(self) -> List[str]:
        """获取所有模版 ID"""
        if not self._initialized:
            self.initialize()
        return list(self._schemas.keys())

    def get_default_schema(self) -> BankSchema:
        """获取默认模版"""
        if not self._initialized:
            self.initialize()
        return self._schemas.get(self._default_template, BankSchema(template_id="unknown", bank_names=[]))

    @classmethod
    def reset(cls) -> None:
        """重置单例（用于测试）"""
        cls._instance = None
        cls._schemas = {}
        cls._keyword_mapping = {}
        cls._initialized = False


# 全局单例
registry = BankRegistry()
