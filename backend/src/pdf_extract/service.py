"""
通用 PDF 提取核心服务

处理流程：PDF → 拆分图片 → 构建 Schema + Prompt → 调用 AI → 修复 JSON → 保存结果
"""
import os
import json
import shutil
import tempfile
from datetime import datetime
from typing import Any, Dict, List

from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_qwen35
from src.json_repair import fix_json
from sqlmodel.ext.asyncio.session import AsyncSession
from src.pdf_extract.models import PdfExtractTask, PdfExtractResult


def _generate_schema(fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    """根据字段列表生成 JSON Schema"""
    properties = {}
    required = []

    for field in fields:
        field_type = field.get("type", "string")
        description = field.get("description") or f"提取 {field['name']}"

        if field_type == "array":
            field_schema = {
                "type": "array",
                "items": {"type": "string"},
                "description": f"{description}，如果有多个请返回数组"
            }
        elif field_type == "object_array":
            item_properties = {}
            item_required = []
            for item in (field.get("items") or []):
                item_properties[item["name"]] = {
                    "type": item.get("type", "string"),
                    "description": item.get("description") or item["name"]
                }
                item_required.append(item["name"])
            field_schema = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": item_properties,
                    "required": item_required
                },
                "description": f"{description}，返回对象数组"
            }
        else:
            field_schema = {
                "type": field_type,
                "description": description
            }

        if field_type == "number":
            field_schema["description"] += "（请提取纯数字，不要包含货币符号）"

        properties[field["name"]] = field_schema
        required.append(field["name"])

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False
    }


SYSTEM_PROMPT = """你是一个专业的文档信息提取专家。请仔细阅读图片中的内容，并严格按照给定的 JSON Schema 提取信息。

要求：
1. 仔细查看所有页面的图片
2. 准确提取 Schema 中要求的所有字段
3. 如果某个字段在图片中找不到，填 null 或空字符串
4. 严格遵守字段类型定义：
   - 如果 schema 中 type 为 "string"，即使有多个值，也必须返回单个字符串（多个值用逗号拼接）
   - 如果 schema 中 type 为 "array"，才返回数组格式如 ["张三", "李四"]
5. 不要用顿号、逗号等把多个条目拼接成一个字符串（仅当 type 为 string 且需要合并多个值时才使用逗号）
6. 只返回纯 JSON，不要包含任何 markdown 标记或其他解释
7. 确保 JSON 格式正确，可以被直接解析"""


def _build_user_prompt(schema: Dict[str, Any]) -> str:
    """构建用户提示词"""
    schema_json = json.dumps(schema, ensure_ascii=False, indent=2)
    return f"""请从以下图片中提取信息，并按此 JSON Schema 返回：

{schema_json}

请只返回 JSON，不要其他内容。"""


def _extract_with_ai(image_paths: List[str], fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    """调用 AI 提取信息"""
    schema = _generate_schema(fields)
    user_prompt = _build_user_prompt(schema)

    response = request_qwen35(
        question=user_prompt,
        file_base=image_paths[0] if len(image_paths) == 1 else "",
        file_ary=image_paths if len(image_paths) > 1 else None,
        pic_tip=len(image_paths) > 1,
        system_content=SYSTEM_PROMPT,
        show_request=False,
        temperature=0.1,
        is_stream=True
    ).strip()

    return json.loads(fix_json(response))


async def process_pdf_extract(db: AsyncSession, task: PdfExtractTask):
    """后台任务：处理通用 PDF 提取"""
    tmp_dir = tempfile.mkdtemp(prefix="pdf_extract_")
    start_time = datetime.utcnow()

    try:
        task.status = "processing"
        db.add(task)
        await db.commit()

        # PDF 转图片
        image_paths = split_pdf_to_images(task.file_path, tmp_dir, dpi=200)
        if not image_paths:
            raise ValueError("PDF 转换图片失败，未产生文件。")

        task.page_count = len(image_paths)

        # 解析字段定义
        fields = json.loads(task.fields_json)

        # 调用 AI 提取
        extracted_data = _extract_with_ai(image_paths, fields)

        # 保存结果
        result = PdfExtractResult(
            task_id=task.id,
            extracted_data=json.dumps(extracted_data, ensure_ascii=False)
        )
        db.add(result)
        task.status = "done"

    except Exception as e:
        print(f"PDF Extract Error: {e}")
        task.status = "failed"
        task.error_msg = str(e)

    finally:
        end_time = datetime.utcnow()
        task.processing_duration = (end_time - start_time).total_seconds()
        db.add(task)
        await db.commit()

        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
