"""
模板结构提取脚本

从格式一、格式二、验资询证函模板 PDF 中提取结构化内容（询证事项 + 表格字段），
输出为 JSON 模板文件，供格式比对使用。

用法:
    cd backend
    uv run python scripts/extract_templates.py
"""
import os
import sys
import json
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_qwen35
from src.config import MODEL_LOCAL
from src.json_repair import fix_json

TEMPLATE_PDFS = {
    "format_1": {
        "path": os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "格式一.pdf"),
        "name": "格式一（银行询证函）",
    },
    "format_2": {
        "path": os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "格式二.pdf"),
        "name": "格式二（银行询证函）",
    },
    "capital_verification": {
        "path": os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "验资.pdf"),
        "name": "验资询证函",
    },
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "templates")

EXTRACT_PROMPT = """
Role: 询证函格式分析专家

Task: 这是一份询证函模板PDF。请提取模板中所有需要比对的结构化内容。

## 提取规则：
1. 提取模板中每一个询证事项（编号如 1、2、3...或一、二、三...）
2. 对于每个事项，提取：
   - section: 事项编号（如 "1", "2", "3"）
   - title: 事项标题/描述文字，保留完整原文（将变量部分如日期、金额用 xxx 代替）
   - table_fields: 该事项下表格的所有列名（字段名），按表格从左到右的顺序
3. 如果事项没有表格，table_fields 为空数组
4. 提取所有事项，不要遗漏

## 输出格式：
返回 JSON 数组，每个元素代表一个事项：
```json
[
  {
    "section": "1",
    "title": "截至xxxx年xx月xx日止，本公司在贵行的存款情况如下：",
    "table_fields": ["账户名称", "账号", "币种", "期末余额"]
  }
]
```

仅输出 JSON，不要解释。
"""


def extract_template(pdf_path: str, template_name: str) -> list:
    """从模板 PDF 提取结构化内容"""
    tmp_dir = tempfile.mkdtemp(prefix="template_")
    try:
        image_paths = split_pdf_to_images(pdf_path, tmp_dir, dpi=200)
        if not image_paths:
            print(f"  ❌ PDF 转图片失败: {pdf_path}")
            return []

        print(f"  📄 共 {len(image_paths)} 页")

        # 对每一页提取结构
        all_items = []
        for i, img_path in enumerate(image_paths):
            print(f"  🔍 正在分析第 {i + 1} 页...")
            response = request_qwen35(
                question=EXTRACT_PROMPT,
                file_base=img_path,
                show_request=False,
            ).strip()

            try:
                items = json.loads(fix_json(response))
                if isinstance(items, list):
                    all_items.extend(items)
                    print(f"     ✅ 提取到 {len(items)} 个事项")
                else:
                    print(f"     ⚠️  返回非数组: {response[:100]}")
            except Exception as e:
                print(f"     ❌ JSON 解析失败: {e}")
                print(f"     原始响应: {response[:200]}")

        # 去重（相同 section 的合并）
        seen = {}
        for item in all_items:
            section = item.get("section", "")
            if section not in seen:
                seen[section] = item
            else:
                # 合并 table_fields
                existing_fields = seen[section].get("table_fields", [])
                new_fields = item.get("table_fields", [])
                for f in new_fields:
                    if f not in existing_fields:
                        existing_fields.append(f)
                seen[section]["table_fields"] = existing_fields

        return list(seen.values())

    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for format_key, info in TEMPLATE_PDFS.items():
        pdf_path = info["path"]
        name = info["name"]

        print(f"\n{'=' * 50}")
        print(f"📋 提取模板: {name}")
        print(f"   文件: {pdf_path}")

        if not os.path.exists(pdf_path):
            print(f"  ❌ 文件不存在!")
            continue

        items = extract_template(pdf_path, name)

        template = {
            "format_name": name,
            "format_key": format_key,
            "items": items,
        }

        output_path = os.path.join(OUTPUT_DIR, f"{format_key}_template.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)

        print(f"  ✅ 已保存: {output_path}")
        print(f"  📊 共提取 {len(items)} 个事项")

    print(f"\n{'=' * 50}")
    print("✅ 所有模板提取完成！")
    print(f"输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
